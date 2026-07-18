"""GitOps dashboard bundles for OpenSearch Dashboards (NDJSON source)."""

from __future__ import annotations

from typing import Any

MANAGED_BY = "shared-gitops-k8s-cluster"

METRICS_VIEW = "shared-observability-metrics"
LOGS_VIEW = "shared-observability-logs"
TRACES_VIEW = "shared-observability-traces"

LOADLINKER_P0_QUERY = (
    "serviceName: (bff OR bidding OR consignments OR notifications)"
)
LOADLINKER_P1_QUERY = (
    "serviceName: (fleet OR customs OR company OR locations OR identity OR inbox)"
)
SESAME_SERVICES_QUERY = (
    "serviceName: (identity-login-service OR identity-session-service OR "
    "identity-user-mgmt-service OR authz-core OR api-keys OR org-mgmt)"
)
SESAME_AUTH_HOT_QUERY = (
    "serviceName: (identity-login-service OR identity-session-service OR authz-core)"
)

POSTGRES_ACTIVITY_QUERY = (
    'name: "pg_stat_activity_count" and '
    'metric.attributes.backend_type: "client backend" and '
    '(metric.attributes.state: "idle" or metric.attributes.state: "active")'
)
POSTGRES_LOADLINKER_QUERY = (
    "metric.attributes.consumer_namespace: loadlinker and " + POSTGRES_ACTIVITY_QUERY
)
POSTGRES_SESAME_QUERY = (
    "metric.attributes.consumer_namespace: sesame-idam and " + POSTGRES_ACTIVITY_QUERY
)
PGPOOL_FRONTEND_QUERY = 'name: "pgpool2_frontend_used" or name: "pgpool2_frontend_total"'
REDIS_CLIENTS_QUERY = 'name: "redis_connected_clients"'
REDIS_MEMORY_QUERY = 'name: "redis_memory_used_bytes"'
DATA_PLATFORM_METRICS_QUERY = (
    "name: pg_stat_activity_count or name: pgpool2_frontend_used or "
    "name: pgpool2_frontend_total or name: redis_connected_clients or "
    'name: "redis_memory_used_bytes"'
)

HTTP_SPANS_QUERY = 'name: "http_request"'
HTTP_SPANS_P0_QUERY = f"{HTTP_SPANS_QUERY} AND {LOADLINKER_P0_QUERY}"
HTTP_SPANS_BFF_QUERY = f'{HTTP_SPANS_QUERY} AND serviceName: "bff"'
HTTP_SPANS_SESAME_AUTH_QUERY = f"{HTTP_SPANS_QUERY} AND {SESAME_AUTH_HOT_QUERY}"

ERROR_LOGS_QUERY = 'severityText: ("ERROR" or "FATAL")'
ERROR_LOGS_P0_QUERY = f"{ERROR_LOGS_QUERY} AND {LOADLINKER_P0_QUERY}"
ERROR_LOGS_SESAME_QUERY = f"{ERROR_LOGS_QUERY} AND {SESAME_SERVICES_QUERY}"
ERROR_LOGS_WITH_TRACE_QUERY = (
    f'{ERROR_LOGS_QUERY} AND traceId: * AND NOT traceId: ""'
)
CORRELATED_LOGS_QUERY = 'traceId: * AND NOT traceId: ""'
DB_PRESSURE_LOGS_QUERY = (
    "body: (*connection* OR *pool* OR *postgres* OR *redis* OR *timeout* OR *Pgpool*)"
)
DB_PRESSURE_LOADLINKER_QUERY = f"{DB_PRESSURE_LOGS_QUERY} AND {LOADLINKER_P0_QUERY}"
DB_PRESSURE_SESAME_QUERY = f"{DB_PRESSURE_LOGS_QUERY} AND {SESAME_SERVICES_QUERY}"

BFF_SESAME_AUTH_LOGS_QUERY = (
    'serviceName: "bff" AND body: (*sesame* OR *identity* OR *auth* OR '
    '*401* OR *403* OR *jwt* OR *token*)'
)
AUTH_FAILURE_LOGS_QUERY = (
    f"({ERROR_LOGS_SESAME_QUERY}) OR ({BFF_SESAME_AUTH_LOGS_QUERY})"
)

# Initial SLO targets (dev); refine against measured baselines.
SLO_BFF_P95_MS = 500
SLO_AUTHZ_P95_MS = 50
SLO_BIDDING_P95_MS = 800


def compact(value: Any) -> str:
    import json

    return json.dumps(value, separators=(",", ":"))


def search_source(index_reference: str, query: str = "") -> dict[str, Any]:
    return {
        "query": {"query": query, "language": "kuery"},
        "filter": [],
        "indexRefName": index_reference,
    }


def line_visualization(
    *,
    title: str,
    data_view: str,
    time_field: str,
    group_field: str,
    query: str = "",
    y_title: str = "Documents",
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
                    "title": {"text": y_title},
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
    y_title: str = "Sum",
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
                    "title": {"text": y_title},
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


def markdown_visualization(*, title: str, markdown: str) -> dict[str, Any]:
    vis_state = {
        "title": title,
        "type": "markdown",
        "params": {"fontSize": 12, "openLinksInNewTab": False, "markdown": markdown},
        "aggs": [],
    }
    return {
        "attributes": {
            "title": title,
            "description": f"Managed by {MANAGED_BY}",
            "visState": compact(vis_state),
            "uiStateJSON": "{}",
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": compact(
                    {"query": {"query": "", "language": "kuery"}, "filter": []}
                )
            },
        },
        "references": [],
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


def _platform_postgres_bundle() -> list[tuple[str, str, dict[str, Any]]]:
    objects: list[tuple[str, str, dict[str, Any]]] = [
        (
            "visualization",
            "postgres-connections-by-namespace",
            metric_sum_line_visualization(
                title="Postgres connections by consumer namespace",
                data_view=METRICS_VIEW,
                time_field="time",
                group_field="metric.attributes.consumer_namespace.keyword",
                query=POSTGRES_ACTIVITY_QUERY,
                y_title="Connections",
            ),
        ),
        (
            "visualization",
            "postgres-loadlinker-connections",
            metric_sum_line_visualization(
                title="Loadlinker Postgres connections",
                data_view=METRICS_VIEW,
                time_field="time",
                group_field="metric.attributes.datname.keyword",
                query=POSTGRES_LOADLINKER_QUERY,
                y_title="Connections",
            ),
        ),
        (
            "visualization",
            "postgres-sesame-connections",
            metric_sum_line_visualization(
                title="Sesame-IDAM Postgres connections",
                data_view=METRICS_VIEW,
                time_field="time",
                group_field="metric.attributes.datname.keyword",
                query=POSTGRES_SESAME_QUERY,
                y_title="Connections",
            ),
        ),
        (
            "visualization",
            "pgpool-frontend-connections",
            metric_sum_line_visualization(
                title="Pgpool frontend connections (used vs capacity)",
                data_view=METRICS_VIEW,
                time_field="time",
                group_field="name.keyword",
                query=PGPOOL_FRONTEND_QUERY,
                y_title="Connections",
            ),
        ),
        (
            "search",
            "postgres-max-connections",
            saved_search(
                title="Postgres max_connections setting",
                data_view=METRICS_VIEW,
                time_field="time",
                columns=["time", "name", "value", "metric.attributes.server"],
                query='name: "pg_settings_max_connections"',
            ),
        ),
    ]
    objects.append(
        assemble_dashboard(
            dashboard_id="platform-postgres-connections",
            title="Platform — Postgres & Pgpool",
            description=(
                "Database saturation by consumer namespace (loadlinker, sesame-idam, "
                f"platform/data). SLO context: pool max=2 per service. Managed by {MANAGED_BY}"
            ),
            panels=[
                ("visualization", "postgres-connections-by-namespace", 0, 0, 24, 12),
                ("visualization", "pgpool-frontend-connections", 24, 0, 24, 12),
                ("visualization", "postgres-loadlinker-connections", 0, 12, 24, 12),
                ("visualization", "postgres-sesame-connections", 24, 12, 24, 12),
                ("search", "postgres-max-connections", 0, 24, 48, 10),
            ],
            panel_ref_prefix="platform_pg",
            time_from="now-6h",
        )
    )
    return objects


def _platform_data_bundle() -> list[tuple[str, str, dict[str, Any]]]:
    objects: list[tuple[str, str, dict[str, Any]]] = [
        (
            "visualization",
            "postgres-connections-by-namespace",
            metric_sum_line_visualization(
                title="Postgres connections by consumer namespace",
                data_view=METRICS_VIEW,
                time_field="time",
                group_field="metric.attributes.consumer_namespace.keyword",
                query=POSTGRES_ACTIVITY_QUERY,
                y_title="Connections",
            ),
        ),
        (
            "visualization",
            "pgpool-frontend-connections",
            metric_sum_line_visualization(
                title="Pgpool frontend connections (used vs capacity)",
                data_view=METRICS_VIEW,
                time_field="time",
                group_field="name.keyword",
                query=PGPOOL_FRONTEND_QUERY,
                y_title="Connections",
            ),
        ),
        (
            "visualization",
            "data-redis-connected-clients",
            metric_sum_line_visualization(
                title="Redis connected clients",
                data_view=METRICS_VIEW,
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
                data_view=METRICS_VIEW,
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
                data_view=METRICS_VIEW,
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
            dashboard_id="platform-data-namespace",
            title="Platform — data namespace",
            description=(
                "Postgres HA, Pgpool, and Redis metrics from the shared data namespace. "
                f"Managed by {MANAGED_BY}"
            ),
            panels=[
                ("visualization", "postgres-connections-by-namespace", 0, 0, 24, 12),
                ("visualization", "pgpool-frontend-connections", 24, 0, 24, 12),
                ("visualization", "data-redis-connected-clients", 0, 12, 24, 12),
                ("visualization", "data-redis-memory-used", 24, 12, 24, 12),
                ("search", "data-platform-metrics-snapshot", 0, 24, 48, 12),
            ],
            panel_ref_prefix="platform_data",
            time_from="now-6h",
        )
    )
    return objects


def _platform_correlation_bundle() -> list[tuple[str, str, dict[str, Any]]]:
    objects: list[tuple[str, str, dict[str, Any]]] = [
        (
            "visualization",
            "correlation-spans-by-service",
            line_visualization(
                title="Trace spans by service",
                data_view=TRACES_VIEW,
                time_field="startTime",
                group_field="serviceName",
            ),
        ),
        (
            "visualization",
            "correlation-logs-with-trace-by-service",
            line_visualization(
                title="Correlated logs by service (traceId present)",
                data_view=LOGS_VIEW,
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
                data_view=TRACES_VIEW,
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
                    "span.attributes.duration_ms",
                ],
                query=HTTP_SPANS_QUERY,
            ),
        ),
        (
            "search",
            "correlation-logs-by-trace",
            saved_search(
                title="Logs with trace context",
                data_view=LOGS_VIEW,
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
                data_view=LOGS_VIEW,
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
                data_view=LOGS_VIEW,
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
                data_view=METRICS_VIEW,
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
            dashboard_id="platform-apm-correlation",
            title="Platform — incident war room",
            description=(
                "Cross-signal correlation for on-call: traces, logs, and DB pressure. "
                "Pick a traceId in Discover to pivot across signals. "
                f"Managed by {MANAGED_BY}"
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
            panel_ref_prefix="platform_corr",
            time_from="now-1h",
            refresh_ms=15000,
        )
    )
    return objects


def _loadlinker_health_bundle() -> list[tuple[str, str, dict[str, Any]]]:
    slo_md = (
        f"## Loadlinker P0 SLO targets (dev)\n\n"
        f"- **bff** p95 latency: **{SLO_BFF_P95_MS} ms**\n"
        f"- **bidding** p95 latency: **{SLO_BIDDING_P95_MS} ms**\n"
        f"- **Error budget**: ERROR/FATAL logs trending up on P0 services\n"
        f"- **DB saturation**: watch pool pressure with max pool=2\n"
    )
    objects: list[tuple[str, str, dict[str, Any]]] = [
        (
            "visualization",
            "loadlinker-slo-notes",
            markdown_visualization(title="Loadlinker SLO targets", markdown=slo_md),
        ),
        (
            "visualization",
            "loadlinker-p0-http-spans",
            line_visualization(
                title="P0 HTTP request rate",
                data_view=TRACES_VIEW,
                time_field="startTime",
                group_field="serviceName",
                query=HTTP_SPANS_P0_QUERY,
                y_title="Requests",
            ),
        ),
        (
            "visualization",
            "loadlinker-p0-error-logs",
            line_visualization(
                title="P0 error logs",
                data_view=LOGS_VIEW,
                time_field="observedTime",
                group_field="serviceName.keyword",
                query=ERROR_LOGS_P0_QUERY,
                y_title="Errors",
            ),
        ),
        (
            "visualization",
            "loadlinker-p1-http-spans",
            line_visualization(
                title="P1 HTTP request rate",
                data_view=TRACES_VIEW,
                time_field="startTime",
                group_field="serviceName",
                query=HTTP_SPANS_QUERY + " AND " + LOADLINKER_P1_QUERY,
                y_title="Requests",
            ),
        ),
        (
            "visualization",
            "loadlinker-postgres-pressure",
            metric_sum_line_visualization(
                title="Loadlinker Postgres connections",
                data_view=METRICS_VIEW,
                time_field="time",
                group_field="metric.attributes.datname.keyword",
                query=POSTGRES_LOADLINKER_QUERY,
                y_title="Connections",
            ),
        ),
        (
            "search",
            "loadlinker-p0-http-snapshot",
            saved_search(
                title="P0 HTTP spans (check duration_ms vs SLO)",
                data_view=TRACES_VIEW,
                time_field="startTime",
                columns=[
                    "startTime",
                    "serviceName",
                    "span.attributes.path",
                    "span.attributes.method",
                    "span.attributes.duration_ms",
                    "durationInNanos",
                    "traceId",
                ],
                query=HTTP_SPANS_P0_QUERY,
            ),
        ),
        (
            "search",
            "loadlinker-p0-errors",
            saved_search(
                title="P0 recent errors",
                data_view=LOGS_VIEW,
                time_field="observedTime",
                columns=[
                    "observedTime",
                    "serviceName",
                    "severityText",
                    "traceId",
                    "body",
                ],
                query=ERROR_LOGS_P0_QUERY,
            ),
        ),
    ]
    objects.append(
        assemble_dashboard(
            dashboard_id="loadlinker-health",
            title="Loadlinker — service health",
            description=(
                "P0 services: bff, bidding, consignments, notifications. "
                f"Managed by {MANAGED_BY}"
            ),
            panels=[
                ("visualization", "loadlinker-slo-notes", 0, 0, 12, 8),
                ("visualization", "loadlinker-p0-http-spans", 12, 0, 36, 8),
                ("visualization", "loadlinker-p0-error-logs", 0, 8, 24, 10),
                ("visualization", "loadlinker-postgres-pressure", 24, 8, 24, 10),
                ("visualization", "loadlinker-p1-http-spans", 0, 18, 24, 10),
                ("search", "loadlinker-p0-http-snapshot", 24, 18, 24, 10),
                ("search", "loadlinker-p0-errors", 0, 28, 48, 12),
            ],
            panel_ref_prefix="loadlinker_health",
            time_from="now-6h",
        )
    )
    return objects


def _loadlinker_bff_bundle() -> list[tuple[str, str, dict[str, Any]]]:
    objects: list[tuple[str, str, dict[str, Any]]] = [
        (
            "visualization",
            "loadlinker-bff-request-rate",
            line_visualization(
                title="BFF request rate by path",
                data_view=TRACES_VIEW,
                time_field="startTime",
                group_field="span.attributes.path",
                query=HTTP_SPANS_BFF_QUERY,
                y_title="Requests",
            ),
        ),
        (
            "visualization",
            "loadlinker-bff-error-logs",
            line_visualization(
                title="BFF error logs",
                data_view=LOGS_VIEW,
                time_field="observedTime",
                group_field="serviceName.keyword",
                query=f'{ERROR_LOGS_QUERY} AND serviceName: "bff"',
                y_title="Errors",
            ),
        ),
        (
            "search",
            "loadlinker-bff-slow-spans",
            saved_search(
                title=f"BFF spans (SLO p95 target {SLO_BFF_P95_MS} ms)",
                data_view=TRACES_VIEW,
                time_field="startTime",
                columns=[
                    "startTime",
                    "span.attributes.path",
                    "span.attributes.method",
                    "span.attributes.duration_ms",
                    "durationInNanos",
                    "traceId",
                ],
                query=HTTP_SPANS_BFF_QUERY,
            ),
        ),
        (
            "search",
            "loadlinker-bff-errors",
            saved_search(
                title="BFF errors",
                data_view=LOGS_VIEW,
                time_field="observedTime",
                columns=[
                    "observedTime",
                    "severityText",
                    "traceId",
                    "body",
                ],
                query=f'{ERROR_LOGS_QUERY} AND serviceName: "bff"',
            ),
        ),
    ]
    objects.append(
        assemble_dashboard(
            dashboard_id="loadlinker-bff-edge",
            title="Loadlinker — BFF edge",
            description=(
                f"User-facing edge latency and errors. SLO p95 target {SLO_BFF_P95_MS} ms. "
                f"Managed by {MANAGED_BY}"
            ),
            panels=[
                ("visualization", "loadlinker-bff-request-rate", 0, 0, 36, 12),
                ("visualization", "loadlinker-bff-error-logs", 36, 0, 12, 12),
                ("search", "loadlinker-bff-slow-spans", 0, 12, 24, 14),
                ("search", "loadlinker-bff-errors", 24, 12, 24, 14),
            ],
            panel_ref_prefix="loadlinker_bff",
            time_from="now-3h",
            refresh_ms=30000,
        )
    )
    return objects


def _loadlinker_sesame_auth_bundle() -> list[tuple[str, str, dict[str, Any]]]:
    objects: list[tuple[str, str, dict[str, Any]]] = [
        (
            "visualization",
            "loadlinker-bff-auth-spans",
            line_visualization(
                title="BFF auth-related HTTP spans",
                data_view=TRACES_VIEW,
                time_field="startTime",
                group_field="span.attributes.path",
                query=(
                    f'{HTTP_SPANS_BFF_QUERY} AND span.attributes.path: '
                    "(*auth* OR *login* OR *session* OR *token* OR *jwks*)"
                ),
                y_title="Requests",
            ),
        ),
        (
            "visualization",
            "loadlinker-sesame-auth-errors",
            line_visualization(
                title="Auth errors (BFF + Sesame)",
                data_view=LOGS_VIEW,
                time_field="observedTime",
                group_field="serviceName.keyword",
                query=AUTH_FAILURE_LOGS_QUERY,
                y_title="Errors",
            ),
        ),
        (
            "search",
            "loadlinker-bff-sesame-auth-logs",
            saved_search(
                title="BFF logs mentioning Sesame/auth",
                data_view=LOGS_VIEW,
                time_field="observedTime",
                columns=[
                    "observedTime",
                    "serviceName",
                    "severityText",
                    "traceId",
                    "body",
                ],
                query=BFF_SESAME_AUTH_LOGS_QUERY,
            ),
        ),
        (
            "search",
            "loadlinker-sesame-auth-spans",
            saved_search(
                title="Sesame auth hot-path spans",
                data_view=TRACES_VIEW,
                time_field="startTime",
                columns=[
                    "startTime",
                    "serviceName",
                    "span.attributes.path",
                    "span.attributes.duration_ms",
                    "traceId",
                ],
                query=HTTP_SPANS_SESAME_AUTH_QUERY,
            ),
        ),
    ]
    objects.append(
        assemble_dashboard(
            dashboard_id="loadlinker-sesame-auth",
            title="Loadlinker → Sesame auth dependency",
            description=(
                "BFF calls into Sesame-IDAM for identity/auth. Use traceId to correlate "
                f"failures across namespaces. Managed by {MANAGED_BY}"
            ),
            panels=[
                ("visualization", "loadlinker-bff-auth-spans", 0, 0, 36, 12),
                ("visualization", "loadlinker-sesame-auth-errors", 36, 0, 12, 12),
                ("search", "loadlinker-bff-sesame-auth-logs", 0, 12, 24, 14),
                ("search", "loadlinker-sesame-auth-spans", 24, 12, 24, 14),
            ],
            panel_ref_prefix="loadlinker_sesame",
            time_from="now-3h",
        )
    )
    return objects


def _sesame_platform_bundle() -> list[tuple[str, str, dict[str, Any]]]:
    objects: list[tuple[str, str, dict[str, Any]]] = [
        (
            "visualization",
            "sesame-http-spans",
            line_visualization(
                title="Sesame HTTP request rate",
                data_view=TRACES_VIEW,
                time_field="startTime",
                group_field="serviceName",
                query=HTTP_SPANS_QUERY + " AND " + SESAME_SERVICES_QUERY,
                y_title="Requests",
            ),
        ),
        (
            "visualization",
            "sesame-error-logs",
            line_visualization(
                title="Sesame error logs",
                data_view=LOGS_VIEW,
                time_field="observedTime",
                group_field="serviceName.keyword",
                query=ERROR_LOGS_SESAME_QUERY,
                y_title="Errors",
            ),
        ),
        (
            "visualization",
            "sesame-postgres-pressure",
            metric_sum_line_visualization(
                title="Sesame Postgres connections",
                data_view=METRICS_VIEW,
                time_field="time",
                group_field="metric.attributes.datname.keyword",
                query=POSTGRES_SESAME_QUERY,
                y_title="Connections",
            ),
        ),
        (
            "search",
            "sesame-service-snapshot",
            saved_search(
                title="Sesame HTTP spans snapshot",
                data_view=TRACES_VIEW,
                time_field="startTime",
                columns=[
                    "startTime",
                    "serviceName",
                    "span.attributes.path",
                    "span.attributes.duration_ms",
                    "traceId",
                ],
                query=HTTP_SPANS_QUERY + " AND " + SESAME_SERVICES_QUERY,
            ),
        ),
    ]
    objects.append(
        assemble_dashboard(
            dashboard_id="sesame-platform-health",
            title="Sesame-IDAM — platform health",
            description=(
                "All six identity services. authz-core dominates traffic in production. "
                f"Managed by {MANAGED_BY}"
            ),
            panels=[
                ("visualization", "sesame-http-spans", 0, 0, 36, 12),
                ("visualization", "sesame-error-logs", 36, 0, 12, 12),
                ("visualization", "sesame-postgres-pressure", 0, 12, 24, 10),
                ("search", "sesame-service-snapshot", 24, 12, 24, 10),
            ],
            panel_ref_prefix="sesame_platform",
            time_from="now-6h",
        )
    )
    return objects


def _sesame_auth_bundle() -> list[tuple[str, str, dict[str, Any]]]:
    slo_md = (
        f"## Sesame auth hot-path SLO targets (dev)\n\n"
        f"- **authz-core** p95 latency: **{SLO_AUTHZ_P95_MS} ms**\n"
        f"- **identity-login-service**: login/register error rate\n"
        f"- **identity-session-service**: refresh/JWKS availability\n"
    )
    objects: list[tuple[str, str, dict[str, Any]]] = [
        (
            "visualization",
            "sesame-auth-slo-notes",
            markdown_visualization(title="Sesame auth SLO targets", markdown=slo_md),
        ),
        (
            "visualization",
            "sesame-auth-hot-spans",
            line_visualization(
                title="Auth hot-path request rate",
                data_view=TRACES_VIEW,
                time_field="startTime",
                group_field="serviceName",
                query=HTTP_SPANS_SESAME_AUTH_QUERY,
                y_title="Requests",
            ),
        ),
        (
            "visualization",
            "sesame-auth-error-logs",
            line_visualization(
                title="Auth hot-path errors",
                data_view=LOGS_VIEW,
                time_field="observedTime",
                group_field="serviceName.keyword",
                query=f"{ERROR_LOGS_QUERY} AND {SESAME_AUTH_HOT_QUERY}",
                y_title="Errors",
            ),
        ),
        (
            "search",
            "sesame-auth-spans-snapshot",
            saved_search(
                title=f"Auth spans (authz SLO p95 {SLO_AUTHZ_P95_MS} ms)",
                data_view=TRACES_VIEW,
                time_field="startTime",
                columns=[
                    "startTime",
                    "serviceName",
                    "span.attributes.path",
                    "span.attributes.method",
                    "span.attributes.duration_ms",
                    "traceId",
                ],
                query=HTTP_SPANS_SESAME_AUTH_QUERY,
            ),
        ),
        (
            "search",
            "sesame-auth-db-pressure",
            saved_search(
                title="Sesame DB / pool pressure logs",
                data_view=LOGS_VIEW,
                time_field="observedTime",
                columns=[
                    "observedTime",
                    "serviceName",
                    "severityText",
                    "traceId",
                    "body",
                ],
                query=DB_PRESSURE_SESAME_QUERY,
            ),
        ),
    ]
    objects.append(
        assemble_dashboard(
            dashboard_id="sesame-auth-critical-path",
            title="Sesame-IDAM — auth critical path",
            description=(
                "Login → session → authz-core hot path. "
                f"Managed by {MANAGED_BY}"
            ),
            panels=[
                ("visualization", "sesame-auth-slo-notes", 0, 0, 12, 8),
                ("visualization", "sesame-auth-hot-spans", 12, 0, 36, 8),
                ("visualization", "sesame-auth-error-logs", 0, 8, 24, 10),
                ("search", "sesame-auth-spans-snapshot", 24, 8, 24, 10),
                ("search", "sesame-auth-db-pressure", 0, 18, 48, 14),
            ],
            panel_ref_prefix="sesame_auth",
            time_from="now-3h",
            refresh_ms=30000,
        )
    )
    return objects


DASHBOARD_BUNDLES: dict[str, list[tuple[str, str, dict[str, Any]]]] = {
    "platform-postgres-connections": _platform_postgres_bundle(),
    "platform-data-namespace": _platform_data_bundle(),
    "platform-apm-correlation": _platform_correlation_bundle(),
    "loadlinker-health": _loadlinker_health_bundle(),
    "loadlinker-bff-edge": _loadlinker_bff_bundle(),
    "loadlinker-sesame-auth": _loadlinker_sesame_auth_bundle(),
    "sesame-platform-health": _sesame_platform_bundle(),
    "sesame-auth-critical-path": _sesame_auth_bundle(),
}

# Shared viz/search objects referenced by multiple bundles (import order handled by bundler).
SHARED_OBJECT_IDS: set[tuple[str, str]] = {
    ("visualization", "postgres-connections-by-namespace"),
    ("visualization", "pgpool-frontend-connections"),
}

DEPRECATED_SAVED_OBJECTS: list[tuple[str, str]] = [
    ("dashboard", "shared-observability-overview"),
    ("dashboard", "shared-postgres-connections"),
    ("dashboard", "shared-data-platform"),
    ("dashboard", "shared-apm-correlation"),
    ("visualization", "shared-metrics-by-service"),
    ("visualization", "shared-logs-by-service"),
    ("search", "shared-error-logs"),
    ("search", "rerp-api-metrics"),
    ("visualization", "postgres-connections-by-database"),
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
