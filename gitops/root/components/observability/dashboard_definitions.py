"""GitOps dashboard bundles for OpenSearch Dashboards (NDJSON source)."""

from __future__ import annotations

from typing import Any

MANAGED_BY = "shared-gitops-k8s-cluster"

LOGS_VIEW = "shared-observability-logs"
LOGS_TIME_FIELD = "observedTimestamp"

# Collector-set classification (see helm-values-otel transform/classify-log-signal).
LOG_EVENT_CLASS_FIELD = "log.attributes.event_class"
LOG_EVENT_CATEGORY_FIELD = "log.attributes.event_category"
LOG_HAS_TRACE_FIELD = "log.attributes.has_trace"
LOG_EPOLL_TARGET_FIELD = "log.attributes.log@target"
LOG_SCOPE_FIELD = "instrumentationScope.name"
LOG_NAMESPACE_FIELD = "resource.attributes.k8s@namespace@name"
LOG_APPLICATION_FIELD = "serviceName"

LOG_NOISE_CATEGORIES = (
    "epoll_io",
    "runtime_metrics",
    "runtime_config",
    "framework_lifecycle",
)
LOG_EPOLL_TARGET = "may::io::sys::select"
LOG_MEMORY_SCOPE = "brrtrouter::middleware::memory"
LOG_RUNTIME_CONFIG_TARGET = "may::config"
LOG_FRAMEWORK_LIFECYCLE_SCOPES = (
    "brrtrouter::dispatcher::core",
    "brrtrouter::validator_cache",
    "brrtrouter::router::core",
    "brrtrouter::server::service",
)

_NOISE_CATEGORY_OR = " OR ".join(f'"{c}"' for c in LOG_NOISE_CATEGORIES)
_FRAMEWORK_SCOPE_OR = " OR ".join(LOG_FRAMEWORK_LIFECYCLE_SCOPES)

# Sidebar + table: namespace → application → time → class → signal fields.
LOG_STREAM_COLUMNS = [
    LOG_NAMESPACE_FIELD,
    LOG_APPLICATION_FIELD,
    "observedTimestamp",
    "severityText",
    LOG_EVENT_CLASS_FIELD,
    LOG_EVENT_CATEGORY_FIELD,
    LOG_HAS_TRACE_FIELD,
    "body",
]

# Popular sidebar ranking (highest count first). Curated SRE control plane.
LOG_SIDEBAR_FILTER_FIELDS = [
    LOG_NAMESPACE_FIELD,
    LOG_APPLICATION_FIELD,
    "severityText",
    LOG_EVENT_CLASS_FIELD,
    LOG_EVENT_CATEGORY_FIELD,
    LOG_HAS_TRACE_FIELD,
    "traceId",
]

# Signal = application logs. Keep Lucene short — long nested body ORs break
# Discover URL state (rison) and can 400 the search API. Collector tagging is
# the source of truth; body/target/scope clauses cover high-volume legacy only.
LOG_SIGNAL_LUCENE = (
    f"({LOG_EVENT_CLASS_FIELD}:application) OR "
    f"(NOT {LOG_EVENT_CLASS_FIELD}:* AND NOT "
    f"{LOG_EVENT_CATEGORY_FIELD}: ({_NOISE_CATEGORY_OR}) AND NOT "
    f'body: (*epoll select*) AND NOT body: "Memory statistics")'
)

LOG_RUNTIME_NOISE_LUCENE = (
    f"({LOG_EVENT_CLASS_FIELD}:runtime_noise) OR "
    f"{LOG_EVENT_CATEGORY_FIELD}: ({_NOISE_CATEGORY_OR}) OR "
    'body: (*epoll select*) OR body: "Memory statistics" OR '
    f'{LOG_EPOLL_TARGET_FIELD}: "{LOG_RUNTIME_CONFIG_TARGET}" OR '
    f"{LOG_SCOPE_FIELD}: ({_FRAMEWORK_SCOPE_OR})"
)

LOG_ERRORS_LUCENE = (
    f"({LOG_SIGNAL_LUCENE}) AND severityText: (ERROR OR FATAL OR WARN)"
)

LOG_AUTH_LUCENE = (
    f'({LOG_SIGNAL_LUCENE}) AND {LOG_NAMESPACE_FIELD}: "sesame-idam"'
)

LOG_BFF_LUCENE = (
    f'({LOG_SIGNAL_LUCENE}) AND {LOG_NAMESPACE_FIELD}: "loadlinker" AND '
    f'{LOG_APPLICATION_FIELD}: "bff"'
)

# Backward-compatible alias used by older docs / filter helpers.
LOG_NOISE_EXCLUSION_LUCENE = LOG_SIGNAL_LUCENE


def log_signal_filters(*, index_id: str = LOGS_VIEW) -> list[dict[str, Any]]:
    """Default pills: hide runtime_noise; keep docs selectable via event_class."""
    return [
        {
            "$state": {"store": "appState"},
            "meta": {
                "alias": "Hide runtime noise (tagged)",
                "disabled": False,
                "index": index_id,
                "key": LOG_EVENT_CLASS_FIELD,
                "negate": True,
                "type": "phrase",
                "params": {"query": "runtime_noise"},
            },
            "query": {
                "match_phrase": {LOG_EVENT_CLASS_FIELD: "runtime_noise"}
            },
        },
        {
            "$state": {"store": "appState"},
            "meta": {
                "alias": "Hide untagged epoll lines",
                "disabled": False,
                "index": index_id,
                "key": "body",
                "negate": True,
                "type": "custom",
            },
            "query": {"wildcard": {"body.keyword": "*epoll select*"}},
        },
    ]


# Legacy name used by older call sites / tests.
log_noise_filters = log_signal_filters


def _url_encode_lucene(query: str) -> str:
    return (
        query.replace("\\", "%5C")
        .replace(" ", "%20")
        .replace('"', "%22")
        .replace("(", "%28")
        .replace(")", "%29")
        .replace(":", "%3A")
    )


# Discover landing = Signal scope (field sidebar). Open saved searches for scopes.
LOGS_DISCOVER_DEFAULT_ROUTE = (
    "/app/data-explorer/discover/#/?"
    "_g=(filters:!(),refreshInterval:(pause:!f,value:30000),time:(from:now-15m,to:now))"
    "&_a=(discover:(columns:!("
    + ",".join(LOG_STREAM_COLUMNS)
    + "),interval:auto,sort:!(!(observedTimestamp,desc))),"
    "metadata:(indexPattern:shared-observability-logs,view:discover))"
    "&_q=(filters:!(),query:(language:lucene,query:'"
    + _url_encode_lucene(LOG_SIGNAL_LUCENE)
    + "'))"
)

LOGS_DISCOVER_PUBLIC_URL = (
    "http://opensearch.dev.microscaler.local" + LOGS_DISCOVER_DEFAULT_ROUTE
)


def compact(value: Any) -> str:
    import json

    return json.dumps(value, separators=(",", ":"))


def search_source(
    index_reference: str,
    query: str = LOG_SIGNAL_LUCENE,
    *,
    filters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "query": {"query": query, "language": "lucene"},
        "filter": filters if filters is not None else log_signal_filters(index_id=LOGS_VIEW),
        "indexRefName": index_reference,
    }


def discover_guide_markdown() -> dict[str, Any]:
    """Dashboard banner: field sidebar + saved-search scopes live in Discover."""
    markdown = (
        "## Use Discover for filters (Logz.io-style left panel)\n\n"
        f"[**Open Logs / Signal**]({LOGS_DISCOVER_DEFAULT_ROUTE}) — default triage view.\n\n"
        "### Filter order\n"
        "1. **namespace** (`resource.attributes.k8s@namespace@name`: "
        "`loadlinker` / `sesame-idam` / `rerp`)\n"
        "2. **application** (`serviceName`)\n"
        "3. **time** (picker, top right)\n"
        "4. **event_class** / **event_category** (signal vs runtime noise)\n\n"
        "### Saved searches (Discover → Open)\n"
        "- **Logs / Signal** — application logs only (`event_class:application`)\n"
        "- **Logs / Errors** — WARN+ within signal\n"
        "- **Logs / Auth** — `sesame-idam` signal\n"
        "- **Logs / BFF** — `loadlinker` + `bff` signal\n"
        "- **Logs / Runtime noise** — epoll, memory, may config, BRRTRouter "
        "lifecycle (`event_class:runtime_noise`) — select *for* trash, not mixed "
        "with triage\n\n"
        "System lines stay indexed; they are tagged, not deleted. Filter "
        "`event_category` for `epoll_io` / `runtime_metrics` / `runtime_config` / "
        "`framework_lifecycle`."
    )
    vis_state = {
        "title": "Open Discover for field sidebar",
        "type": "markdown",
        "params": {
            "fontSize": 12,
            "openLinksInNewTab": False,
            "markdown": markdown,
        },
        "aggs": [],
    }
    return {
        "attributes": {
            "title": "Open Discover for field sidebar",
            "description": f"Managed by {MANAGED_BY}",
            "visState": compact(vis_state),
            "uiStateJSON": "{}",
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": compact(
                    {"query": {"query": "", "language": "lucene"}, "filter": []}
                )
            },
        },
        "references": [],
    }


def log_histogram_visualization(
    *,
    title: str,
    data_view: str,
    time_field: str,
    query: str = LOG_SIGNAL_LUCENE,
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
    *,
    title: str,
    data_view: str,
    time_field: str,
    columns: list[str],
    query: str,
    filters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    source_ref = "kibanaSavedObjectMeta.searchSourceJSON.index"
    return {
        "attributes": {
            "title": title,
            "description": f"Managed by {MANAGED_BY}",
            "columns": columns,
            "sort": [[time_field, "desc"]],
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": compact(
                    search_source(source_ref, query, filters=filters)
                )
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
                            "query": {
                                "query": LOG_SIGNAL_LUCENE,
                                "language": "lucene",
                            },
                            "filter": log_signal_filters(),
                        }
                    )
                },
            },
            "references": references,
        },
    )


def _saved_search_scopes() -> list[tuple[str, str, dict[str, Any]]]:
    """Discover → Open: Signal / Errors / Auth / BFF / Runtime noise."""
    # logs-explore-stream is the canonical "Logs / Signal" (dashboard + Discover).
    scopes: list[tuple[str, str, str, list[dict[str, Any]] | None]] = [
        ("logs-errors", "Logs / Errors", LOG_ERRORS_LUCENE, None),
        ("logs-auth", "Logs / Auth", LOG_AUTH_LUCENE, None),
        ("logs-bff", "Logs / BFF", LOG_BFF_LUCENE, None),
        (
            "logs-runtime-noise",
            "Logs / Runtime noise",
            LOG_RUNTIME_NOISE_LUCENE,
            [],  # no hide pills — this view *selects* trash
        ),
    ]
    objects: list[tuple[str, str, dict[str, Any]]] = []
    for object_id, title, query, filters in scopes:
        objects.append(
            (
                "search",
                object_id,
                saved_search(
                    title=title,
                    data_view=LOGS_VIEW,
                    time_field=LOGS_TIME_FIELD,
                    columns=LOG_STREAM_COLUMNS,
                    query=query,
                    filters=filters,
                ),
            )
        )
    return objects


def _logs_explore_bundle() -> list[tuple[str, str, dict[str, Any]]]:
    """Dashboard companion + Discover saved-search pack."""
    objects: list[tuple[str, str, dict[str, Any]]] = [
        (
            "visualization",
            "logs-explore-discover-guide",
            discover_guide_markdown(),
        ),
        (
            "visualization",
            "logs-explore-histogram",
            log_histogram_visualization(
                title="Log volume (signal)",
                data_view=LOGS_VIEW,
                time_field=LOGS_TIME_FIELD,
            ),
        ),
        (
            "search",
            "logs-explore-stream",
            saved_search(
                title="Logs / Signal",
                data_view=LOGS_VIEW,
                time_field=LOGS_TIME_FIELD,
                columns=LOG_STREAM_COLUMNS,
                query=LOG_SIGNAL_LUCENE,
            ),
        ),
    ]
    objects.extend(_saved_search_scopes())
    objects.append(
        assemble_dashboard(
            dashboard_id="logs-explore",
            title="Logs",
            description=(
                "Companion overview. Open Discover for the field sidebar and saved "
                "searches (Signal / Errors / Auth / BFF / Runtime noise). System "
                "noise (epoll, memory, may config, BRRTRouter lifecycle) is tagged "
                "event_class:runtime_noise — hidden by default, selectable when "
                f"needed. Managed by {MANAGED_BY}"
            ),
            panels=[
                ("visualization", "logs-explore-discover-guide", 0, 0, 48, 8),
                ("visualization", "logs-explore-histogram", 0, 8, 48, 12),
                ("search", "logs-explore-stream", 0, 20, 48, 26),
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
