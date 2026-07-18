#!/usr/bin/env python3
"""Reconcile OpenSearch-native retention, dashboards, and alert monitors."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import dashboard_definitions


METRICS_PATTERN = "otel-v1-apm-metrics*"
LOGS_PATTERN = "otel-v1-apm-logs*"
TRACES_PATTERN = "otel-v1-apm-span-*"
LOGS_TIME_FIELD = dashboard_definitions.LOGS_TIME_FIELD
LOGS_LEGACY_TIME_FIELD = "observedTime"
MANAGED_BY = "shared-gitops-k8s-cluster"

POSTGRES_ACTIVITY_QUERY = (
    'name: "pg_stat_activity_count" and '
    'metric.attributes.backend_type: "client backend" and '
    '(metric.attributes.state: "idle" or metric.attributes.state: "active")'
)
PGPOOL_FRONTEND_QUERY = 'name: "pgpool2_frontend_used" or name: "pgpool2_frontend_total"'
REDIS_CLIENTS_QUERY = 'name: "redis_connected_clients"'
REDIS_MEMORY_QUERY = 'name: "redis_memory_used_bytes"'
DATA_PLATFORM_METRICS_QUERY = (
    "name: pg_stat_activity_count or name: pgpool2_frontend_used or "
    "name: pgpool2_frontend_total or name: redis_connected_clients or "
    'name: "redis_memory_used_bytes"'
)
CORRELATED_LOGS_QUERY = 'traceId: * AND NOT traceId: ""'
ERROR_LOGS_WITH_TRACE_QUERY = (
    'severityText: ("ERROR" or "FATAL") AND traceId: * AND NOT traceId: ""'
)
DB_PRESSURE_LOGS_QUERY = (
    "body: (*connection* OR *pool* OR *postgres* OR *redis* OR *timeout* OR *Pgpool*)"
)
HTTP_SPANS_QUERY = 'name: "http_request"'


class ApiError(RuntimeError):
    """An HTTP API request failed."""


class JsonClient:
    def __init__(self, base_url: str, *, dashboards: bool = False) -> None:
        self.base_url = base_url.rstrip("/")
        self.dashboards = dashboards

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: Any | None = None,
        allowed: tuple[int, ...] = (),
    ) -> tuple[int, Any | None]:
        data = None if payload is None else json.dumps(payload).encode()
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if self.dashboards:
            headers["osd-xsrf"] = "true"
        request = Request(
            f"{self.base_url}/{path.lstrip('/')}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=30) as response:  # noqa: S310
                body = response.read()
                return response.status, json.loads(body) if body else None
        except HTTPError as error:
            body = error.read().decode(errors="replace")
            if error.code in allowed:
                return error.code, json.loads(body) if body else None
            raise ApiError(f"{method} {path} returned {error.code}: {body}") from error
        except URLError as error:
            raise ApiError(f"{method} {path} failed: {error.reason}") from error


def wait_ready(client: JsonClient, path: str, name: str) -> None:
    for _ in range(60):
        try:
            client.request(path)
            return
        except ApiError:
            time.sleep(5)
    raise ApiError(f"{name} did not become ready within five minutes")


def lifecycle_policy(retention_days: int, patterns: list[str]) -> dict[str, Any]:
    return {
        "policy": {
            "description": (
                f"Delete dev telemetry after {retention_days} days; managed by {MANAGED_BY}"
            ),
            "default_state": "hot",
            "states": [
                {
                    "name": "hot",
                    "actions": [],
                    "transitions": [
                        {
                            "state_name": "delete",
                            "conditions": {"min_index_age": f"{retention_days}d"},
                        }
                    ],
                },
                {
                    "name": "delete",
                    "actions": [{"delete": {}}],
                    "transitions": [],
                },
            ],
            "ism_template": [{"index_patterns": patterns, "priority": 200}],
        }
    }


def upsert_policy(
    client: JsonClient, policy_id: str, retention_days: int, patterns: list[str]
) -> None:
    upsert_policy_payload(client, policy_id, lifecycle_policy(retention_days, patterns))


def upsert_policy_payload(
    client: JsonClient, policy_id: str, payload: dict[str, Any]
) -> None:
    path = f"_plugins/_ism/policies/{quote(policy_id)}"
    status, current = client.request(path, allowed=(404,))
    query = ""
    if status == 200:
        query = "?" + urlencode(
            {
                "if_seq_no": current["_seq_no"],
                "if_primary_term": current["_primary_term"],
            }
        )
    client.request(
        path + query,
        method="PUT",
        payload=payload,
    )


def trace_lifecycle_policy(retention_days: int) -> dict[str, Any]:
    """Extend Data Prepper's raw-span rollover policy with bounded retention."""
    return {
        "policy": {
            "description": (
                "Roll raw spans daily and delete dev telemetry after "
                f"{retention_days} days; managed by {MANAGED_BY}"
            ),
            "default_state": "current_write_index",
            "states": [
                {
                    "name": "current_write_index",
                    "actions": [
                        {
                            "retry": {
                                "count": 3,
                                "backoff": "exponential",
                                "delay": "1m",
                            },
                            "rollover": {
                                "min_size": "50gb",
                                "min_index_age": "24h",
                                "copy_alias": False,
                            },
                        }
                    ],
                    "transitions": [
                        {
                            "state_name": "delete",
                            "conditions": {"min_index_age": f"{retention_days}d"},
                        }
                    ],
                },
                {
                    "name": "delete",
                    "actions": [{"delete": {}}],
                    "transitions": [],
                },
            ],
            "ism_template": [{"index_patterns": [TRACES_PATTERN], "priority": 200}],
        }
    }


def index_template(pattern: str, time_field: str) -> dict[str, Any]:
    return {
        "index_patterns": [pattern],
        "priority": 200,
        "_meta": {"managed_by": MANAGED_BY},
        "template": {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "refresh_interval": "30s",
            },
            "mappings": {
                "properties": {
                    time_field: {
                        "type": "date",
                        "format": "strict_date_optional_time||epoch_millis",
                    }
                }
            },
        },
    }


def logs_index_template(pattern: str) -> dict[str, Any]:
    """Map both OTLP log timestamp field names for backward compatibility."""
    date_mapping = {
        "type": "date",
        "format": "strict_date_optional_time||epoch_millis",
    }
    return {
        "index_patterns": [pattern],
        "priority": 200,
        "_meta": {"managed_by": MANAGED_BY},
        "template": {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "refresh_interval": "30s",
            },
            "mappings": {
                "properties": {
                    LOGS_TIME_FIELD: date_mapping,
                    "observedTime": date_mapping,
                    "log.attributes.event_category": {
                        "type": "keyword",
                        "ignore_above": 256,
                    },
                    "log.attributes.event_class": {
                        "type": "keyword",
                        "ignore_above": 256,
                    },
                    "log.attributes.has_trace": {
                        "type": "boolean",
                    },
                }
            },
        },
    }


def index_exposes_time_field(properties: dict[str, Any], time_field: str) -> bool:
    if time_field in properties:
        return True
    return (
        time_field == LOGS_TIME_FIELD and LOGS_LEGACY_TIME_FIELD in properties
    )


def attach_existing_index(
    client: JsonClient, index: str, policy_id: str, time_field: str
) -> None:
    status, _ = client.request(index, method="HEAD", allowed=(404,))
    if status == 404:
        return
    client.request(
        f"{quote(index)}/_settings",
        method="PUT",
        payload={"index": {"number_of_replicas": 0, "refresh_interval": "30s"}},
    )
    _, explanation = client.request(
        f"_plugins/_ism/explain/{quote(index)}", allowed=(404,)
    )
    current = (explanation or {}).get(index, {}).get("policy_id")
    if current and current != policy_id:
        raise ApiError(f"{index} is already managed by unexpected policy {current}")
    if not current:
        client.request(
            f"_plugins/_ism/add/{quote(index)}",
            method="POST",
            payload={"policy_id": policy_id},
        )
    # The field is part of the contract even on the legacy unsuffixed index.
    _, mapping = client.request(f"{quote(index)}/_mapping")
    properties = mapping[index]["mappings"].get("properties", {})
    if not index_exposes_time_field(properties, time_field):
        raise ApiError(f"{index} does not expose required time field {time_field}")


def matching_indices(client: JsonClient, pattern: str) -> list[str]:
    status, response = client.request(
        f"_cat/indices/{quote(pattern, safe='*')}?"
        + urlencode({"format": "json", "h": "index", "expand_wildcards": "open"}),
        allowed=(404,),
    )
    if status == 404:
        return []
    return sorted(
        row["index"]
        for row in response or []
        if isinstance(row, dict) and row.get("index")
    )


def reconcile_matching_indices(
    client: JsonClient, pattern: str, policy_id: str, time_field: str
) -> None:
    """Apply the contract to indices created before their template existed."""
    for index in matching_indices(client, pattern):
        attach_existing_index(client, index, policy_id, time_field)


def reconcile_trace_storage(client: JsonClient) -> None:
    """Keep Data Prepper trace mappings/alias while applying dev storage settings."""
    template_name = "otel-v1-apm-span-index-template"
    status, response = client.request(f"_template/{template_name}", allowed=(404,))
    if status == 404:
        raise ApiError(f"Data Prepper trace template {template_name} is missing")
    template = response[template_name]
    settings = template.setdefault("settings", {}).setdefault("index", {})
    settings["number_of_replicas"] = 0
    settings["refresh_interval"] = "30s"
    client.request(f"_template/{template_name}", method="PUT", payload=template)
    for index in matching_indices(client, TRACES_PATTERN):
        client.request(
            f"{quote(index)}/_settings",
            method="PUT",
            payload={"index": {"number_of_replicas": 0, "refresh_interval": "30s"}},
        )


def monitor_payload(
    *,
    name: str,
    indices: list[str],
    query: dict[str, Any],
    condition: str,
    severity: str,
) -> dict[str, Any]:
    trigger_id = name.lower().replace(" ", "-") + "-trigger"
    return {
        "type": "monitor",
        "schema_version": 2,
        "name": name,
        "monitor_type": "query_level_monitor",
        "enabled": True,
        "schedule": {"period": {"interval": 5, "unit": "MINUTES"}},
        "inputs": [{"search": {"indices": indices, "query": query}}],
        "triggers": [
            {
                "query_level_trigger": {
                    "id": trigger_id,
                    "name": name,
                    "severity": severity,
                    "condition": {"script": {"source": condition, "lang": "painless"}},
                    # Alerts are evaluated and visible in Dashboards. Notification
                    # channels remain a separate secret-backed integration decision.
                    "actions": [],
                }
            }
        ],
        "ui_metadata": {},
    }


def desired_monitors() -> list[dict[str, Any]]:
    metrics_recent = {
        "size": 0,
        "track_total_hits": True,
        "query": {"range": {"time": {"gte": "now-10m", "lte": "now"}}},
    }
    error_logs = {
        "size": 0,
        "track_total_hits": True,
        "query": {
            "bool": {
                "filter": [
                    {"range": {"observedTimestamp": {"gte": "now-5m", "lte": "now"}}},
                    {"terms": {"severityText.keyword": ["ERROR", "FATAL"]}},
                ]
            }
        },
    }
    rerp_metrics = {
        "size": 0,
        "track_total_hits": True,
        "query": {
            "bool": {
                "filter": [
                    {"range": {"time": {"gte": "now-10m", "lte": "now"}}},
                    {"term": {"serviceName.keyword": "api"}},
                    {"term": {"name.keyword": "api_requests_total"}},
                ]
            }
        },
    }
    postgres_metrics = {
        "size": 0,
        "track_total_hits": True,
        "query": {
            "bool": {
                "filter": [
                    {"range": {"time": {"gte": "now-10m", "lte": "now"}}},
                    {"prefix": {"name.keyword": "pg_"}},
                ]
            }
        },
    }
    loadlinker_p0_errors = {
        "size": 0,
        "track_total_hits": True,
        "query": {
            "bool": {
                "filter": [
                    {"range": {"observedTimestamp": {"gte": "now-5m", "lte": "now"}}},
                    {"terms": {"severityText.keyword": ["ERROR", "FATAL"]}},
                    {
                        "terms": {
                            "serviceName.keyword": [
                                "bff",
                                "bidding",
                                "consignments",
                                "notifications",
                            ]
                        }
                    },
                ]
            }
        },
    }
    sesame_auth_errors = {
        "size": 0,
        "track_total_hits": True,
        "query": {
            "bool": {
                "filter": [
                    {"range": {"observedTimestamp": {"gte": "now-5m", "lte": "now"}}},
                    {"terms": {"severityText.keyword": ["ERROR", "FATAL"]}},
                    {
                        "terms": {
                            "serviceName.keyword": [
                                "identity-login-service",
                                "identity-session-service",
                                "authz-core",
                            ]
                        }
                    },
                ]
            }
        },
    }
    loadlinker_p0_spans = {
        "size": 0,
        "track_total_hits": True,
        "query": {
            "bool": {
                "filter": [
                    {"range": {"startTime": {"gte": "now-10m", "lte": "now"}}},
                    {"term": {"name.keyword": "http_request"}},
                    {
                        "terms": {
                            "serviceName.keyword": [
                                "bff",
                                "bidding",
                                "consignments",
                                "notifications",
                            ]
                        }
                    },
                ]
            }
        },
    }
    sesame_auth_spans = {
        "size": 0,
        "track_total_hits": True,
        "query": {
            "bool": {
                "filter": [
                    {"range": {"startTime": {"gte": "now-10m", "lte": "now"}}},
                    {"term": {"name.keyword": "http_request"}},
                    {
                        "terms": {
                            "serviceName.keyword": [
                                "identity-login-service",
                                "identity-session-service",
                                "authz-core",
                            ]
                        }
                    },
                ]
            }
        },
    }
    return [
        monitor_payload(
            name="Telemetry metrics stale",
            indices=[METRICS_PATTERN],
            query=metrics_recent,
            condition="ctx.results[0].hits.total.value == 0",
            severity="1",
        ),
        monitor_payload(
            name="Telemetry error logs detected",
            indices=[LOGS_PATTERN],
            query=error_logs,
            condition="ctx.results[0].hits.total.value > 0",
            severity="2",
        ),
        monitor_payload(
            name="RERP API metrics stale",
            indices=[METRICS_PATTERN],
            query=rerp_metrics,
            condition="ctx.results[0].hits.total.value == 0",
            severity="1",
        ),
        monitor_payload(
            name="Postgres metrics stale",
            indices=[METRICS_PATTERN],
            query=postgres_metrics,
            condition="ctx.results[0].hits.total.value == 0",
            severity="1",
        ),
        monitor_payload(
            name="Redis metrics stale",
            indices=[METRICS_PATTERN],
            query={
                "size": 0,
                "track_total_hits": True,
                "query": {
                    "bool": {
                        "filter": [
                            {"range": {"time": {"gte": "now-10m", "lte": "now"}}},
                            {"prefix": {"name.keyword": "redis_"}},
                        ]
                    }
                },
            },
            condition="ctx.results[0].hits.total.value == 0",
            severity="1",
        ),
        monitor_payload(
            name="Loadlinker P0 error burst",
            indices=[LOGS_PATTERN],
            query=loadlinker_p0_errors,
            condition="ctx.results[0].hits.total.value > 5",
            severity="2",
        ),
        monitor_payload(
            name="Sesame auth error logs",
            indices=[LOGS_PATTERN],
            query=sesame_auth_errors,
            condition="ctx.results[0].hits.total.value > 0",
            severity="2",
        ),
        monitor_payload(
            name="Loadlinker P0 traces stale",
            indices=[TRACES_PATTERN],
            query=loadlinker_p0_spans,
            condition="ctx.results[0].hits.total.value == 0",
            severity="1",
        ),
        monitor_payload(
            name="Sesame auth traces stale",
            indices=[TRACES_PATTERN],
            query=sesame_auth_spans,
            condition="ctx.results[0].hits.total.value == 0",
            severity="1",
        ),
    ]


def existing_monitors(client: JsonClient) -> dict[str, list[dict[str, Any]]]:
    status, response = client.request(
        "_plugins/_alerting/monitors/_search",
        method="POST",
        payload={
            "size": 100,
            "seq_no_primary_term": True,
            "query": {"match_all": {}},
        },
        allowed=(404,),
    )
    if status == 404:
        return {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for hit in response.get("hits", {}).get("hits", []):
        source = hit.get("_source", {})
        name = source.get("name") or source.get("monitor", {}).get("name")
        if name:
            grouped.setdefault(name, []).append(hit)
    return grouped


def upsert_monitors(client: JsonClient) -> None:
    current = existing_monitors(client)
    for monitor in desired_monitors():
        hits = current.get(monitor["name"], [])
        if not hits:
            client.request(
                "_plugins/_alerting/monitors", method="POST", payload=monitor
            )
            current = existing_monitors(client)
            continue
        hit, *duplicates = sorted(hits, key=lambda item: item["_seq_no"], reverse=True)
        for duplicate in duplicates:
            client.request(
                f"_plugins/_alerting/monitors/{quote(duplicate['_id'])}",
                method="DELETE",
            )
        query = urlencode(
            {
                "if_seq_no": hit["_seq_no"],
                "if_primary_term": hit["_primary_term"],
            }
        )
        client.request(
            f"_plugins/_alerting/monitors/{quote(hit['_id'])}?{query}",
            method="PUT",
            payload=monitor,
        )


DASHBOARDS_DIR = Path(
    os.environ.get("OBSERVABILITY_DASHBOARDS_DIR", "/opt/observability/dashboards")
)


def import_ndjson_file(client: JsonClient, path: Path) -> None:
    boundary = "ObservabilityDashboardImport"
    payload = path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f"Content-Type: application/ndjson\r\n\r\n"
    ).encode() + payload + f"\r\n--{boundary}--\r\n".encode()
    headers = {
        "Accept": "application/json",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "osd-xsrf": "true",
    }
    request = Request(
        f"{client.base_url}/api/saved_objects/_import?overwrite=true",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:  # noqa: S310
            result = json.loads(response.read())
    except HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise ApiError(f"import {path.name} returned {error.code}: {detail}") from error
    except URLError as error:
        raise ApiError(f"import {path.name} failed: {error.reason}") from error
    if result.get("errors"):
        raise ApiError(f"import {path.name} failed: {result['errors']}")


def import_dashboard_bundles(client: JsonClient, directory: Path) -> None:
    if not directory.is_dir():
        raise ApiError(f"dashboard bundle directory missing: {directory}")
    bundle_files = sorted(directory.glob("*.ndjson"))
    if not bundle_files:
        raise ApiError(f"no dashboard NDJSON bundles in {directory}")
    for path in bundle_files:
        import_ndjson_file(client, path)


def cleanup_deprecated_saved_objects(client: JsonClient) -> None:
    for object_type, object_id in dashboard_definitions.DEPRECATED_SAVED_OBJECTS:
        client.request(
            f"api/saved_objects/{quote(object_type)}/{quote(object_id)}",
            method="DELETE",
            allowed=(404,),
        )


def verify_dashboards(client: JsonClient) -> None:
    for dashboard_id in dashboard_definitions.DASHBOARD_BUNDLES:
        client.request(f"api/saved_objects/dashboard/{quote(dashboard_id)}")


def compact(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"))


def fetch_index_fields(
    client: JsonClient,
    pattern: str,
    *,
    popular_fields: list[str] | None = None,
) -> str:
    """Return index-pattern `fields` JSON string from a live wildcard lookup."""
    query = urlencode(
        {
            "pattern": pattern,
            "meta_fields": ["_source", "_id", "_type", "_index", "_score"],
        },
        doseq=True,
    )
    _, response = client.request(f"api/index_patterns/_fields_for_wildcard?{query}")
    # Higher count surfaces fields under Discover's "Popular" sidebar group.
    popularity = {
        name: max(50, 200 - (index * 10))
        for index, name in enumerate(popular_fields or [])
    }
    specs: list[dict[str, Any]] = []
    for field in response.get("fields", []):
        name = field["name"]
        specs.append(
            {
                "count": popularity.get(name, 0),
                "name": name,
                "type": field["type"],
                "esTypes": field.get("esTypes", [field["type"]]),
                "scripted": False,
                "searchable": field.get("searchable", True),
                "aggregatable": field.get("aggregatable", False),
                "readFromDocValues": field.get("aggregatable", False),
            }
        )
    return compact(specs)


def upsert_index_pattern(
    client: JsonClient,
    pattern_id: str,
    title: str,
    time_field: str,
    *,
    popular_fields: list[str] | None = None,
) -> None:
    """Register an index pattern with field mappings so Dashboards UI can use it."""
    client.request(
        f"api/saved_objects/index-pattern/{quote(pattern_id)}?overwrite=true",
        method="POST",
        payload={
            "attributes": {
                "title": title,
                "timeFieldName": time_field,
                "fields": fetch_index_fields(
                    client, title, popular_fields=popular_fields
                ),
            }
        },
    )


def reconcile_index_patterns(client: JsonClient) -> None:
    for pattern_id, title, time_field, popular_fields in (
        ("shared-observability-metrics", METRICS_PATTERN, "time", None),
        (
            "shared-observability-logs",
            LOGS_PATTERN,
            LOGS_TIME_FIELD,
            list(dashboard_definitions.LOG_SIDEBAR_FILTER_FIELDS),
        ),
        ("shared-observability-traces", TRACES_PATTERN, "startTime", None),
    ):
        upsert_index_pattern(
            client,
            pattern_id,
            title,
            time_field,
            popular_fields=popular_fields,
        )


def reconcile_ui_settings(client: JsonClient) -> None:
    """Point Discover/home defaults at the logs index pattern (field sidebar UX)."""
    client.request(
        "api/opensearch-dashboards/settings",
        method="POST",
        payload={"changes": {"defaultIndex": "shared-observability-logs"}},
    )


def verify(opensearch: JsonClient, dashboards: JsonClient, retention_days: int) -> None:
    for policy_id in (
        "observability-metrics-retention",
        "observability-logs-retention",
        "raw-span-policy",
    ):
        _, policy = opensearch.request(f"_plugins/_ism/policies/{policy_id}")
        transitions = policy["policy"]["states"][0]["transitions"]
        age = transitions[0]["conditions"]["min_index_age"]
        if age != f"{retention_days}d":
            raise ApiError(f"{policy_id} has unexpected retention {age}")
    monitor_names = set(existing_monitors(opensearch))
    expected_monitors = {monitor["name"] for monitor in desired_monitors()}
    if not expected_monitors.issubset(monitor_names):
        raise ApiError(f"missing monitors: {sorted(expected_monitors - monitor_names)}")
    verify_dashboards(dashboards)



def main() -> int:
    retention_days = int(os.environ.get("OBSERVABILITY_RETENTION_DAYS", "7"))
    if not 1 <= retention_days <= 90:
        raise ValueError("OBSERVABILITY_RETENTION_DAYS must be between 1 and 90")
    opensearch = JsonClient(os.environ["OPENSEARCH_URL"])
    dashboards = JsonClient(os.environ["DASHBOARDS_URL"], dashboards=True)
    wait_ready(opensearch, "", "OpenSearch")
    wait_ready(dashboards, "api/status", "OpenSearch Dashboards")

    upsert_policy(
        opensearch,
        "observability-metrics-retention",
        retention_days,
        ["otel-v1-apm-metrics", "otel-v1-apm-metrics-*"],
    )
    upsert_policy(
        opensearch,
        "observability-logs-retention",
        retention_days,
        ["otel-v1-apm-logs", "otel-v1-apm-logs-*"],
    )
    upsert_policy_payload(
        opensearch,
        "raw-span-policy",
        trace_lifecycle_policy(retention_days),
    )
    opensearch.request(
        "_index_template/observability-metrics",
        method="PUT",
        payload=index_template("otel-v1-apm-metrics-*", "time"),
    )
    opensearch.request(
        "_index_template/observability-logs",
        method="PUT",
        payload=logs_index_template("otel-v1-apm-logs-*"),
    )
    reconcile_matching_indices(
        opensearch,
        METRICS_PATTERN,
        "observability-metrics-retention",
        "time",
    )
    reconcile_matching_indices(
        opensearch,
        LOGS_PATTERN,
        "observability-logs-retention",
        LOGS_TIME_FIELD,
    )
    reconcile_trace_storage(opensearch)
    upsert_monitors(opensearch)
    reconcile_index_patterns(dashboards)
    reconcile_ui_settings(dashboards)
    cleanup_deprecated_saved_objects(dashboards)
    import_dashboard_bundles(dashboards, DASHBOARDS_DIR)
    verify(opensearch, dashboards, retention_days)
    print(
        "observability provisioning passed: "
        f"retention={retention_days}d monitors={len(desired_monitors())} "
        f"dashboard_bundles={len(dashboard_definitions.DASHBOARD_BUNDLES)} "
        f"saved_objects={len(dashboard_definitions.all_dashboard_objects())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
