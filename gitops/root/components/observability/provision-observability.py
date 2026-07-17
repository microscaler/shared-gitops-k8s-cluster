#!/usr/bin/env python3
"""Reconcile OpenSearch-native retention, dashboards, and alert monitors."""

from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


METRICS_PATTERN = "otel-v1-apm-metrics*"
LOGS_PATTERN = "otel-v1-apm-logs*"
TRACES_PATTERN = "otel-v1-apm-span-*"
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
    if time_field not in properties:
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
                    {"range": {"observedTime": {"gte": "now-5m", "lte": "now"}}},
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


def compact(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"))


def fetch_index_fields(client: JsonClient, pattern: str) -> str:
    """Return index-pattern `fields` JSON string from a live wildcard lookup."""
    query = urlencode(
        {
            "pattern": pattern,
            "meta_fields": ["_source", "_id", "_type", "_index", "_score"],
        },
        doseq=True,
    )
    _, response = client.request(f"api/index_patterns/_fields_for_wildcard?{query}")
    specs: list[dict[str, Any]] = []
    for field in response.get("fields", []):
        specs.append(
            {
                "count": 0,
                "name": field["name"],
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
    client: JsonClient, pattern_id: str, title: str, time_field: str
) -> None:
    """Register an index pattern with field mappings so Dashboards UI can use it."""
    client.request(
        f"api/saved_objects/index-pattern/{quote(pattern_id)}?overwrite=true",
        method="POST",
        payload={
            "attributes": {
                "title": title,
                "timeFieldName": time_field,
                "fields": fetch_index_fields(client, title),
            }
        },
    )


def reconcile_index_patterns(client: JsonClient) -> None:
    for pattern_id, title, time_field in (
        ("shared-observability-metrics", METRICS_PATTERN, "time"),
        ("shared-observability-logs", LOGS_PATTERN, "observedTime"),
        ("shared-observability-traces", TRACES_PATTERN, "startTime"),
    ):
        upsert_index_pattern(client, pattern_id, title, time_field)


def search_source(index_reference: str, query: str = "") -> dict[str, Any]:
    return {
        "query": {"query": query, "language": "kuery"},
        "filter": [],
        "indexRefName": index_reference,
    }


def line_visualization(
    *, title: str, data_view: str, time_field: str, group_field: str, query: str = ""
) -> dict[str, Any]:
    source_ref = "kibanaSavedObjectMeta.searchSourceJSON.index"
    vis_state = {
        "title": title,
        "type": "line",
        "params": {
            "type": "line",
            "grid": {"categoryLines": False},
            "categoryAxes": [
                {
                    "id": "CategoryAxis-1",
                    "type": "category",
                    "position": "bottom",
                    "show": True,
                    "style": {},
                    "scale": {"type": "linear"},
                    "labels": {"show": True, "truncate": 100},
                    "title": {},
                }
            ],
            "valueAxes": [
                {
                    "id": "ValueAxis-1",
                    "name": "LeftAxis-1",
                    "type": "value",
                    "position": "left",
                    "show": True,
                    "style": {},
                    "scale": {"type": "linear", "mode": "normal"},
                    "labels": {"show": True, "rotate": 0, "filter": False},
                    "title": {"text": "Documents"},
                }
            ],
            "seriesParams": [
                {
                    "show": "true",
                    "type": "line",
                    "mode": "normal",
                    "data": {"label": "Count", "id": "1"},
                    "valueAxis": "ValueAxis-1",
                    "drawLinesBetweenPoints": True,
                    "showCircles": True,
                }
            ],
            "addTooltip": True,
            "addLegend": True,
            "legendPosition": "right",
            "times": [],
            "addTimeMarker": False,
        },
        "aggs": [
            {
                "id": "1",
                "enabled": True,
                "type": "count",
                "schema": "metric",
                "params": {},
            },
            {
                "id": "2",
                "enabled": True,
                "type": "date_histogram",
                "schema": "segment",
                "params": {
                    "field": time_field,
                    "interval": "auto",
                    "min_doc_count": 1,
                    "extended_bounds": {},
                },
            },
            {
                "id": "3",
                "enabled": True,
                "type": "terms",
                "schema": "group",
                "params": {
                    "field": group_field,
                    "size": 12,
                    "order": "desc",
                    "orderBy": "1",
                    "otherBucket": False,
                    "missingBucket": False,
                },
            },
        ],
    }
    return {
        "attributes": {
            "title": title,
            "description": f"Managed by {MANAGED_BY}",
            "visState": compact(vis_state),
            "uiStateJSON": "{}",
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": compact(search_source(source_ref, query))
            },
        },
        "references": [{"name": source_ref, "type": "index-pattern", "id": data_view}],
    }


def metric_sum_line_visualization(
    *,
    title: str,
    data_view: str,
    time_field: str,
    group_field: str,
    value_field: str = "value",
    query: str = "",
) -> dict[str, Any]:
    source_ref = "kibanaSavedObjectMeta.searchSourceJSON.index"
    vis_state = {
        "title": title,
        "type": "line",
        "params": {
            "type": "line",
            "grid": {"categoryLines": False},
            "categoryAxes": [
                {
                    "id": "CategoryAxis-1",
                    "type": "category",
                    "position": "bottom",
                    "show": True,
                    "style": {},
                    "scale": {"type": "linear"},
                    "labels": {"show": True, "truncate": 100},
                    "title": {},
                }
            ],
            "valueAxes": [
                {
                    "id": "ValueAxis-1",
                    "name": "LeftAxis-1",
                    "type": "value",
                    "position": "left",
                    "show": True,
                    "style": {},
                    "scale": {"type": "linear", "mode": "normal"},
                    "labels": {"show": True, "rotate": 0, "filter": False},
                    "title": {"text": "Connections"},
                }
            ],
            "seriesParams": [
                {
                    "show": "true",
                    "type": "line",
                    "mode": "normal",
                    "data": {"label": "Sum", "id": "1"},
                    "valueAxis": "ValueAxis-1",
                    "drawLinesBetweenPoints": True,
                    "showCircles": True,
                }
            ],
            "addTooltip": True,
            "addLegend": True,
            "legendPosition": "right",
            "times": [],
            "addTimeMarker": False,
        },
        "aggs": [
            {
                "id": "1",
                "enabled": True,
                "type": "sum",
                "schema": "metric",
                "params": {"field": value_field},
            },
            {
                "id": "2",
                "enabled": True,
                "type": "date_histogram",
                "schema": "segment",
                "params": {
                    "field": time_field,
                    "interval": "auto",
                    "min_doc_count": 1,
                    "extended_bounds": {},
                },
            },
            {
                "id": "3",
                "enabled": True,
                "type": "terms",
                "schema": "group",
                "params": {
                    "field": group_field,
                    "size": 12,
                    "order": "desc",
                    "orderBy": "1",
                    "otherBucket": False,
                    "missingBucket": False,
                },
            },
        ],
    }
    return {
        "attributes": {
            "title": title,
            "description": f"Managed by {MANAGED_BY}",
            "visState": compact(vis_state),
            "uiStateJSON": "{}",
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": compact(search_source(source_ref, query))
            },
        },
        "references": [{"name": source_ref, "type": "index-pattern", "id": data_view}],
    }


def metric_sum_table_visualization(
    *,
    title: str,
    data_view: str,
    group_fields: list[str],
    value_field: str = "value",
    query: str = "",
) -> dict[str, Any]:
    source_ref = "kibanaSavedObjectMeta.searchSourceJSON.index"
    aggs: list[dict[str, Any]] = [
        {
            "id": "1",
            "enabled": True,
            "type": "sum",
            "schema": "metric",
            "params": {"field": value_field},
        }
    ]
    for index, field in enumerate(group_fields, start=2):
        aggs.append(
            {
                "id": str(index),
                "enabled": True,
                "type": "terms",
                "schema": "bucket",
                "params": {
                    "field": field,
                    "size": 20,
                    "order": "desc",
                    "orderBy": "1",
                    "otherBucket": False,
                    "missingBucket": False,
                },
            }
        )
    vis_state = {
        "title": title,
        "type": "table",
        "params": {
            "perPage": 10,
            "showPartialRows": False,
            "showMetricsAtAllLevels": False,
            "sort": {"columnIndex": None, "direction": None},
            "showTotal": False,
            "totalFunc": "sum",
        },
        "aggs": aggs,
    }
    return {
        "attributes": {
            "title": title,
            "description": f"Managed by {MANAGED_BY}",
            "visState": compact(vis_state),
            "uiStateJSON": "{}",
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": compact(search_source(source_ref, query))
            },
        },
        "references": [{"name": source_ref, "type": "index-pattern", "id": data_view}],
    }


def assemble_dashboard(
    *,
    dashboard_id: str,
    title: str,
    description: str,
    panels: list[tuple[str, str, int, int, int, int]],
    panel_ref_prefix: str,
    time_from: str = "now-6h",
    refresh_ms: int = 30000,
) -> tuple[str, str, dict[str, Any]]:
    panel_json: list[dict[str, Any]] = []
    references: list[dict[str, str]] = []
    for position, (object_type, object_id, x, y, width, height) in enumerate(panels):
        panel_ref = f"{panel_ref_prefix}_{position}"
        panel_json.append(
            {
                "version": "2.19.6",
                "type": object_type,
                "gridData": {
                    "x": x,
                    "y": y,
                    "w": width,
                    "h": height,
                    "i": str(position + 1),
                },
                "panelIndex": str(position + 1),
                "embeddableConfig": {},
                "panelRefName": panel_ref,
            }
        )
        references.append({"name": panel_ref, "type": object_type, "id": object_id})
    return (
        "dashboard",
        dashboard_id,
        {
            "attributes": {
                "title": title,
                "description": description,
                "panelsJSON": compact(panel_json),
                "optionsJSON": compact(
                    {
                        "useMargins": True,
                        "syncColors": False,
                        "syncCursor": True,
                        "syncTooltips": False,
                        "hidePanelTitles": False,
                    }
                ),
                "version": 1,
                "timeRestore": True,
                "timeFrom": time_from,
                "timeTo": "now",
                "refreshInterval": {"pause": False, "value": refresh_ms},
                "kibanaSavedObjectMeta": {
                    "searchSourceJSON": compact(
                        {"query": {"query": "", "language": "kuery"}, "filter": []}
                    )
                },
            },
            "references": references,
        },
    )


def saved_search(
    *, title: str, data_view: str, time_field: str, columns: list[str], query: str
) -> dict[str, Any]:
    source_ref = "kibanaSavedObjectMeta.searchSourceJSON.index"
    return {
        "attributes": {
            "title": title,
            "description": f"Managed by {MANAGED_BY}",
            "columns": columns,
            "sort": [[time_field, "desc"]],
            "hideChart": False,
            "isTextBasedQuery": False,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": compact(search_source(source_ref, query))
            },
        },
        "references": [{"name": source_ref, "type": "index-pattern", "id": data_view}],
    }


def dashboard_objects() -> list[tuple[str, str, dict[str, Any]]]:
    metrics_view = "shared-observability-metrics"
    logs_view = "shared-observability-logs"
    traces_view = "shared-observability-traces"
    objects: list[tuple[str, str, dict[str, Any]]] = [
        (
            "visualization",
            "shared-metrics-by-service",
            line_visualization(
                title="Metric samples by service",
                data_view=metrics_view,
                time_field="time",
                group_field="serviceName.keyword",
            ),
        ),
        (
            "visualization",
            "shared-logs-by-service",
            line_visualization(
                title="Stored logs by service",
                data_view=logs_view,
                time_field="observedTime",
                group_field="serviceName.keyword",
            ),
        ),
        (
            "search",
            "shared-error-logs",
            saved_search(
                title="Recent error logs",
                data_view=logs_view,
                time_field="observedTime",
                columns=[
                    "observedTime",
                    "serviceName",
                    "severityText",
                    "traceId",
                    "spanId",
                    "body",
                ],
                query='severityText: ("ERROR" or "FATAL")',
            ),
        ),
        (
            "search",
            "rerp-api-metrics",
            saved_search(
                title="RERP API metrics",
                data_view=metrics_view,
                time_field="time",
                columns=["time", "serviceName", "name", "value", "sum", "count"],
                query='serviceName: "api"',
            ),
        ),
    ]
    panels = [
        ("visualization", "shared-metrics-by-service", 0, 0, 24, 12),
        ("visualization", "shared-logs-by-service", 24, 0, 24, 12),
        ("search", "shared-error-logs", 0, 12, 24, 14),
        ("search", "rerp-api-metrics", 24, 12, 24, 14),
    ]
    panel_json = []
    references = []
    for position, (object_type, object_id, x, y, width, height) in enumerate(panels):
        panel_ref = f"panel_{position}"
        panel_json.append(
            {
                "version": "2.19.6",
                "type": object_type,
                "gridData": {
                    "x": x,
                    "y": y,
                    "w": width,
                    "h": height,
                    "i": str(position + 1),
                },
                "panelIndex": str(position + 1),
                "embeddableConfig": {},
                "panelRefName": panel_ref,
            }
        )
        references.append({"name": panel_ref, "type": object_type, "id": object_id})
    objects.append(
        (
            "dashboard",
            "shared-observability-overview",
            {
                "attributes": {
                    "title": "Shared observability overview",
                    "description": (
                        "Metrics and retained operational logs managed by " + MANAGED_BY
                    ),
                    "panelsJSON": compact(panel_json),
                    "optionsJSON": compact(
                        {
                            "useMargins": True,
                            "syncColors": False,
                            "syncCursor": True,
                            "syncTooltips": False,
                            "hidePanelTitles": False,
                        }
                    ),
                    "version": 1,
                    "timeRestore": True,
                    "timeFrom": "now-24h",
                    "timeTo": "now",
                    "refreshInterval": {"pause": False, "value": 60000},
                    "kibanaSavedObjectMeta": {
                        "searchSourceJSON": compact(
                            {"query": {"query": "", "language": "kuery"}, "filter": []}
                        )
                    },
                },
                "references": references,
            },
        )
    )
    objects.extend(postgres_dashboard_objects(metrics_view))
    objects.extend(data_platform_dashboard_objects(metrics_view))
    objects.extend(correlation_dashboard_objects(metrics_view, logs_view, traces_view))
    return objects


def postgres_dashboard_objects(metrics_view: str) -> list[tuple[str, str, dict[str, Any]]]:
    """Postgres/Pgpool connection dashboards (consumer_namespace = K8s namespace)."""
    objects: list[tuple[str, str, dict[str, Any]]] = [
        (
            "visualization",
            "postgres-connections-by-namespace",
            metric_sum_line_visualization(
                title="Postgres connections by namespace",
                data_view=metrics_view,
                time_field="time",
                group_field="metric.attributes.consumer_namespace.keyword",
                query=POSTGRES_ACTIVITY_QUERY,
            ),
        ),
        (
            "visualization",
            "postgres-connections-by-database",
            metric_sum_table_visualization(
                title="Postgres connections by database and user",
                data_view=metrics_view,
                group_fields=[
                    "metric.attributes.consumer_namespace.keyword",
                    "metric.attributes.datname.keyword",
                    "metric.attributes.usename.keyword",
                ],
                query=POSTGRES_ACTIVITY_QUERY,
            ),
        ),
        (
            "visualization",
            "pgpool-frontend-connections",
            metric_sum_line_visualization(
                title="Pgpool frontend connections (used vs capacity)",
                data_view=metrics_view,
                time_field="time",
                group_field="name.keyword",
                query=PGPOOL_FRONTEND_QUERY,
            ),
        ),
        (
            "search",
            "postgres-max-connections",
            saved_search(
                title="Postgres max_connections setting",
                data_view=metrics_view,
                time_field="time",
                columns=["time", "name", "value", "metric.attributes.server"],
                query='name: "pg_settings_max_connections"',
            ),
        ),
    ]
    panels = [
        ("visualization", "postgres-connections-by-namespace", 0, 0, 36, 14),
        ("visualization", "pgpool-frontend-connections", 36, 0, 12, 14),
        ("visualization", "postgres-connections-by-database", 0, 14, 36, 16),
        ("search", "postgres-max-connections", 36, 14, 12, 16),
    ]
    panel_json = []
    references = []
    for position, (object_type, object_id, x, y, width, height) in enumerate(panels):
        panel_ref = f"postgres_panel_{position}"
        panel_json.append(
            {
                "version": "2.19.6",
                "type": object_type,
                "gridData": {
                    "x": x,
                    "y": y,
                    "w": width,
                    "h": height,
                    "i": str(position + 1),
                },
                "panelIndex": str(position + 1),
                "embeddableConfig": {},
                "panelRefName": panel_ref,
            }
        )
        references.append({"name": panel_ref, "type": object_type, "id": object_id})
    objects.append(
        (
            "dashboard",
            "shared-postgres-connections",
            {
                "attributes": {
                    "title": "Postgres & Pgpool connections",
                    "description": (
                        "Database consumer pressure by Kubernetes namespace "
                        f"(datname → consumer_namespace mapping). Managed by {MANAGED_BY}"
                    ),
                    "panelsJSON": compact(panel_json),
                    "optionsJSON": compact(
                        {
                            "useMargins": True,
                            "syncColors": False,
                            "syncCursor": True,
                            "syncTooltips": False,
                            "hidePanelTitles": False,
                        }
                    ),
                    "version": 1,
                    "timeRestore": True,
                    "timeFrom": "now-6h",
                    "timeTo": "now",
                    "refreshInterval": {"pause": False, "value": 30000},
                    "kibanaSavedObjectMeta": {
                        "searchSourceJSON": compact(
                            {"query": {"query": "", "language": "kuery"}, "filter": []}
                        )
                    },
                },
                "references": references,
            },
        )
    )
    return objects


def data_platform_dashboard_objects(
    metrics_view: str,
) -> list[tuple[str, str, dict[str, Any]]]:
    """Data namespace health: Postgres, Pgpool, Redis."""
    objects: list[tuple[str, str, dict[str, Any]]] = [
        (
            "visualization",
            "data-redis-connected-clients",
            metric_sum_line_visualization(
                title="Redis connected clients",
                data_view=metrics_view,
                time_field="time",
                group_field="name.keyword",
                query=REDIS_CLIENTS_QUERY,
            ),
        ),
        (
            "visualization",
            "data-redis-memory-used",
            metric_sum_line_visualization(
                title="Redis memory used (bytes)",
                data_view=metrics_view,
                time_field="time",
                group_field="name.keyword",
                query=REDIS_MEMORY_QUERY,
            ),
        ),
        (
            "search",
            "data-platform-metrics-snapshot",
            saved_search(
                title="Data namespace metrics snapshot",
                data_view=metrics_view,
                time_field="time",
                columns=[
                    "time",
                    "name",
                    "value",
                    "metric.attributes.consumer_namespace",
                    "metric.attributes.datname",
                ],
                query=DATA_PLATFORM_METRICS_QUERY,
            ),
        ),
    ]
    objects.append(
        assemble_dashboard(
            dashboard_id="shared-data-platform",
            title="Data namespace platform",
            description=(
                "Postgres HA, Pgpool, and Redis metrics from the data namespace. "
                f"Managed by {MANAGED_BY}"
            ),
            panels=[
                ("visualization", "postgres-connections-by-namespace", 0, 0, 24, 12),
                ("visualization", "pgpool-frontend-connections", 24, 0, 24, 12),
                ("visualization", "data-redis-connected-clients", 0, 12, 24, 12),
                ("visualization", "data-redis-memory-used", 24, 12, 24, 12),
                ("search", "data-platform-metrics-snapshot", 0, 24, 48, 14),
            ],
            panel_ref_prefix="data_platform",
            time_from="now-6h",
        )
    )
    return objects


def correlation_dashboard_objects(
    metrics_view: str,
    logs_view: str,
    traces_view: str,
) -> list[tuple[str, str, dict[str, Any]]]:
    """Cross-system APM ↔ logs ↔ database correlation."""
    objects: list[tuple[str, str, dict[str, Any]]] = [
        (
            "visualization",
            "correlation-spans-by-service",
            line_visualization(
                title="Trace spans by service",
                data_view=traces_view,
                time_field="startTime",
                group_field="serviceName.keyword",
            ),
        ),
        (
            "visualization",
            "correlation-logs-with-trace-by-service",
            line_visualization(
                title="Correlated logs by service (traceId present)",
                data_view=logs_view,
                time_field="observedTime",
                group_field="serviceName.keyword",
                query=CORRELATED_LOGS_QUERY,
            ),
        ),
        (
            "search",
            "correlation-http-spans",
            saved_search(
                title="HTTP request spans",
                data_view=traces_view,
                time_field="startTime",
                columns=[
                    "startTime",
                    "serviceName",
                    "name",
                    "traceId",
                    "spanId",
                    "durationInNanos",
                    "span.attributes.path",
                    "span.attributes.method",
                ],
                query=HTTP_SPANS_QUERY,
            ),
        ),
        (
            "search",
            "correlation-logs-by-trace",
            saved_search(
                title="Logs with trace context",
                data_view=logs_view,
                time_field="observedTime",
                columns=[
                    "observedTime",
                    "serviceName",
                    "severityText",
                    "traceId",
                    "spanId",
                    "body",
                ],
                query=CORRELATED_LOGS_QUERY,
            ),
        ),
        (
            "search",
            "correlation-errors-with-trace",
            saved_search(
                title="Errors with trace context",
                data_view=logs_view,
                time_field="observedTime",
                columns=[
                    "observedTime",
                    "serviceName",
                    "severityText",
                    "traceId",
                    "spanId",
                    "body",
                ],
                query=ERROR_LOGS_WITH_TRACE_QUERY,
            ),
        ),
        (
            "search",
            "correlation-db-pressure-logs",
            saved_search(
                title="Database / pool pressure logs",
                data_view=logs_view,
                time_field="observedTime",
                columns=[
                    "observedTime",
                    "serviceName",
                    "severityText",
                    "traceId",
                    "body",
                ],
                query=DB_PRESSURE_LOGS_QUERY,
            ),
        ),
        (
            "search",
            "correlation-postgres-at-time",
            saved_search(
                title="Postgres connections (align time with logs/traces)",
                data_view=metrics_view,
                time_field="time",
                columns=[
                    "time",
                    "name",
                    "value",
                    "metric.attributes.consumer_namespace",
                    "metric.attributes.datname",
                    "metric.attributes.usename",
                ],
                query=POSTGRES_ACTIVITY_QUERY,
            ),
        ),
    ]
    objects.append(
        assemble_dashboard(
            dashboard_id="shared-apm-correlation",
            title="APM & log correlation",
            description=(
                "Correlate traces, application logs, and database pressure using "
                "traceId/spanId and aligned time windows. Filter Discover by traceId "
                f"to pivot across signals. Managed by {MANAGED_BY}"
            ),
            panels=[
                ("visualization", "correlation-spans-by-service", 0, 0, 24, 10),
                (
                    "visualization",
                    "correlation-logs-with-trace-by-service",
                    24,
                    0,
                    24,
                    10,
                ),
                ("search", "correlation-http-spans", 0, 10, 24, 14),
                ("search", "correlation-logs-by-trace", 24, 10, 24, 14),
                ("search", "correlation-errors-with-trace", 0, 24, 24, 12),
                ("search", "correlation-db-pressure-logs", 24, 24, 24, 12),
                ("search", "correlation-postgres-at-time", 0, 36, 48, 12),
            ],
            panel_ref_prefix="correlation",
            time_from="now-1h",
            refresh_ms=15000,
        )
    )
    return objects


def upsert_dashboards(client: JsonClient) -> None:
    for object_type, object_id, payload in dashboard_objects():
        client.request(
            f"api/saved_objects/{quote(object_type)}/{quote(object_id)}?overwrite=true",
            method="POST",
            payload=payload,
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
    dashboards.request("api/saved_objects/dashboard/shared-observability-overview")
    dashboards.request("api/saved_objects/dashboard/shared-postgres-connections")
    dashboards.request("api/saved_objects/dashboard/shared-data-platform")
    dashboards.request("api/saved_objects/dashboard/shared-apm-correlation")


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
        payload=index_template("otel-v1-apm-logs-*", "observedTime"),
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
        "observedTime",
    )
    reconcile_trace_storage(opensearch)
    upsert_monitors(opensearch)
    reconcile_index_patterns(dashboards)
    upsert_dashboards(dashboards)
    verify(opensearch, dashboards, retention_days)
    print(
        "observability provisioning passed: "
        f"retention={retention_days}d monitors={len(desired_monitors())} "
        f"saved_objects={len(dashboard_objects())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
