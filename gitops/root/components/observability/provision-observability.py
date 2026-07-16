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
MANAGED_BY = "shared-gitops-k8s-cluster"


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
        payload=lifecycle_policy(retention_days, patterns),
    )


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
    ]


def existing_monitors(client: JsonClient) -> dict[str, dict[str, Any]]:
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
    hits = response.get("hits", {}).get("hits", [])
    return {
        hit.get("_source", {}).get("monitor", {}).get("name"): hit
        for hit in hits
        if hit.get("_source", {}).get("monitor", {}).get("name")
    }


def upsert_monitors(client: JsonClient) -> None:
    current = existing_monitors(client)
    for monitor in desired_monitors():
        hit = current.get(monitor["name"])
        if hit is None:
            client.request(
                "_plugins/_alerting/monitors", method="POST", payload=monitor
            )
            current = existing_monitors(client)
            continue
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
            "grid": {},
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
    objects: list[tuple[str, str, dict[str, Any]]] = [
        (
            "index-pattern",
            metrics_view,
            {"attributes": {"title": METRICS_PATTERN, "timeFieldName": "time"}},
        ),
        (
            "index-pattern",
            logs_view,
            {"attributes": {"title": LOGS_PATTERN, "timeFieldName": "observedTime"}},
        ),
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
                columns=["observedTime", "serviceName", "severityText", "body"],
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
    attach_existing_index(
        opensearch,
        "otel-v1-apm-metrics",
        "observability-metrics-retention",
        "time",
    )
    attach_existing_index(
        opensearch,
        "otel-v1-apm-logs",
        "observability-logs-retention",
        "observedTime",
    )
    upsert_monitors(opensearch)
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
