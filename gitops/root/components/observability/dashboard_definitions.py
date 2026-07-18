"""GitOps dashboard bundles for OpenSearch Dashboards (NDJSON source)."""

from __future__ import annotations

from typing import Any

MANAGED_BY = "shared-gitops-k8s-cluster"

LOGS_VIEW = "shared-observability-logs"

# Discover-style column layout: time + service context + message body.
LOG_STREAM_COLUMNS = [
    "observedTime",
    "serviceName",
    "severityText",
    "traceId",
    "body",
]


def compact(value: Any) -> str:
    import json

    return json.dumps(value, separators=(",", ":"))


def search_source(index_reference: str, query: str = "") -> dict[str, Any]:
    return {
        "query": {"query": query, "language": "lucene"},
        "filter": [],
        "indexRefName": index_reference,
    }


def log_histogram_visualization(
    *,
    title: str,
    data_view: str,
    time_field: str,
    query: str = "",
) -> dict[str, Any]:
    source_ref = "kibanaSavedObjectMeta.searchSourceJSON.index"
    vis_state = {
        "title": title,
        "type": "histogram",
        "params": {
            "type": "histogram",
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
                    "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                    "title": {"text": "Count"},
                }
            ],
            "seriesParams": [
                {
                    "show": True,
                    "type": "histogram",
                    "mode": "stacked",
                    "data": {"label": "Count", "id": "1"},
                    "valueAxis": "ValueAxis-1",
                    "drawLinesBetweenPoints": True,
                    "showCircles": True,
                }
            ],
            "addTooltip": True,
            "addLegend": False,
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
    time_from: str = "now-15m",
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
                        {
                            "query": {"query": "", "language": "lucene"},
                            "filter": [],
                        }
                    )
                },
            },
            "references": references,
        },
    )


def _logs_explore_bundle() -> list[tuple[str, str, dict[str, Any]]]:
    """Single Discover-style log view: histogram + document stream."""
    objects: list[tuple[str, str, dict[str, Any]]] = [
        (
            "visualization",
            "logs-explore-histogram",
            log_histogram_visualization(
                title="Log volume",
                data_view=LOGS_VIEW,
                time_field="observedTime",
            ),
        ),
        (
            "search",
            "logs-explore-stream",
            saved_search(
                title="Logs",
                data_view=LOGS_VIEW,
                time_field="observedTime",
                columns=LOG_STREAM_COLUMNS,
                query="",
            ),
        ),
    ]
    objects.append(
        assemble_dashboard(
            dashboard_id="logs-explore",
            title="Logs",
            description=(
                "Unified log exploration (Discover-style). Use the search bar and "
                f"Add filter controls above; Lucene queries match alert monitors. "
                f"Managed by {MANAGED_BY}"
            ),
            panels=[
                ("visualization", "logs-explore-histogram", 0, 0, 48, 12),
                ("search", "logs-explore-stream", 0, 12, 48, 30),
            ],
            panel_ref_prefix="logs_explore",
            time_from="now-15m",
            refresh_ms=30000,
        )
    )
    return objects


DASHBOARD_BUNDLES: dict[str, list[tuple[str, str, dict[str, Any]]]] = {
    "logs-explore": _logs_explore_bundle(),
}

DEPRECATED_SAVED_OBJECTS: list[tuple[str, str]] = [
    ("dashboard", "shared-observability-overview"),
    ("dashboard", "shared-postgres-connections"),
    ("dashboard", "shared-data-platform"),
    ("dashboard", "shared-apm-correlation"),
    ("dashboard", "platform-postgres-connections"),
    ("dashboard", "platform-data-namespace"),
    ("dashboard", "platform-apm-correlation"),
    ("dashboard", "platform-logs-explore"),
    ("dashboard", "loadlinker-logs-explore"),
    ("dashboard", "loadlinker-health"),
    ("dashboard", "loadlinker-bff-edge"),
    ("dashboard", "loadlinker-sesame-auth"),
    ("dashboard", "sesame-logs-explore"),
    ("dashboard", "sesame-platform-health"),
    ("dashboard", "sesame-auth-critical-path"),
    ("visualization", "shared-metrics-by-service"),
    ("visualization", "shared-logs-by-service"),
    ("search", "shared-error-logs"),
    ("search", "rerp-api-metrics"),
    ("visualization", "postgres-connections-by-database"),
    ("visualization", "loadlinker-p0-error-logs"),
    ("search", "loadlinker-p0-errors"),
    ("visualization", "loadlinker-bff-error-logs"),
    ("search", "loadlinker-bff-errors"),
    ("visualization", "loadlinker-sesame-auth-errors"),
    ("search", "loadlinker-bff-sesame-auth-logs"),
    ("visualization", "sesame-error-logs"),
    ("visualization", "sesame-auth-error-logs"),
    ("search", "sesame-auth-db-pressure"),
    ("search", "correlation-logs-by-trace"),
    ("search", "correlation-errors-with-trace"),
    ("search", "correlation-db-pressure-logs"),
    ("search", "correlation-http-spans"),
    ("search", "correlation-postgres-at-time"),
    ("search", "data-platform-metrics-snapshot"),
    ("search", "loadlinker-bff-slow-spans"),
    ("search", "loadlinker-p0-http-snapshot"),
    ("search", "loadlinker-sesame-auth-spans"),
    ("search", "loadlinker_logs_explore-db-pressure"),
    ("search", "loadlinker_logs_explore-recent-errors"),
    ("search", "loadlinker_logs_explore-trace-logs"),
    ("search", "loadlinker_logs_explore-warn-logs"),
    ("search", "platform_logs_explore-db-pressure"),
    ("search", "platform_logs_explore-recent-errors"),
    ("search", "platform_logs_explore-trace-logs"),
    ("search", "platform_logs_explore-warn-logs"),
    ("search", "postgres-max-connections"),
    ("search", "sesame-auth-spans-snapshot"),
    ("search", "sesame-service-snapshot"),
    ("search", "sesame_logs_explore-db-pressure"),
    ("search", "sesame_logs_explore-recent-errors"),
    ("search", "sesame_logs_explore-trace-logs"),
    ("search", "sesame_logs_explore-warn-logs"),
    ("visualization", "correlation-logs-link"),
    ("visualization", "correlation-logs-with-trace-by-service"),
    ("visualization", "correlation-spans-by-service"),
    ("visualization", "data-redis-connected-clients"),
    ("visualization", "data-redis-memory-used"),
    ("visualization", "loadlinker-bff-auth-spans"),
    ("visualization", "loadlinker-bff-logs-link"),
    ("visualization", "loadlinker-bff-request-rate"),
    ("visualization", "loadlinker-health-logs-link"),
    ("visualization", "loadlinker-p0-http-spans"),
    ("visualization", "loadlinker-p1-http-spans"),
    ("visualization", "loadlinker-postgres-pressure"),
    ("visualization", "loadlinker-sesame-auth-logs-link"),
    ("visualization", "loadlinker-slo-notes"),
    ("visualization", "loadlinker_logs_explore-errors-by-service"),
    ("visualization", "loadlinker_logs_explore-guide"),
    ("visualization", "loadlinker_logs_explore-volume-by-severity"),
    ("visualization", "pgpool-frontend-connections"),
    ("visualization", "platform_logs_explore-errors-by-service"),
    ("visualization", "platform_logs_explore-guide"),
    ("visualization", "platform_logs_explore-volume-by-severity"),
    ("visualization", "postgres-connections-by-namespace"),
    ("visualization", "postgres-loadlinker-connections"),
    ("visualization", "postgres-sesame-connections"),
    ("visualization", "sesame-auth-hot-spans"),
    ("visualization", "sesame-auth-logs-link"),
    ("visualization", "sesame-auth-slo-notes"),
    ("visualization", "sesame-http-spans"),
    ("visualization", "sesame-platform-logs-link"),
    ("visualization", "sesame-postgres-pressure"),
    ("visualization", "sesame_logs_explore-errors-by-service"),
    ("visualization", "sesame_logs_explore-guide"),
    ("visualization", "sesame_logs_explore-volume-by-severity"),
]


def all_dashboard_objects() -> list[tuple[str, str, dict[str, Any]]]:
    """Return deduplicated saved objects across all bundles."""
    merged: dict[tuple[str, str], tuple[str, str, dict[str, Any]]] = {}
    for objects in DASHBOARD_BUNDLES.values():
        for object_type, object_id, payload in objects:
            merged[(object_type, object_id)] = (object_type, object_id, payload)
    return list(merged.values())


def export_line(object_type: str, object_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    line = {"type": object_type, "id": object_id}
    line.update(payload)
    return line
