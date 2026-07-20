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
LOG_METHOD_FIELD = "log.attributes.method"
LOG_PATH_FIELD = "log.attributes.path"
LOG_PATH_KEYWORD_FIELD = "log.attributes.path.keyword"
LOG_STATUS_FIELD = "log.attributes.status"
LOG_DURATION_FIELD = "log.attributes.duration_ms"

# Default HTTP latency SLO percentile target (BFF edge design: p95 ≤ 500 ms).
HTTP_P95_SLO_MS = 500

# HTTP status class colors (pie / stream / triage).
HTTP_STATUS_COLOR_2XX = "#0a7a28"  # green
HTTP_STATUS_COLOR_3XX = "#1a73e8"  # blue
HTTP_STATUS_COLOR_4XX = "#c77700"  # amber
HTTP_STATUS_COLOR_5XX = "#b00020"  # red
HTTP_STATUS_COLOR_OTHER = "#666666"

LOGS_DASHBOARD_ID = "logs-explore"
LOG_VOLUME_BUCKET_MS = 30_000  # clickable volume bars (matches typical auto bucket)

# epoll_io is dropped at the collector (filter/drop-epoll-io); keep the token
# for legacy docs still in the index and for Discover filter pills.
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
)

_NOISE_CATEGORY_OR = " OR ".join(f'"{c}"' for c in LOG_NOISE_CATEGORIES)
_FRAMEWORK_SCOPE_OR = " OR ".join(LOG_FRAMEWORK_LIFECYCLE_SCOPES)

# Short root-level copies (ingest pipeline) used as Discover column headers.
# Source fields keep full OTel paths for Lucene / aggregations / filters.
LOG_FIELD_SHORT_COPIES = {
    "name": LOG_NAMESPACE_FIELD,
    "event_class": LOG_EVENT_CLASS_FIELD,
    "event_category": LOG_EVENT_CATEGORY_FIELD,
    "method": LOG_METHOD_FIELD,
    "path": LOG_PATH_FIELD,
    "status": LOG_STATUS_FIELD,
    "duration_ms": LOG_DURATION_FIELD,
    "has_trace": LOG_HAS_TRACE_FIELD,
}

# Discover also keeps customLabel on long paths (detail/sidebar); DE headers
# ignore it, so columns use the short copies above.
LOG_FIELD_SHORT_LABELS = {
    source: short for short, source in LOG_FIELD_SHORT_COPIES.items()
} | {
    LOG_PATH_KEYWORD_FIELD: "path",
    "log.attributes.message": "message",
    LOG_EPOLL_TARGET_FIELD: "log_target",
}

# Sidebar + table: namespace → application → time → class → HTTP → signal fields.
LOG_STREAM_COLUMNS = [
    "name",
    LOG_APPLICATION_FIELD,
    "observedTimestamp",
    "severityText",
    "event_class",
    "event_category",
    "method",
    "path",
    "status",
    "duration_ms",
    "has_trace",
    "body",
]

LOG_HTTP_COLUMNS = [
    "name",
    LOG_APPLICATION_FIELD,
    "observedTimestamp",
    "method",
    "path",
    "status",
    "duration_ms",
    "body",
]

# Popular sidebar ranking (highest count first). Curated SRE control plane.
LOG_SIDEBAR_FILTER_FIELDS = [
    LOG_NAMESPACE_FIELD,
    LOG_APPLICATION_FIELD,
    "severityText",
    LOG_EVENT_CLASS_FIELD,
    LOG_EVENT_CATEGORY_FIELD,
    LOG_METHOD_FIELD,
    LOG_PATH_FIELD,
    LOG_STATUS_FIELD,
    LOG_HAS_TRACE_FIELD,
    "traceId",
]

# Signal = application logs. Prefer a single phrase query — nested NOT/OR
# Lucene 400s Discover against this OpenSearch mapping. Collector tagging is
# the source of truth; filter pills hide leftover untagged epoll lines.
LOG_SIGNAL_LUCENE = f"{LOG_EVENT_CLASS_FIELD}:application"

# Same constraint as Signal: keep Lucene to a single tagged phrase. Category /
# body/scope selection is done in the Discover sidebar (event_category).
LOG_RUNTIME_NOISE_LUCENE = f"{LOG_EVENT_CLASS_FIELD}:runtime_noise"

LOG_HTTP_LUCENE = (
    f"{LOG_EVENT_CLASS_FIELD}:application AND {LOG_EVENT_CATEGORY_FIELD}:http"
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


def _discover_route_for_query(query: str) -> str:
    return (
        "/app/data-explorer/discover/#/?"
        "_g=(filters:!(),refreshInterval:(pause:!f,value:30000),time:(from:now-15m,to:now))"
        "&_a=(discover:(columns:!("
        + ",".join(LOG_STREAM_COLUMNS)
        + "),interval:auto,sort:!(!(observedTimestamp,desc))),"
        "metadata:(indexPattern:shared-observability-logs,view:discover))"
        "&_q=(filters:!(),query:(language:lucene,query:'"
        + _url_encode_lucene(query)
        + "'))"
    )


def discover_guide_markdown() -> dict[str, Any]:
    """Dashboard banner: field sidebar + saved-search scopes live in Discover."""
    http_route = _discover_route_for_query(LOG_HTTP_LUCENE)
    markdown = (
        "## Use Discover for filters (Logz.io-style left panel)\n\n"
        f"[**Open Logs / Signal**]({LOGS_DISCOVER_DEFAULT_ROUTE}) — default triage.\n"
        f"[**Open Logs / HTTP**]({http_route}) — access logs "
        "(`Request completed` / method · path · status · duration).\n\n"
        "### Filter order\n"
        "1. **namespace** (`loadlinker` / `sesame-idam` / `rerp`)\n"
        "2. **application** (`serviceName`)\n"
        "3. **time** (picker, top right)\n"
        "4. **event_category** (`http` / `auth`) or method / path / status\n\n"
        "### Saved searches (Discover → Open)\n"
        "- **Logs / Signal** — all application logs "
        "(`event_class:application`)\n"
        "- **Logs / HTTP** — access logs only (`event_category:http`)\n"
        "- **Logs / Errors** — WARN+ within signal\n"
        "- **Logs / Auth** — `sesame-idam` signal\n"
        "- **Logs / BFF** — `loadlinker` + `bff` signal\n"
        "- **Logs / Runtime noise** — rare lifecycle/config lines "
        "(`event_class:runtime_noise`)\n\n"
        "Epoll and memory stats are **dropped at the collector** (not indexed).\n\n"
        "### Signal stream row links (no expand)\n"
        "- **doc** → View single document\n"
        "- **around** → View surrounding documents\n"
        "Use Discover (links above) when you need the field sidebar / JSON detail."
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


def http_status_class_color_expr(field: str = "status") -> str:
    """Vega expr: map numeric/string HTTP status → class color."""
    return (
        f"toNumber(datum.{field}) >= 500 ? '{HTTP_STATUS_COLOR_5XX}' : "
        f"toNumber(datum.{field}) >= 400 ? '{HTTP_STATUS_COLOR_4XX}' : "
        f"toNumber(datum.{field}) >= 300 ? '{HTTP_STATUS_COLOR_3XX}' : "
        f"toNumber(datum.{field}) >= 200 ? '{HTTP_STATUS_COLOR_2XX}' : "
        f"'{HTTP_STATUS_COLOR_OTHER}'"
    )


def http_status_vis_colors() -> dict[str, str]:
    """uiState legend colors for classic pie/table (keyed by status string)."""
    colors: dict[str, str] = {}
    for code in range(100, 600):
        if 200 <= code < 300:
            colors[str(code)] = HTTP_STATUS_COLOR_2XX
        elif 300 <= code < 400:
            colors[str(code)] = HTTP_STATUS_COLOR_3XX
        elif 400 <= code < 500:
            colors[str(code)] = HTTP_STATUS_COLOR_4XX
        elif 500 <= code < 600:
            colors[str(code)] = HTTP_STATUS_COLOR_5XX
        else:
            colors[str(code)] = HTTP_STATUS_COLOR_OTHER
    return colors


def _visualization(
    *,
    title: str,
    data_view: str,
    vis_state: dict[str, Any],
    query: str,
    filters: list[dict[str, Any]] | None = None,
    ui_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_ref = "kibanaSavedObjectMeta.searchSourceJSON.index"
    return {
        "attributes": {
            "title": title,
            "description": f"Managed by {MANAGED_BY}",
            "visState": compact(vis_state),
            "uiStateJSON": compact(ui_state or {}),
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": compact(
                    search_source(source_ref, query, filters=filters)
                )
            },
        },
        "references": [{"name": source_ref, "type": "index-pattern", "id": data_view}],
    }


def log_histogram_visualization(
    *,
    title: str,
    data_view: str,
    time_field: str,
    query: str = LOG_SIGNAL_LUCENE,
    bucket_ms: int = LOG_VOLUME_BUCKET_MS,
    dashboard_id: str = LOGS_DASHBOARD_ID,
) -> dict[str, Any]:
    """Volume bars; click a bar to zoom the dashboard time range to that bucket."""
    # href updates `_g.time` (rison). Interval fixed so click bounds are known.
    interval = f"{bucket_ms // 1000}s"
    href_expr = (
        f"'/app/dashboards#/view/{dashboard_id}?_g=(filters:!(),"
        "refreshInterval:(pause:!f,value:30000),"
        "time:(from:\\'' + utcFormat(datum.start, '%Y-%m-%dT%H:%M:%S.000Z') + "
        "'\\',to:\\'' + utcFormat(datum.end, '%Y-%m-%dT%H:%M:%S.000Z') + '\\'))'"
    )
    spec = {
        "$schema": "https://vega.github.io/schema/vega/v5.json",
        "padding": {"left": 8, "right": 8, "top": 8, "bottom": 8},
        "autosize": {"type": "fit", "contains": "padding"},
        "data": [
            {
                "name": "volumes",
                "url": {
                    "%context%": True,
                    "%timefield%": time_field,
                    "index": "otel-v1-apm-logs-*",
                    "body": {
                        "size": 0,
                        "aggs": {
                            "volumes": {
                                "date_histogram": {
                                    "field": time_field,
                                    "fixed_interval": interval,
                                    "min_doc_count": 0,
                                    "extended_bounds": {
                                        "min": {"%timefilter%": "min"},
                                        "max": {"%timefilter%": "max"},
                                    },
                                }
                            }
                        },
                    },
                },
                "format": {"property": "aggregations.volumes.buckets"},
                "transform": [
                    {
                        "type": "formula",
                        "as": "start",
                        "expr": "datum.key",
                    },
                    {
                        "type": "formula",
                        "as": "end",
                        "expr": f"datum.key + {bucket_ms}",
                    },
                    {
                        "type": "formula",
                        "as": "href",
                        "expr": href_expr,
                    },
                ],
            }
        ],
        "signals": [
            {
                "name": "tooltip",
                "value": {},
                "on": [
                    {
                        "events": "@volbar:mouseover",
                        "update": (
                            "{x: x(), y: y(), count: datum.doc_count, "
                            "label: utcFormat(datum.start, '%H:%M:%S')}"
                        ),
                    },
                    {"events": "@volbar:mouseout", "update": "{}"},
                ],
            }
        ],
        "scales": [
            {
                "name": "x",
                "type": "time",
                "domain": {"data": "volumes", "field": "start"},
                "range": "width",
            },
            {
                "name": "y",
                "type": "linear",
                "domain": {"data": "volumes", "field": "doc_count"},
                "nice": True,
                "range": "height",
            },
        ],
        "axes": [
            {
                "orient": "bottom",
                "scale": "x",
                "labelFontSize": 10,
                "title": f"{time_field} per {interval} (click bar → zoom time)",
                "titleFontSize": 11,
            },
            {
                "orient": "left",
                "scale": "y",
                "labelFontSize": 10,
                "title": "Count",
                "titleFontSize": 11,
            },
        ],
        "marks": [
            {
                "name": "volbar",
                "type": "rect",
                "from": {"data": "volumes"},
                "encode": {
                    "enter": {
                        "fill": {"value": "#0b7a75"},
                        "cursor": {"value": "pointer"},
                    },
                    "update": {
                        "x": {"scale": "x", "field": "start"},
                        "x2": {
                            "scale": "x",
                            "signal": f"datum.start + {bucket_ms * 0.85}",
                        },
                        "y": {"scale": "y", "field": "doc_count"},
                        "y2": {"scale": "y", "value": 0},
                        "href": {"field": "href"},
                        "tooltip": {
                            "signal": (
                                "{title: utcFormat(datum.start, '%Y-%m-%d %H:%M:%S'), "
                                "'count': datum.doc_count, "
                                "'action': 'click to zoom time range'}"
                            )
                        },
                    },
                    "hover": {"fill": {"value": "#095e5a"}},
                },
            }
        ],
    }
    vis_state = {
        "title": title,
        "type": "vega",
        "params": {"spec": compact(spec), "hideWarnings": True},
        "aggs": [],
    }
    return _visualization(
        title=title, data_view=data_view, vis_state=vis_state, query=query
    )


def log_terms_table_visualization(
    *,
    title: str,
    data_view: str,
    field: str,
    query: str,
    size: int = 10,
    field_label: str | None = None,
) -> dict[str, Any]:
    """Top-N terms table (paths, status codes, …)."""
    bucket_params: dict[str, Any] = {
        "field": field,
        "size": size,
        "order": "desc",
        "orderBy": "1",
        "otherBucket": False,
        "otherBucketLabel": "Other",
        "missingBucket": False,
        "missingBucketLabel": "Missing",
    }
    if field_label:
        bucket_params["customLabel"] = field_label
    vis_state = {
        "title": title,
        "type": "table",
        "params": {
            "perPage": size,
            "showPartialRows": False,
            "showMeticsAtAllLevels": False,
            "sort": {"columnIndex": None, "direction": None},
            "showTotal": False,
            "showToolbar": False,
            "totalFunc": "sum",
            "percentageCol": "",
        },
        "aggs": [
            {
                "id": "1",
                "enabled": True,
                "type": "count",
                "schema": "metric",
                "params": {"customLabel": "count"},
            },
            {
                "id": "2",
                "enabled": True,
                "type": "terms",
                "schema": "bucket",
                "params": bucket_params,
            },
        ],
    }
    return _visualization(
        title=title, data_view=data_view, vis_state=vis_state, query=query
    )


def log_terms_pie_visualization(
    *,
    title: str,
    data_view: str,
    field: str,
    query: str,
    size: int = 10,
    field_label: str | None = None,
) -> dict[str, Any]:
    """HTTP status donut: 2xx green / 3xx blue / 4xx amber / 5xx red."""
    del field_label  # labels come from status keys
    # Vega pie — classic pie ignores custom class colors (all teal).
    color_expr = http_status_class_color_expr("status")
    spec = {
        "$schema": "https://vega.github.io/schema/vega/v5.json",
        "padding": 4,
        "autosize": {"type": "fit", "contains": "padding"},
        "data": [
            {
                "name": "statuses",
                "url": {
                    "%context%": True,
                    "%timefield%": LOGS_TIME_FIELD,
                    "index": "otel-v1-apm-logs-*",
                    "body": {
                        "size": 0,
                        "aggs": {
                            "statuses": {
                                "terms": {
                                    "field": field,
                                    "size": size,
                                    "order": {"_count": "desc"},
                                }
                            }
                        },
                    },
                },
                "format": {"property": "aggregations.statuses.buckets"},
                "transform": [
                    {"type": "formula", "as": "status", "expr": "datum.key"},
                    {"type": "formula", "as": "color", "expr": color_expr},
                    {
                        "type": "joinaggregate",
                        "ops": ["sum"],
                        "fields": ["doc_count"],
                        "as": ["total"],
                    },
                    {
                        "type": "formula",
                        "as": "percent",
                        "expr": "datum.total > 0 ? datum.doc_count / datum.total : 0",
                    },
                    # Legend label: "200 - 100%" (no text on the donut itself).
                    {
                        "type": "formula",
                        "as": "label",
                        "expr": (
                            "datum.status + ' - ' + format(datum.percent, '.0%')"
                        ),
                    },
                    {
                        "type": "pie",
                        "field": "doc_count",
                        "startAngle": 0,
                        "endAngle": 6.283185307179586,
                    },
                ],
            },
        ],
        "scales": [
            {
                "name": "color",
                "type": "ordinal",
                "domain": {"data": "statuses", "field": "label"},
                "range": {"data": "statuses", "field": "color"},
            }
        ],
        "marks": [
            {
                "type": "arc",
                "from": {"data": "statuses"},
                "encode": {
                    "enter": {
                        "fill": {"field": "color"},
                        "stroke": {"value": "#fff"},
                        "strokeWidth": {"value": 1},
                        "tooltip": {
                            "signal": (
                                "{'status': datum.status, "
                                "'count': datum.doc_count, "
                                "'pct': format(datum.percent, '.0%')}"
                            )
                        },
                    },
                    "update": {
                        # Leave room on the right for "200 - 100%" legend labels.
                        "x": {"signal": "width * 0.38"},
                        "y": {"signal": "height / 2"},
                        "startAngle": {"field": "startAngle"},
                        "endAngle": {"field": "endAngle"},
                        "innerRadius": {"signal": "min(width * 0.72, height) / 5"},
                        "outerRadius": {
                            "signal": "min(width * 0.72, height) / 2 - 4"
                        },
                    },
                },
            },
        ],
        "legends": [
            {
                "fill": "color",
                "orient": "right",
                "title": "status",
                "labelFontSize": 11,
                "symbolType": "circle",
                "symbolSize": 80,
            }
        ],
    }
    # Legend uses ordinal scale range from data colors — keep uiState as docs hint.
    vis_state = {
        "title": title,
        "type": "vega",
        "params": {"spec": compact(spec), "hideWarnings": True},
        "aggs": [],
    }
    return _visualization(
        title=title,
        data_view=data_view,
        vis_state=vis_state,
        query=query,
        ui_state={"vis": {"colors": http_status_vis_colors()}},
    )


def log_http_top_paths_visualization(
    *,
    title: str,
    data_view: str,
    query: str,
    size: int = 10,
    slo_ms: int = HTTP_P95_SLO_MS,
) -> dict[str, Any]:
    """Top paths with count, RPS (window-normalized), and p95 vs SLO."""
    # Full Vega: classic table cannot compute RPS from the dashboard time range.
    spec = {
        "$schema": "https://vega.github.io/schema/vega/v5.json",
        "padding": 8,
        "autosize": {"type": "fit", "contains": "padding"},
        "signals": [
            # Dashboard default window is 15m; RPS = count / windowSeconds.
            # (OSD 2.19 does not reliably substitute %timefilter% into Vega signals.)
            {"name": "windowSeconds", "value": 900},
            {"name": "sloMs", "value": slo_ms},
        ],
        "data": [
            {
                "name": "paths",
                "url": {
                    "%context%": True,
                    "%timefield%": LOGS_TIME_FIELD,
                    "index": "otel-v1-apm-logs*",
                    "body": {
                        "size": 0,
                        "aggs": {
                            "paths": {
                                "terms": {
                                    "field": LOG_PATH_KEYWORD_FIELD,
                                    "size": size,
                                    "order": {"_count": "desc"},
                                },
                                "aggs": {
                                    "p95": {
                                        "percentiles": {
                                            "field": LOG_DURATION_FIELD,
                                            "percents": [95],
                                        }
                                    }
                                },
                            }
                        },
                    },
                },
                "format": {"property": "aggregations.paths.buckets"},
                "transform": [
                    {
                        "type": "formula",
                        "as": "p95",
                        "expr": "datum.p95.values['95.0']",
                    },
                    {
                        "type": "formula",
                        "as": "vsSlo",
                        "expr": "datum.p95 <= sloMs ? 'ok' : 'breach'",
                    },
                    {
                        "type": "window",
                        "ops": ["row_number"],
                        "as": ["row"],
                        "sort": [{"field": "doc_count", "order": "descending"}],
                    },
                ],
            },
            {
                "name": "header",
                "values": [
                    {
                        "path": "path",
                        "count": "count",
                        "rps": "rps/15m",
                        "p95": "p95 ms",
                        "slo": "SLO ms",
                        "vs": "pSLO",
                        "row": 0,
                    }
                ],
            },
        ],
        "scales": [
            {
                "name": "y",
                "type": "band",
                "domain": {"data": "paths", "field": "row"},
                "range": {"step": 22},
                "padding": 0.1,
            }
        ],
        "marks": [
            {
                "type": "group",
                "encode": {
                    "update": {
                        "x": {"value": 0},
                        "y": {"value": 0},
                        "width": {"signal": "width"},
                        "height": {"signal": "22"},
                    }
                },
                "marks": [
                    {
                        "type": "text",
                        "from": {"data": "header"},
                        "encode": {
                            "update": {
                                "x": {"value": 0},
                                "y": {"value": 14},
                                "text": {"field": "path"},
                                "fontWeight": {"value": "bold"},
                                "fontSize": {"value": 11},
                                "fill": {"value": "#333"},
                            }
                        },
                    },
                    {
                        "type": "text",
                        "from": {"data": "header"},
                        "encode": {
                            "update": {
                                "x": {"signal": "width * 0.48"},
                                "y": {"value": 14},
                                "text": {"field": "count"},
                                "align": {"value": "right"},
                                "fontWeight": {"value": "bold"},
                                "fontSize": {"value": 11},
                                "fill": {"value": "#333"},
                            }
                        },
                    },
                    {
                        "type": "text",
                        "from": {"data": "header"},
                        "encode": {
                            "update": {
                                "x": {"signal": "width * 0.60"},
                                "y": {"value": 14},
                                "text": {"field": "rps"},
                                "align": {"value": "right"},
                                "fontWeight": {"value": "bold"},
                                "fontSize": {"value": 11},
                                "fill": {"value": "#333"},
                            }
                        },
                    },
                    {
                        "type": "text",
                        "from": {"data": "header"},
                        "encode": {
                            "update": {
                                "x": {"signal": "width * 0.74"},
                                "y": {"value": 14},
                                "text": {"field": "p95"},
                                "align": {"value": "right"},
                                "fontWeight": {"value": "bold"},
                                "fontSize": {"value": 11},
                                "fill": {"value": "#333"},
                            }
                        },
                    },
                    {
                        "type": "text",
                        "from": {"data": "header"},
                        "encode": {
                            "update": {
                                "x": {"signal": "width * 0.86"},
                                "y": {"value": 14},
                                "text": {"field": "slo"},
                                "align": {"value": "right"},
                                "fontWeight": {"value": "bold"},
                                "fontSize": {"value": 11},
                                "fill": {"value": "#333"},
                            }
                        },
                    },
                    {
                        "type": "text",
                        "from": {"data": "header"},
                        "encode": {
                            "update": {
                                "x": {"signal": "width"},
                                "y": {"value": 14},
                                "text": {"field": "vs"},
                                "align": {"value": "right"},
                                "fontWeight": {"value": "bold"},
                                "fontSize": {"value": 11},
                                "fill": {"value": "#333"},
                            }
                        },
                    },
                ],
            },
            {
                "type": "group",
                "encode": {
                    "update": {
                        "y": {"value": 24},
                        "width": {"signal": "width"},
                        "height": {"signal": "height - 24"},
                    }
                },
                "marks": [
                    {
                        "type": "text",
                        "from": {"data": "paths"},
                        "encode": {
                            "update": {
                                "x": {"value": 0},
                                "y": {"scale": "y", "field": "row", "band": 0.5},
                                "text": {"field": "key"},
                                "fontSize": {"value": 11},
                                "fill": {"value": "#111"},
                                "limit": {"signal": "width * 0.46"},
                            }
                        },
                    },
                    {
                        "type": "text",
                        "from": {"data": "paths"},
                        "encode": {
                            "update": {
                                "x": {"signal": "width * 0.48"},
                                "y": {"scale": "y", "field": "row", "band": 0.5},
                                "text": {"field": "doc_count"},
                                "align": {"value": "right"},
                                "fontSize": {"value": 11},
                                "fill": {"value": "#111"},
                            }
                        },
                    },
                    {
                        "type": "text",
                        "from": {"data": "paths"},
                        "encode": {
                            "update": {
                                "x": {"signal": "width * 0.60"},
                                "y": {"scale": "y", "field": "row", "band": 0.5},
                                "text": {
                                    "signal": (
                                        "format(datum.doc_count / windowSeconds, '.3f')"
                                    )
                                },
                                "align": {"value": "right"},
                                "fontSize": {"value": 11},
                                "fill": {"value": "#111"},
                            }
                        },
                    },
                    {
                        "type": "text",
                        "from": {"data": "paths"},
                        "encode": {
                            "update": {
                                "x": {"signal": "width * 0.74"},
                                "y": {"scale": "y", "field": "row", "band": 0.5},
                                # Integer ms today (0/1/2…); use 3dp below 1 so
                                # sub-ms floats are visible if emitters gain precision.
                                "text": {
                                    "signal": (
                                        "datum.p95 < 1 ? format(datum.p95, '.3f') "
                                        ": format(datum.p95, '.1f')"
                                    )
                                },
                                "align": {"value": "right"},
                                "fontSize": {"value": 11},
                                "fill": {
                                    "signal": (
                                        "datum.vsSlo === 'ok' ? '#0a7a28' : '#b00020'"
                                    )
                                },
                            }
                        },
                    },
                    {
                        "type": "text",
                        "from": {"data": "paths"},
                        "encode": {
                            "update": {
                                "x": {"signal": "width * 0.86"},
                                "y": {"scale": "y", "field": "row", "band": 0.5},
                                "text": {"signal": "sloMs"},
                                "align": {"value": "right"},
                                "fontSize": {"value": 11},
                                "fill": {"value": "#555"},
                            }
                        },
                    },
                    {
                        "type": "text",
                        "from": {"data": "paths"},
                        "encode": {
                            "update": {
                                "x": {"signal": "width"},
                                "y": {"scale": "y", "field": "row", "band": 0.5},
                                "text": {"field": "vsSlo"},
                                "align": {"value": "right"},
                                "fontSize": {"value": 11},
                                "fontWeight": {"value": "bold"},
                                "fill": {
                                    "signal": (
                                        "datum.vsSlo === 'ok' ? '#0a7a28' : '#b00020'"
                                    )
                                },
                            }
                        },
                    },
                ],
            },
        ],
    }
    vis_state = {
        "title": title,
        "type": "vega",
        "params": {
            "spec": compact(spec),
            "hideWarnings": True,
        },
        "aggs": [],
    }
    return _visualization(
        title=title, data_view=data_view, vis_state=vis_state, query=query
    )


def _vega_header_text(field: str, x: str | dict[str, Any]) -> dict[str, Any]:
    encode: dict[str, Any] = {
        "y": {"value": 14},
        "text": {"field": field},
        "fontWeight": {"value": "bold"},
        "fontSize": {"value": 11},
        "fill": {"value": "#333"},
    }
    if isinstance(x, dict):
        encode["x"] = x
    else:
        encode["x"] = {"signal": x}
    return {
        "type": "text",
        "from": {"data": "header"},
        "encode": {"update": encode},
    }


def _vega_row_text(
    *,
    field: str | None = None,
    signal: str | None = None,
    x: str | dict[str, Any],
    align: str | None = None,
    fill: str | dict[str, Any] = "#111",
    limit: str | None = None,
    font_weight: str | None = None,
) -> dict[str, Any]:
    encode: dict[str, Any] = {
        "y": {"scale": "y", "field": "row", "band": 0.5},
        "fontSize": {"value": 11},
        "baseline": {"value": "middle"},
    }
    if isinstance(x, dict):
        encode["x"] = x
    else:
        encode["x"] = {"signal": x}
    if field is not None:
        encode["text"] = {"field": field}
    if signal is not None:
        encode["text"] = {"signal": signal}
    if align is not None:
        encode["align"] = {"value": align}
    if isinstance(fill, dict):
        encode["fill"] = fill
    else:
        encode["fill"] = {"value": fill}
    if limit is not None:
        encode["limit"] = {"signal": limit}
    if font_weight is not None:
        encode["fontWeight"] = {"value": font_weight}
    return {
        "type": "text",
        "from": {"data": "rows"},
        "encode": {"update": encode},
    }


def _vega_row_link(
    *,
    label: str,
    href_field: str,
    x_signal: str,
    width_signal: str = "width * 0.07",
) -> list[dict[str, Any]]:
    """Clickable link: wide hit rect + label (OSD needs enableExternalUrls)."""
    return [
        {
            "type": "rect",
            "from": {"data": "rows"},
            "encode": {
                "enter": {
                    "fill": {"value": "transparent"},
                    "cursor": {"value": "pointer"},
                },
                "update": {
                    "x": {"signal": x_signal},
                    "y": {
                        "scale": "y",
                        "field": "row",
                        "band": 0,
                    },
                    "width": {"signal": width_signal},
                    "height": {"scale": "y", "band": 1},
                    "href": {"field": href_field},
                    "tooltip": {
                        "signal": (
                            "{'open': '" + label + "', 'id': datum._id}"
                        )
                    },
                },
            },
        },
        {
            "type": "text",
            "from": {"data": "rows"},
            "encode": {
                "enter": {
                    "fill": {"value": "#006bb8"},
                    "fontWeight": {"value": "bold"},
                    "fontSize": {"value": 11},
                    "baseline": {"value": "middle"},
                    "cursor": {"value": "pointer"},
                },
                "update": {
                    "x": {"signal": f"({x_signal}) + 2"},
                    "y": {"scale": "y", "field": "row", "band": 0.5},
                    "text": {"value": label},
                    "href": {"field": href_field},
                },
            },
        },
    ]


def log_signal_stream_visualization(
    *,
    title: str,
    data_view: str,
    query: str = LOG_SIGNAL_LUCENE,
    size: int = 40,
) -> dict[str, Any]:
    """Signal stream with per-row Discover doc / surrounding links (no expand)."""
    # Classic Discover app owns single-doc + surrounding views.
    # `/app/data-explorer/discover/#/doc|context/...` silently falls back to the
    # search list (no Table/JSON doc view). Use `/app/discover#/...` instead.
    #   single:  #/doc/<indexPattern>/<index>?id=<docId>
    #   surround:#/context/<indexPattern>/<docId>
    doc_base = f"/app/discover#/doc/{LOGS_VIEW}/"
    ctx_prefix = f"/app/discover#/context/{LOGS_VIEW}/"
    # Prefer dated indices; bare otel-v1-apm-logs lacks observedTimestamp mapping.
    index_pattern = "otel-v1-apm-logs-*"
    spec = {
        "$schema": "https://vega.github.io/schema/vega/v5.json",
        "padding": 8,
        "autosize": {"type": "fit", "contains": "padding"},
        "data": [
            {
                "name": "rows",
                "url": {
                    "%context%": True,
                    "%timefield%": LOGS_TIME_FIELD,
                    "index": index_pattern,
                    "body": {
                        "size": size,
                        "sort": [{LOGS_TIME_FIELD: {"order": "desc"}}],
                        "_source": [
                            LOGS_TIME_FIELD,
                            "name",
                            LOG_APPLICATION_FIELD,
                            "severityText",
                            "method",
                            "path",
                            "status",
                            "duration_ms",
                            "body",
                        ],
                    },
                },
                "format": {"property": "hits.hits"},
                "transform": [
                    {
                        "type": "formula",
                        "as": "ts",
                        "expr": (
                            "datum._source.observedTimestamp ? "
                            "slice(datum._source.observedTimestamp, 11, 19) : ''"
                        ),
                    },
                    {
                        "type": "formula",
                        "as": "ns",
                        "expr": "datum._source.name || ''",
                    },
                    {
                        "type": "formula",
                        "as": "app",
                        "expr": "datum._source.serviceName || ''",
                    },
                    {
                        "type": "formula",
                        "as": "sev",
                        "expr": "datum._source.severityText || ''",
                    },
                    {
                        "type": "formula",
                        "as": "method",
                        "expr": "datum._source.method || ''",
                    },
                    {
                        "type": "formula",
                        "as": "path",
                        "expr": "datum._source.path || datum._source.body || ''",
                    },
                    {
                        "type": "formula",
                        "as": "status",
                        "expr": (
                            "datum._source.status == null ? '' : "
                            "datum._source.status"
                        ),
                    },
                    {
                        "type": "formula",
                        "as": "dur",
                        "expr": (
                            "datum._source.duration_ms == null ? '' : "
                            "datum._source.duration_ms"
                        ),
                    },
                    {
                        "type": "formula",
                        "as": "docUrl",
                        "expr": (
                            f"'{doc_base}' + datum._index + '?id=' + datum._id"
                        ),
                    },
                    {
                        "type": "formula",
                        "as": "ctxUrl",
                        "expr": f"'{ctx_prefix}' + datum._id",
                    },
                    {
                        "type": "window",
                        "ops": ["row_number"],
                        "as": ["row"],
                        "sort": [
                            {
                                "field": "_source.observedTimestamp",
                                "order": "descending",
                            }
                        ],
                    },
                ],
            },
            {
                "name": "header",
                "values": [
                    {
                        "ts": "time",
                        "ns": "ns",
                        "app": "app",
                        "sev": "sev",
                        "method": "method",
                        "path": "path",
                        "status": "status",
                        "dur": "ms",
                        "doc": "single doc",
                        "ctx": "surrounding",
                        "row": 0,
                    }
                ],
            },
        ],
        "scales": [
            {
                "name": "y",
                "type": "band",
                "domain": {"data": "rows", "field": "row"},
                "range": {"step": 20},
                "padding": 0.05,
            }
        ],
        "marks": [
            {
                "type": "group",
                "encode": {
                    "update": {
                        "x": {"value": 0},
                        "y": {"value": 0},
                        "width": {"signal": "width"},
                        "height": {"signal": "22"},
                    }
                },
                "marks": [
                    _vega_header_text("ts", {"value": 0}),
                    _vega_header_text("ns", "width * 0.09"),
                    _vega_header_text("app", "width * 0.20"),
                    _vega_header_text("sev", "width * 0.30"),
                    _vega_header_text("method", "width * 0.36"),
                    _vega_header_text("path", "width * 0.42"),
                    _vega_header_text("status", "width * 0.68"),
                    _vega_header_text("dur", "width * 0.74"),
                    _vega_header_text("doc", "width * 0.82"),
                    _vega_header_text("ctx", "width * 0.92"),
                ],
            },
            {
                "type": "group",
                "encode": {
                    "update": {
                        "y": {"value": 22},
                        "width": {"signal": "width"},
                        "height": {"signal": "height - 22"},
                    }
                },
                "marks": [
                    _vega_row_text(field="ts", x={"value": 0}),
                    _vega_row_text(field="ns", x="width * 0.09", limit="width * 0.10"),
                    _vega_row_text(field="app", x="width * 0.20", limit="width * 0.09"),
                    _vega_row_text(
                        field="sev",
                        x="width * 0.30",
                        fill={
                            "signal": (
                                "datum.sev === 'ERROR' || datum.sev === 'FATAL' "
                                "? '#b00020' : datum.sev === 'WARN' "
                                "? '#a15c00' : '#111'"
                            )
                        },
                    ),
                    _vega_row_text(field="method", x="width * 0.36"),
                    _vega_row_text(
                        field="path", x="width * 0.42", limit="width * 0.24"
                    ),
                    _vega_row_text(
                        field="status",
                        x="width * 0.68",
                        fill={
                            "signal": (
                                "datum.status >= 500 ? '#b00020' : "
                                "datum.status >= 400 ? '#a15c00' : "
                                "datum.status >= 200 ? '#0a7a28' : '#111'"
                            )
                        },
                    ),
                    _vega_row_text(field="dur", x="width * 0.74"),
                    *_vega_row_link(
                        label="doc",
                        href_field="docUrl",
                        x_signal="width * 0.82",
                    ),
                    *_vega_row_link(
                        label="around",
                        href_field="ctxUrl",
                        x_signal="width * 0.91",
                    ),
                ],
            },
        ],
    }
    vis_state = {
        "title": title,
        "type": "vega",
        "params": {
            "spec": compact(spec),
            "hideWarnings": True,
        },
        "aggs": [],
    }
    return _visualization(
        title=title, data_view=data_view, vis_state=vis_state, query=query
    )


def log_avg_metric_visualization(
    *,
    title: str,
    data_view: str,
    field: str,
    query: str,
) -> dict[str, Any]:
    """Single-number average metric (e.g. avg duration_ms)."""
    vis_state = {
        "title": title,
        "type": "metric",
        "params": {
            "addTooltip": True,
            "addLegend": False,
            "type": "metric",
            "metric": {
                "percentageMode": False,
                "useRanges": False,
                "colorSchema": "Green to Red",
                "metricColorMode": "None",
                "colorsRange": [{"from": 0, "to": 10000}],
                "labels": {"show": True},
                "invertColors": False,
                "style": {
                    "bgFill": 0.0,
                    "bgColor": False,
                    "labelColor": False,
                    "subText": "",
                    "fontSize": 48,
                },
            },
        },
        "aggs": [
            {
                "id": "1",
                "enabled": True,
                "type": "avg",
                "schema": "metric",
                "params": {"field": field, "customLabel": "avg duration_ms"},
            }
        ],
    }
    return _visualization(
        title=title, data_view=data_view, vis_state=vis_state, query=query
    )


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
    query: str = LOG_SIGNAL_LUCENE,
    filters: list[dict[str, Any]] | None = None,
) -> tuple[str, str, dict[str, Any]]:
    panel_json: list[dict[str, Any]] = []
    references: list[dict[str, str]] = []
    for position, (object_type, object_id, x, y, width, height) in enumerate(panels):
        panel_ref = f"{panel_ref_prefix}_{position}"
        # Use object_id as grid i/panelIndex so geometry updates stick to the
        # panel identity (position-based "1"/"2"/… can leave OSD showing a
        # stale layout after overwrite imports).
        panel_json.append(
            {
                "version": "2.19.6",
                "type": object_type,
                "gridData": {
                    "x": x,
                    "y": y,
                    "w": width,
                    "h": height,
                    "i": object_id,
                },
                "panelIndex": object_id,
                "embeddableConfig": {},
                "panelRefName": panel_ref,
            }
        )
        references.append({"name": panel_ref, "type": object_type, "id": object_id})
    dash_filters = (
        log_signal_filters() if filters is None else filters
    )
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
                                "query": query,
                                "language": "lucene",
                            },
                            "filter": dash_filters,
                        }
                    )
                },
            },
            "references": references,
        },
    )


def _saved_search_scopes() -> list[tuple[str, str, dict[str, Any]]]:
    """Discover → Open: Signal / HTTP / Errors / Auth / BFF / Runtime noise."""
    # logs-explore-stream is the canonical "Logs / Signal" (dashboard + Discover).
    scopes: list[
        tuple[str, str, str, list[str], list[dict[str, Any]] | None]
    ] = [
        ("logs-http", "Logs / HTTP", LOG_HTTP_LUCENE, LOG_HTTP_COLUMNS, None),
        ("logs-errors", "Logs / Errors", LOG_ERRORS_LUCENE, LOG_STREAM_COLUMNS, None),
        ("logs-auth", "Logs / Auth", LOG_AUTH_LUCENE, LOG_STREAM_COLUMNS, None),
        ("logs-bff", "Logs / BFF", LOG_BFF_LUCENE, LOG_STREAM_COLUMNS, None),
        (
            "logs-runtime-noise",
            "Logs / Runtime noise",
            LOG_RUNTIME_NOISE_LUCENE,
            LOG_STREAM_COLUMNS,
            [],  # no hide pills — this view *selects* rare lifecycle/config
        ),
    ]
    objects: list[tuple[str, str, dict[str, Any]]] = []
    for object_id, title, query, columns, filters in scopes:
        objects.append(
            (
                "search",
                object_id,
                saved_search(
                    title=title,
                    data_view=LOGS_VIEW,
                    time_field=LOGS_TIME_FIELD,
                    columns=columns,
                    query=query,
                    filters=filters,
                ),
            )
        )
    return objects


def _logs_explore_bundle() -> list[tuple[str, str, dict[str, Any]]]:
    """Dashboard companion + Discover saved-search pack + HTTP triage panels."""
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
                title="Log volume (signal) — click bar to zoom time",
                data_view=LOGS_VIEW,
                time_field=LOGS_TIME_FIELD,
            ),
        ),
        (
            "visualization",
            "logs-http-top-paths",
            log_http_top_paths_visualization(
                title=f"Top paths (HTTP) — RPS + p95 vs {HTTP_P95_SLO_MS}ms SLO",
                data_view=LOGS_VIEW,
                query=LOG_HTTP_LUCENE,
                size=10,
                slo_ms=HTTP_P95_SLO_MS,
            ),
        ),
        (
            "visualization",
            "logs-http-status-codes",
            log_terms_table_visualization(
                title="Status codes (HTTP)",
                data_view=LOGS_VIEW,
                field=LOG_STATUS_FIELD,
                query=LOG_HTTP_LUCENE,
                size=10,
                field_label="status",
            ),
        ),
        (
            "visualization",
            "logs-http-status-codes-pie",
            log_terms_pie_visualization(
                title="Status codes % (HTTP)",
                data_view=LOGS_VIEW,
                field=LOG_STATUS_FIELD,
                query=LOG_HTTP_LUCENE,
                size=10,
                field_label="status",
            ),
        ),
        (
            "visualization",
            "logs-http-avg-duration",
            log_avg_metric_visualization(
                title="Avg duration_ms (HTTP)",
                data_view=LOGS_VIEW,
                field=LOG_DURATION_FIELD,
                query=LOG_HTTP_LUCENE,
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
        (
            "visualization",
            "logs-signal-stream",
            log_signal_stream_visualization(
                title="Signal stream — doc + surrounding on each row",
                data_view=LOGS_VIEW,
                query=LOG_SIGNAL_LUCENE,
                size=40,
            ),
        ),
    ]
    objects.extend(_saved_search_scopes())
    objects.append(
        assemble_dashboard(
            dashboard_id="logs-explore",
            title="Logs",
            description=(
                "Companion overview with HTTP triage (top paths, status table + "
                "pie, avg latency) and a signal stream with per-row Discover "
                "doc/surrounding links. Open Discover for the field sidebar and "
                "saved searches (Signal / HTTP / Errors / Auth / BFF / Runtime "
                "noise). Epoll and memory are dropped at the collector; rare "
                "lifecycle/config noise is selectable via Runtime noise. "
                f"Managed by {MANAGED_BY}"
            ),
            panels=[
                ("visualization", "logs-explore-discover-guide", 0, 0, 48, 7),
                ("visualization", "logs-explore-histogram", 0, 7, 48, 10),
                ("visualization", "logs-http-top-paths", 0, 17, 28, 14),
                # Mid column: status table full height. Right: avg + donut stacked.
                ("visualization", "logs-http-status-codes", 28, 17, 10, 14),
                ("visualization", "logs-http-avg-duration", 38, 17, 10, 7),
                ("visualization", "logs-http-status-codes-pie", 38, 24, 10, 7),
                ("visualization", "logs-signal-stream", 0, 31, 48, 24),
            ],
            panel_ref_prefix="logs_explore",
            time_from="now-15m",
            refresh_ms=30000,
        )
    )
    return objects


# ---------------------------------------------------------------------------
# DataPersistence — Lifeguard Postgres (primary + replicas) / Redis
# ---------------------------------------------------------------------------

METRICS_VIEW = "shared-observability-metrics"
METRICS_TIME_FIELD = "time"
METRICS_VALUE_FIELD = "value"
METRICS_NAME_KEYWORD = "name.keyword"
METRICS_DATNAME_KEYWORD = "metric.attributes.datname.keyword"
METRICS_CONSUMER_NS_KEYWORD = "metric.attributes.consumer_namespace.keyword"
METRICS_SLOT_KEYWORD = "metric.attributes.slot_name.keyword"
METRICS_CLIENT_ADDR_KEYWORD = "metric.attributes.client_addr.keyword"
METRICS_STATE_KEYWORD = "metric.attributes.state.keyword"
METRICS_SERVER_KEYWORD = "metric.attributes.server.keyword"
METRICS_NODE_KEYWORD = "metric.attributes.node.keyword"
METRICS_NAMESPACE_KEYWORD = "metric.attributes.namespace.keyword"
METRICS_POD_KEYWORD = "metric.attributes.pod.keyword"
METRICS_PHASE_KEYWORD = "metric.attributes.phase.keyword"
METRICS_CONDITION_KEYWORD = "metric.attributes.condition.keyword"
METRICS_STATUS_KEYWORD = "metric.attributes.status.keyword"
METRICS_DEPLOYMENT_KEYWORD = "metric.attributes.deployment.keyword"
METRICS_DAEMONSET_KEYWORD = "metric.attributes.daemonset.keyword"
METRICS_PLATFORM_COMPONENT_KEYWORD = "metric.attributes.platform_component.keyword"

K3S_DEV_DASHBOARD_ID = "k3s-dev"
K3S_NODE_SPLIT_FIELD = METRICS_NODE_KEYWORD
K3S_LUCENE = (
    f'{METRICS_NAME_KEYWORD}: (node_* OR kube_*) AND '
    f'metric.attributes.platform_component: k3s'
)
K3S_NODE_LUCENE = (
    f'{METRICS_NAME_KEYWORD}: (node_load1 OR node_load5 OR node_load15 OR '
    f'node_memory_MemAvailable_bytes OR node_memory_MemTotal_bytes OR '
    f'node_filesystem_avail_bytes OR node_filesystem_size_bytes OR '
    f'node_network_receive_bytes_total OR node_network_transmit_bytes_total OR '
    f'node_uname_info) AND metric.attributes.platform_component: k3s'
)
K3S_KUBE_LUCENE = (
    f'{METRICS_NAME_KEYWORD}: (kube_node_info OR kube_node_status_condition OR '
    f'kube_pod_status_phase OR kube_pod_container_status_restarts_total OR '
    f'kube_deployment_status_replicas_unavailable OR '
    f'kube_deployment_status_replicas_available OR '
    f'kube_daemonset_status_number_unavailable) AND '
    f'metric.attributes.platform_component: k3s'
)

METRICS_COLUMNS = [
    "time",
    "name",
    "value",
    "serviceName",
    "metric.attributes.platform_component",
    "metric.attributes.server",
    "metric.attributes.client_addr",
    "metric.attributes.slot_name",
    "metric.attributes.state",
    "metric.attributes.datname",
    "metric.attributes.consumer_namespace",
]

PG_CONNECTIONS_LUCENE = (
    f'{METRICS_NAME_KEYWORD}: ("pg_stat_database_numbackends" OR '
    f'"pg_settings_max_connections" OR "pg_stat_activity_count")'
)
PG_REPLICATION_LUCENE = (
    f'{METRICS_NAME_KEYWORD}: ("pg_up" OR "pg_replication_is_replica" OR '
    f'"pg_replication_lag_seconds" OR '
    f'"pg_stat_replication_pg_wal_lsn_diff")'
)
PG_SIZE_LUCENE = f'{METRICS_NAME_KEYWORD}: "pg_database_size_bytes"'
REDIS_LUCENE = f"{METRICS_NAME_KEYWORD}: redis_*"
DATA_PLATFORM_LUCENE = (
    f"({PG_CONNECTIONS_LUCENE}) OR ({PG_REPLICATION_LUCENE}) OR "
    f"({PG_SIZE_LUCENE}) OR ({REDIS_LUCENE})"
)
DB_PRESSURE_LOGS_LUCENE = (
    "body: (*connection* OR *pool* OR *postgres* OR *redis* OR *timeout* OR "
    "*replication* OR *replica*)"
)


def _metrics_discover_route(query: str) -> str:
    return (
        "/app/data-explorer/discover/#/?"
        "_g=(filters:!(),refreshInterval:(pause:!f,value:30000),time:(from:now-15m,to:now))"
        "&_a=(discover:(columns:!("
        + ",".join(METRICS_COLUMNS)
        + f"),interval:auto,sort:!(!({METRICS_TIME_FIELD},desc))),"
        "metadata:(indexPattern:shared-observability-metrics,view:discover))"
        "&_q=(filters:!(),query:(language:lucene,query:'"
        + _url_encode_lucene(query)
        + "'))"
    )


def data_persistence_guide_markdown() -> dict[str, Any]:
    """Banner: Discover scopes for Postgres primary/replicas + Redis."""
    markdown = (
        "## DataPersistence — Postgres primary + replicas, Redis\n\n"
        "Topology: Lifeguard `postgres-primary` + `postgres-replica-{0,1}` "
        "(no Pgpool). Exporter scrapes the primary Service; replica health is "
        "visible via `pg_stat_replication_*` streaming rows.\n\n"
        f"[**Open metrics (all)**]({_metrics_discover_route(DATA_PLATFORM_LUCENE)}) — "
        "Postgres + Redis gauges.\n"
        f"[**Open replication**]({_metrics_discover_route(PG_REPLICATION_LUCENE)}) — "
        "`pg_up`, is_replica, WAL lag bytes per standby.\n"
        f"[**Open Redis**]({_metrics_discover_route(REDIS_LUCENE)}) — "
        "clients, memory, keyspace.\n\n"
        "### What to watch\n"
        "1. **`pg_up`** — exporter scrape of primary = 1\n"
        "2. **`pg_replication_is_replica`** — primary scrape should stay **0**\n"
        "3. **Streaming replicas** — two `client_addr` rows in "
        "`pg_stat_replication_pg_wal_lsn_diff`, state `streaming`, lag ≈ 0\n"
        "4. **DB backends** — `pg_stat_database_numbackends` by `datname`\n"
        "5. **Redis** — connected clients + memory used\n\n"
        "### Saved searches (Discover → Open)\n"
        "- **DataPersistence / Platform metrics**\n"
        "- **DataPersistence / Postgres connections**\n"
        "- **DataPersistence / Replication**\n"
        "- **DataPersistence / Redis**\n"
        "- **DataPersistence / DB pressure logs** (log index)\n\n"
        "Scraped via OTel `prometheus/data` → `postgres-exporter:9187` + "
        "`redis-metrics` → Data Prepper → `otel-v1-apm-metrics*`. "
        "Managed by shared-gitops-k8s-cluster."
    )
    vis_state = {
        "title": "DataPersistence guide",
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
            "title": "DataPersistence guide",
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


def metrics_value_metric_visualization(
    *,
    title: str,
    query: str,
    agg: str = "avg",
    custom_label: str | None = None,
) -> dict[str, Any]:
    """Single-number gauge from metric `value` (avg/max/sum).

    Warning: ``sum`` over a dashboard time range totals *every scrape
    datapoint*, not the live gauge. Prefer
    ``metrics_cardinality_metric_visualization`` (distinct series) or
    ``metrics_instant_sum_vega`` (latest value per series, then sum).
    """
    vis_state = {
        "title": title,
        "type": "metric",
        "params": {
            "addTooltip": True,
            "addLegend": False,
            "type": "metric",
            "metric": {
                "percentageMode": False,
                "useRanges": False,
                "colorSchema": "Green to Red",
                "metricColorMode": "None",
                "colorsRange": [{"from": 0, "to": 10000}],
                "labels": {"show": True},
                "invertColors": False,
                "style": {
                    "bgFill": 0.0,
                    "bgColor": False,
                    "labelColor": False,
                    "subText": "",
                    "fontSize": 40,
                },
            },
        },
        "aggs": [
            {
                "id": "1",
                "enabled": True,
                "type": agg,
                "schema": "metric",
                "params": {
                    "field": METRICS_VALUE_FIELD,
                    "customLabel": custom_label or title,
                },
            }
        ],
    }
    return _visualization(
        title=title,
        data_view=METRICS_VIEW,
        vis_state=vis_state,
        query=query,
        filters=[],
    )


def metrics_cardinality_metric_visualization(
    *,
    title: str,
    query: str,
    field: str,
    custom_label: str | None = None,
) -> dict[str, Any]:
    """Count distinct series keys matching the query (not sum of scrapes)."""
    vis_state = {
        "title": title,
        "type": "metric",
        "params": {
            "addTooltip": True,
            "addLegend": False,
            "type": "metric",
            "metric": {
                "percentageMode": False,
                "useRanges": False,
                "colorSchema": "Green to Red",
                "metricColorMode": "None",
                "colorsRange": [{"from": 0, "to": 10000}],
                "labels": {"show": True},
                "invertColors": False,
                "style": {
                    "bgFill": 0.0,
                    "bgColor": False,
                    "labelColor": False,
                    "subText": "",
                    "fontSize": 40,
                },
            },
        },
        "aggs": [
            {
                "id": "1",
                "enabled": True,
                "type": "cardinality",
                "schema": "metric",
                "params": {
                    "field": field,
                    "customLabel": custom_label or title,
                },
            }
        ],
    }
    return _visualization(
        title=title,
        data_view=METRICS_VIEW,
        vis_state=vis_state,
        query=query,
        filters=[],
    )


def metrics_cardinality_table_visualization(
    *,
    title: str,
    query: str,
    bucket_field: str,
    cardinality_field: str,
    size: int = 10,
    bucket_label: str | None = None,
    metric_label: str = "count",
) -> dict[str, Any]:
    """Distinct-series count broken down by a terms bucket."""
    bucket_params: dict[str, Any] = {
        "field": bucket_field,
        "size": size,
        "order": "desc",
        "orderBy": "1",
        "otherBucket": False,
        "otherBucketLabel": "Other",
        "missingBucket": False,
        "missingBucketLabel": "Missing",
    }
    if bucket_label:
        bucket_params["customLabel"] = bucket_label
    vis_state = {
        "title": title,
        "type": "table",
        "params": {
            "perPage": size,
            "showPartialRows": False,
            "showMeticsAtAllLevels": False,
            "sort": {"columnIndex": None, "direction": None},
            "showTotal": False,
            "showToolbar": False,
            "totalFunc": "sum",
            "percentageCol": "",
        },
        "aggs": [
            {
                "id": "1",
                "enabled": True,
                "type": "cardinality",
                "schema": "metric",
                "params": {
                    "field": cardinality_field,
                    "customLabel": metric_label,
                },
            },
            {
                "id": "2",
                "enabled": True,
                "type": "terms",
                "schema": "bucket",
                "params": bucket_params,
            },
        ],
    }
    return _visualization(
        title=title,
        data_view=METRICS_VIEW,
        vis_state=vis_state,
        query=query,
        filters=[],
    )


def metrics_instant_sum_vega(
    *,
    title: str,
    metric_name: str,
    series_field: str,
    extra_filters: list[dict[str, Any]] | None = None,
    series_size: int = 200,
    custom_label: str = "now",
) -> dict[str, Any]:
    """Sum of the latest gauge value per series (Prometheus-style instant).

    Classic metric ``sum`` over the time picker adds every scrape sample and
    looks "cumulative". This takes ``top_metrics`` per series key, then sums.
    """
    filters: list[dict[str, Any]] = [
        {"range": {METRICS_TIME_FIELD: {"%timefilter%": True}}},
        {"term": {METRICS_NAME_KEYWORD: metric_name}},
        {"term": {METRICS_PLATFORM_COMPONENT_KEYWORD: "k3s"}},
    ]
    if extra_filters:
        filters.extend(extra_filters)
    url = {
        "index": "otel-v1-apm-metrics*",
        "body": {
            "size": 0,
            "query": {"bool": {"filter": filters}},
            "aggs": {
                "series": {
                    "terms": {"field": series_field, "size": series_size},
                    "aggs": {
                        "latest": {
                            "top_metrics": {
                                "metrics": {"field": METRICS_VALUE_FIELD},
                                "sort": {METRICS_TIME_FIELD: "desc"},
                                "size": 1,
                            }
                        }
                    },
                }
            },
        },
    }
    spec = {
        "$schema": "https://vega.github.io/schema/vega/v5.json",
        "padding": 8,
        "autosize": {"type": "fit", "contains": "padding"},
        "data": [
            {
                "name": "series",
                "url": url,
                "format": {"property": "aggregations.series.buckets"},
                "transform": [
                    {
                        "type": "formula",
                        "as": "latest",
                        "expr": (
                            "datum.latest && datum.latest.top && "
                            "datum.latest.top[0] && "
                            "datum.latest.top[0].metrics && "
                            f"datum.latest.top[0].metrics['{METRICS_VALUE_FIELD}'] != null "
                            f"? datum.latest.top[0].metrics['{METRICS_VALUE_FIELD}'] : 0"
                        ),
                    },
                    {
                        "type": "aggregate",
                        "ops": ["sum"],
                        "fields": ["latest"],
                        "as": ["total"],
                    },
                ],
            }
        ],
        "marks": [
            {
                "type": "text",
                "from": {"data": "series"},
                "encode": {
                    "enter": {
                        "align": {"value": "center"},
                        "baseline": {"value": "middle"},
                        "fill": {"value": "#111"},
                        "fontSize": {"value": 40},
                        "fontWeight": {"value": "bold"},
                        "text": {
                            "signal": (
                                f"format(datum.total, ',.0f') + ' {custom_label}'"
                            )
                        },
                    },
                    "update": {
                        "x": {"signal": "width / 2"},
                        "y": {"signal": "height / 2"},
                    },
                },
            }
        ],
    }
    vis_state = {
        "title": title,
        "type": "vega",
        "params": {"spec": compact(spec), "hideWarnings": True},
        "aggs": [],
    }
    return _visualization(
        title=title,
        data_view=METRICS_VIEW,
        vis_state=vis_state,
        query="",
        filters=[],
    )


def metrics_line_visualization(
    *,
    title: str,
    query: str,
    split_field: str | None = None,
    split_size: int = 8,
    y_label: str = "value",
) -> dict[str, Any]:
    """Time series of avg(value), optionally split by a keyword attribute."""
    aggs: list[dict[str, Any]] = [
        {
            "id": "1",
            "enabled": True,
            "type": "avg",
            "schema": "metric",
            "params": {"field": METRICS_VALUE_FIELD, "customLabel": y_label},
        },
        {
            "id": "2",
            "enabled": True,
            "type": "date_histogram",
            "schema": "segment",
            "params": {
                "field": METRICS_TIME_FIELD,
                "interval": "auto",
                "min_doc_count": 1,
                "extended_bounds": {},
            },
        },
    ]
    if split_field:
        aggs.append(
            {
                "id": "3",
                "enabled": True,
                "type": "terms",
                "schema": "group",
                "params": {
                    "field": split_field,
                    "size": split_size,
                    "order": "desc",
                    "orderBy": "1",
                    "otherBucket": False,
                    "otherBucketLabel": "Other",
                    "missingBucket": False,
                    "missingBucketLabel": "Missing",
                },
            }
        )
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
                    "labels": {
                        "show": True,
                        "rotate": 0,
                        "filter": False,
                        "truncate": 100,
                    },
                    "title": {"text": y_label},
                }
            ],
            "seriesParams": [
                {
                    "show": True,
                    "type": "line",
                    "mode": "normal",
                    "data": {"label": y_label, "id": "1"},
                    "valueAxis": "ValueAxis-1",
                    "drawLinesBetweenPoints": True,
                    "showCircles": True,
                    "interpolate": "linear",
                }
            ],
            "addTooltip": True,
            "addLegend": bool(split_field),
            "legendPosition": "right",
            "times": [],
            "addTimeMarker": False,
        },
        "aggs": aggs,
    }
    return _visualization(
        title=title,
        data_view=METRICS_VIEW,
        vis_state=vis_state,
        query=query,
        filters=[],
    )


def metrics_terms_table_visualization(
    *,
    title: str,
    query: str,
    field: str,
    size: int = 10,
    field_label: str | None = None,
    value_agg: str = "avg",
    value_label: str | None = None,
) -> dict[str, Any]:
    """Value agg by terms bucket (replicas, databases, …).

    Prefer ``value_agg=\"max\"`` for Prometheus gauges/counters so the cell
    reflects the latest-ish magnitude rather than a time-range average.
    """
    bucket_params: dict[str, Any] = {
        "field": field,
        "size": size,
        "order": "desc",
        "orderBy": "1",
        "otherBucket": False,
        "otherBucketLabel": "Other",
        "missingBucket": False,
        "missingBucketLabel": "Missing",
    }
    if field_label:
        bucket_params["customLabel"] = field_label
    vis_state = {
        "title": title,
        "type": "table",
        "params": {
            "perPage": size,
            "showPartialRows": False,
            "showMeticsAtAllLevels": False,
            "sort": {"columnIndex": None, "direction": None},
            "showTotal": False,
            "showToolbar": False,
            "totalFunc": "sum",
            "percentageCol": "",
        },
        "aggs": [
            {
                "id": "1",
                "enabled": True,
                "type": value_agg,
                "schema": "metric",
                "params": {
                    "field": METRICS_VALUE_FIELD,
                    "customLabel": value_label or f"{value_agg} value",
                },
            },
            {
                "id": "2",
                "enabled": True,
                "type": "terms",
                "schema": "bucket",
                "params": bucket_params,
            },
        ],
    }
    return _visualization(
        title=title,
        data_view=METRICS_VIEW,
        vis_state=vis_state,
        query=query,
        filters=[],
    )


def _metrics_vega_url(*, metric_name: str, aggs: dict[str, Any]) -> dict[str, Any]:
    """Vega ES data URL with an explicit metric filter.

    OSD forbids ``%context%`` / ``%timefield%`` when ``body.query`` is set.
    Use ``%timefilter%`` on the metrics time field instead.
    """
    return {
        "index": "otel-v1-apm-metrics*",
        "body": {
            "size": 0,
            "query": {
                "bool": {
                    "filter": [
                        {
                            "range": {
                                METRICS_TIME_FIELD: {"%timefilter%": True}
                            }
                        },
                        {"term": {METRICS_NAME_KEYWORD: metric_name}},
                    ]
                }
            },
            "aggs": aggs,
        },
    }


def metrics_streaming_replicas_vega(
    *,
    title: str = "Streaming replicas — WAL lag by client_addr",
) -> dict[str, Any]:
    """Table of standby WAL receivers: client_addr × state × slot × lag bytes."""
    spec = {
        "$schema": "https://vega.github.io/schema/vega/v5.json",
        "padding": 8,
        "autosize": {"type": "fit", "contains": "padding"},
        "data": [
            {
                "name": "replicas",
                "url": _metrics_vega_url(
                    metric_name="pg_stat_replication_pg_wal_lsn_diff",
                    aggs={
                        "clients": {
                            "terms": {
                                "field": METRICS_CLIENT_ADDR_KEYWORD,
                                "size": 10,
                            },
                            "aggs": {
                                "lag": {"avg": {"field": METRICS_VALUE_FIELD}},
                                "state": {
                                    "terms": {
                                        "field": METRICS_STATE_KEYWORD,
                                        "size": 1,
                                    }
                                },
                                "slot": {
                                    "terms": {
                                        "field": METRICS_SLOT_KEYWORD,
                                        "size": 1,
                                    }
                                },
                            },
                        }
                    },
                ),
                "format": {"property": "aggregations.clients.buckets"},
                "transform": [
                    {
                        "type": "formula",
                        "as": "client",
                        "expr": "datum.key",
                    },
                    {
                        "type": "formula",
                        "as": "lag",
                        "expr": "datum.lag.value",
                    },
                    {
                        "type": "formula",
                        "as": "state",
                        "expr": (
                            "datum.state.buckets && length(datum.state.buckets) "
                            "? datum.state.buckets[0].key : '—'"
                        ),
                    },
                    {
                        "type": "formula",
                        "as": "slot",
                        "expr": (
                            "datum.slot.buckets && length(datum.slot.buckets) "
                            "? datum.slot.buckets[0].key : '—'"
                        ),
                    },
                    {
                        "type": "window",
                        "ops": ["row_number"],
                        "as": ["row"],
                        "sort": [{"field": "client", "order": "ascending"}],
                    },
                ],
            },
            {
                "name": "header",
                "values": [
                    {
                        "client": "client_addr",
                        "state": "state",
                        "slot": "slot",
                        "lag": "WAL lag (bytes)",
                        "row": 0,
                    }
                ],
            },
        ],
        "scales": [
            {
                "name": "y",
                "type": "band",
                "domain": {"data": "replicas", "field": "row"},
                "range": {"step": 24},
                "padding": 0.1,
            }
        ],
        "marks": [
            {
                "type": "group",
                "encode": {
                    "update": {
                        "x": {"value": 0},
                        "y": {"value": 0},
                        "width": {"signal": "width"},
                        "height": {"value": 22},
                    }
                },
                "marks": [
                    {
                        "type": "text",
                        "from": {"data": "header"},
                        "encode": {
                            "update": {
                                "x": {"value": 0},
                                "y": {"value": 14},
                                "text": {"field": "client"},
                                "fontWeight": {"value": "bold"},
                                "fontSize": {"value": 11},
                                "fill": {"value": "#333"},
                            }
                        },
                    },
                    {
                        "type": "text",
                        "from": {"data": "header"},
                        "encode": {
                            "update": {
                                "x": {"signal": "width * 0.38"},
                                "y": {"value": 14},
                                "text": {"field": "state"},
                                "fontWeight": {"value": "bold"},
                                "fontSize": {"value": 11},
                                "fill": {"value": "#333"},
                            }
                        },
                    },
                    {
                        "type": "text",
                        "from": {"data": "header"},
                        "encode": {
                            "update": {
                                "x": {"signal": "width * 0.58"},
                                "y": {"value": 14},
                                "text": {"field": "slot"},
                                "fontWeight": {"value": "bold"},
                                "fontSize": {"value": 11},
                                "fill": {"value": "#333"},
                            }
                        },
                    },
                    {
                        "type": "text",
                        "from": {"data": "header"},
                        "encode": {
                            "update": {
                                "x": {"signal": "width"},
                                "y": {"value": 14},
                                "text": {"field": "lag"},
                                "align": {"value": "right"},
                                "fontWeight": {"value": "bold"},
                                "fontSize": {"value": 11},
                                "fill": {"value": "#333"},
                            }
                        },
                    },
                ],
            },
            # Offset body below the header row (same pattern as logs top-paths).
            # Without this, band scale row 1 starts at y=0 and overlaps the header.
            {
                "type": "group",
                "encode": {
                    "update": {
                        "y": {"value": 24},
                        "width": {"signal": "width"},
                        "height": {"signal": "height - 24"},
                    }
                },
                "marks": [
                    {
                        "type": "text",
                        "from": {"data": "replicas"},
                        "encode": {
                            "update": {
                                "x": {"value": 0},
                                "y": {"scale": "y", "field": "row", "band": 0.5},
                                "text": {"field": "client"},
                                "fontSize": {"value": 12},
                                "fill": {"value": "#111"},
                            }
                        },
                    },
                    {
                        "type": "text",
                        "from": {"data": "replicas"},
                        "encode": {
                            "update": {
                                "x": {"signal": "width * 0.38"},
                                "y": {"scale": "y", "field": "row", "band": 0.5},
                                "text": {"field": "state"},
                                "fontSize": {"value": 12},
                                "fontWeight": {"value": "bold"},
                                "fill": {
                                    "signal": (
                                        "datum.state === 'streaming' "
                                        "? '#0a7a28' : '#b00020'"
                                    )
                                },
                            }
                        },
                    },
                    {
                        "type": "text",
                        "from": {"data": "replicas"},
                        "encode": {
                            "update": {
                                "x": {"signal": "width * 0.58"},
                                "y": {"scale": "y", "field": "row", "band": 0.5},
                                "text": {"field": "slot"},
                                "fontSize": {"value": 12},
                                "fill": {"value": "#555"},
                            }
                        },
                    },
                    {
                        "type": "text",
                        "from": {"data": "replicas"},
                        "encode": {
                            "update": {
                                "x": {"signal": "width"},
                                "y": {"scale": "y", "field": "row", "band": 0.5},
                                "text": {
                                    "signal": (
                                        "datum.lag == null ? '—' : "
                                        "format(datum.lag, ',.0f')"
                                    )
                                },
                                "align": {"value": "right"},
                                "fontSize": {"value": 12},
                                "fill": {
                                    "signal": (
                                        "datum.lag > 0 ? '#b00020' : '#0a7a28'"
                                    )
                                },
                            }
                        },
                    },
                ],
            },
        ],
    }
    vis_state = {
        "title": title,
        "type": "vega",
        "params": {"spec": compact(spec), "hideWarnings": True},
        "aggs": [],
    }
    return _visualization(
        title=title,
        data_view=METRICS_VIEW,
        vis_state=vis_state,
        query=PG_REPLICATION_LUCENE,
        filters=[],
    )


def _data_persistence_bundle() -> list[tuple[str, str, dict[str, Any]]]:
    """Lifeguard Postgres primary + streaming replicas + Redis overview."""
    objects: list[tuple[str, str, dict[str, Any]]] = [
        ("visualization", "data-persistence-guide", data_persistence_guide_markdown()),
        (
            "visualization",
            "data-persistence-pg-up",
            metrics_value_metric_visualization(
                title="Postgres scrape up",
                query=f'{METRICS_NAME_KEYWORD}: "pg_up"',
                agg="max",
                custom_label="pg_up",
            ),
        ),
        (
            "visualization",
            "data-persistence-pg-max-connections",
            metrics_value_metric_visualization(
                title="Postgres max_connections",
                query=f'{METRICS_NAME_KEYWORD}: "pg_settings_max_connections"',
                agg="max",
                custom_label="max_connections",
            ),
        ),
        (
            "visualization",
            "data-persistence-is-replica",
            metrics_value_metric_visualization(
                title="Is replica (0=primary)",
                query=f'{METRICS_NAME_KEYWORD}: "pg_replication_is_replica"',
                agg="max",
                custom_label="is_replica",
            ),
        ),
        (
            "visualization",
            "data-persistence-redis-clients",
            metrics_value_metric_visualization(
                title="Redis connected clients",
                query=f'{METRICS_NAME_KEYWORD}: "redis_connected_clients"',
                agg="avg",
                custom_label="clients",
            ),
        ),
        (
            "visualization",
            "data-persistence-redis-memory",
            metrics_value_metric_visualization(
                title="Redis memory used (bytes)",
                query=f'{METRICS_NAME_KEYWORD}: "redis_memory_used_bytes"',
                agg="avg",
                custom_label="memory bytes",
            ),
        ),
        (
            "visualization",
            "data-persistence-streaming-replicas",
            metrics_streaming_replicas_vega(),
        ),
        (
            "visualization",
            "data-persistence-backends-table",
            metrics_terms_table_visualization(
                title="Backends by database (avg)",
                query=f'{METRICS_NAME_KEYWORD}: "pg_stat_database_numbackends"',
                field=METRICS_DATNAME_KEYWORD,
                size=12,
                field_label="datname",
            ),
        ),
        (
            "visualization",
            "data-persistence-replication-lag",
            metrics_line_visualization(
                title="Replica WAL lag bytes (by client_addr)",
                query=(
                    f'{METRICS_NAME_KEYWORD}: "pg_stat_replication_pg_wal_lsn_diff"'
                ),
                split_field=METRICS_CLIENT_ADDR_KEYWORD,
                y_label="lag bytes",
            ),
        ),
        (
            "visualization",
            "data-persistence-pg-backends",
            metrics_line_visualization(
                title="Postgres backends by database",
                query=f'{METRICS_NAME_KEYWORD}: "pg_stat_database_numbackends"',
                split_field=METRICS_DATNAME_KEYWORD,
                y_label="backends",
            ),
        ),
        (
            "visualization",
            "data-persistence-pg-activity",
            metrics_line_visualization(
                title="Postgres activity (idle + active)",
                query=(
                    f'{METRICS_NAME_KEYWORD}: "pg_stat_activity_count" AND '
                    '(metric.attributes.state: "idle" OR '
                    'metric.attributes.state: "active")'
                ),
                split_field=METRICS_DATNAME_KEYWORD,
                y_label="sessions",
            ),
        ),
        (
            "visualization",
            "data-persistence-pg-db-size",
            metrics_line_visualization(
                title="Database size bytes",
                query=PG_SIZE_LUCENE,
                split_field=METRICS_DATNAME_KEYWORD,
                y_label="bytes",
            ),
        ),
        (
            "visualization",
            "data-persistence-redis-memory-line",
            metrics_line_visualization(
                title="Redis memory used",
                query=f'{METRICS_NAME_KEYWORD}: "redis_memory_used_bytes"',
                y_label="bytes",
            ),
        ),
        (
            "visualization",
            "data-persistence-redis-clients-line",
            metrics_line_visualization(
                title="Redis connected clients",
                query=f'{METRICS_NAME_KEYWORD}: "redis_connected_clients"',
                y_label="clients",
            ),
        ),
        (
            "visualization",
            "data-persistence-redis-keyspace",
            metrics_line_visualization(
                title="Redis keyspace hits vs misses",
                query=(
                    f'{METRICS_NAME_KEYWORD}: ("redis_keyspace_hits_total" OR '
                    f'"redis_keyspace_misses_total")'
                ),
                split_field=METRICS_NAME_KEYWORD,
                y_label="count",
            ),
        ),
        (
            "search",
            "data-persistence-metrics",
            saved_search(
                title="DataPersistence / Platform metrics",
                data_view=METRICS_VIEW,
                time_field=METRICS_TIME_FIELD,
                columns=METRICS_COLUMNS,
                query=DATA_PLATFORM_LUCENE,
                filters=[],
            ),
        ),
        (
            "search",
            "data-persistence-postgres",
            saved_search(
                title="DataPersistence / Postgres connections",
                data_view=METRICS_VIEW,
                time_field=METRICS_TIME_FIELD,
                columns=METRICS_COLUMNS,
                query=PG_CONNECTIONS_LUCENE,
                filters=[],
            ),
        ),
        (
            "search",
            "data-persistence-replication",
            saved_search(
                title="DataPersistence / Replication",
                data_view=METRICS_VIEW,
                time_field=METRICS_TIME_FIELD,
                columns=METRICS_COLUMNS,
                query=PG_REPLICATION_LUCENE,
                filters=[],
            ),
        ),
        (
            "search",
            "data-persistence-redis",
            saved_search(
                title="DataPersistence / Redis",
                data_view=METRICS_VIEW,
                time_field=METRICS_TIME_FIELD,
                columns=METRICS_COLUMNS,
                query=REDIS_LUCENE,
                filters=[],
            ),
        ),
        (
            "search",
            "data-persistence-db-pressure-logs",
            saved_search(
                title="DataPersistence / DB pressure logs",
                data_view=LOGS_VIEW,
                time_field=LOGS_TIME_FIELD,
                columns=LOG_STREAM_COLUMNS,
                query=DB_PRESSURE_LOGS_LUCENE,
                filters=[],
            ),
        ),
    ]
    objects.append(
        assemble_dashboard(
            dashboard_id="data-persistence",
            title="DataPersistence",
            description=(
                "Lifeguard Postgres primary + streaming replicas "
                "(WAL lag via pg_stat_replication), connection pressure, "
                "database size, and Redis clients/memory/keyspace. "
                "Open Discover saved searches for field sidebar triage. "
                f"Managed by {MANAGED_BY}"
            ),
            panels=[
                ("visualization", "data-persistence-guide", 0, 0, 48, 8),
                ("visualization", "data-persistence-pg-up", 0, 8, 8, 6),
                ("visualization", "data-persistence-pg-max-connections", 8, 8, 10, 6),
                ("visualization", "data-persistence-is-replica", 18, 8, 10, 6),
                ("visualization", "data-persistence-redis-clients", 28, 8, 10, 6),
                ("visualization", "data-persistence-redis-memory", 38, 8, 10, 6),
                ("visualization", "data-persistence-streaming-replicas", 0, 14, 28, 12),
                ("visualization", "data-persistence-backends-table", 28, 14, 20, 12),
                ("visualization", "data-persistence-replication-lag", 0, 26, 24, 12),
                ("visualization", "data-persistence-pg-backends", 24, 26, 24, 12),
                ("visualization", "data-persistence-pg-activity", 0, 38, 24, 12),
                ("visualization", "data-persistence-pg-db-size", 24, 38, 24, 12),
                ("visualization", "data-persistence-redis-memory-line", 0, 50, 24, 12),
                ("visualization", "data-persistence-redis-clients-line", 24, 50, 24, 12),
                ("visualization", "data-persistence-redis-keyspace", 0, 62, 48, 12),
                ("search", "data-persistence-metrics", 0, 74, 48, 18),
            ],
            panel_ref_prefix="data_persistence",
            time_from="now-1h",
            refresh_ms=30000,
            query=DATA_PLATFORM_LUCENE,
            filters=[],
        )
    )
    return objects


# ---------------------------------------------------------------------------
# k3s (dev) — LAN multipass cluster hosts + object health
# ---------------------------------------------------------------------------


def k3s_dev_guide_markdown() -> dict[str, Any]:
    """Banner: topology for the shared LAN k3s cluster (not GCP)."""
    markdown = (
        "## k3s (dev) — LAN cluster health\n\n"
        "**Dev-only.** Built for the Multipass/`shared-gitops-k8s-cluster` "
        "k3s LAN (`v1.36.2+k3s1`), not for GCP/cloud.\n\n"
        "### Nodes (expected)\n"
        "| Node | Role | LAN IP |\n"
        "|---|---|---|\n"
        "| `k8s-cp-1` | control-plane + etcd | `10.177.76.137` |\n"
        "| `k8s-worker-1` | worker | `10.177.76.175` |\n"
        "| `k8s-worker-2` | worker | `10.177.76.141` |\n"
        "| `k8s-worker-3` | worker | `10.177.76.44` |\n\n"
        "### What feeds this board\n"
        "- **node-exporter** DaemonSet (`observability`, hostNetwork `:9100`)\n"
        "- **kube-state-metrics** (`observability:8080`, allowlisted series)\n"
        "- OTel `prometheus/k3s` → Data Prepper → `otel-v1-apm-metrics*`\n"
        "- Filter: `metric.attributes.platform_component: k3s`\n\n"
        "KPI tiles use **distinct series** / **latest-per-series sum** — "
        "not `sum` of every scrape sample in the time picker (that looked like "
        "140 \"nodes Ready\").\n\n"
        "### Companion boards\n"
        f"- [**Logs**](/app/dashboards#/view/{LOGS_DASHBOARD_ID}) — app signal / HTTP\n"
        "- [**DataPersistence**](/app/dashboards#/view/data-persistence) — "
        "Postgres + Redis\n\n"
        "Stale nav entries under *Recently viewed* (Loadlinker / Platform war "
        "room / …) are browser history only — those dashboards were deleted. "
        "Clear via the nav overflow or a fresh profile.\n\n"
        f"Managed by {MANAGED_BY}."
    )
    vis_state = {
        "title": "k3s (dev) guide",
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
            "title": "k3s (dev) guide",
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


def _k3s_dev_bundle() -> list[tuple[str, str, dict[str, Any]]]:
    objects: list[tuple[str, str, dict[str, Any]]] = [
        ("visualization", "k3s-dev-guide", k3s_dev_guide_markdown()),
        (
            "visualization",
            "k3s-dev-nodes-ready",
            # Distinct nodes (not sum of every Ready=true scrape sample).
            metrics_cardinality_metric_visualization(
                title="Nodes Ready (condition=true)",
                query=(
                    f'{METRICS_NAME_KEYWORD}: "kube_node_status_condition" AND '
                    f'{METRICS_CONDITION_KEYWORD}: Ready AND '
                    f'{METRICS_STATUS_KEYWORD}: "true" AND '
                    f"metric.attributes.platform_component: k3s"
                ),
                field=METRICS_NODE_KEYWORD,
                custom_label="nodes Ready",
            ),
        ),
        (
            "visualization",
            "k3s-dev-pods-running",
            metrics_cardinality_metric_visualization(
                title="Pods Running",
                query=(
                    f'{METRICS_NAME_KEYWORD}: "kube_pod_status_phase" AND '
                    f'{METRICS_PHASE_KEYWORD}: Running AND '
                    f"metric.attributes.platform_component: k3s"
                ),
                field=METRICS_POD_KEYWORD,
                custom_label="pods Running",
            ),
        ),
        (
            "visualization",
            "k3s-dev-deploy-unavailable",
            metrics_instant_sum_vega(
                title="Deployment replicas unavailable",
                metric_name="kube_deployment_status_replicas_unavailable",
                series_field=METRICS_DEPLOYMENT_KEYWORD,
                custom_label="unavailable replicas",
            ),
        ),
        (
            "visualization",
            "k3s-dev-ds-unavailable",
            metrics_instant_sum_vega(
                title="DaemonSet pods unavailable",
                metric_name="kube_daemonset_status_number_unavailable",
                series_field=METRICS_DAEMONSET_KEYWORD,
                custom_label="unavailable DS pods",
            ),
        ),
        (
            "visualization",
            "k3s-dev-load1",
            metrics_line_visualization(
                title="Load1 by node",
                query=(
                    f'{METRICS_NAME_KEYWORD}: "node_load1" AND '
                    f"metric.attributes.platform_component: k3s"
                ),
                split_field=K3S_NODE_SPLIT_FIELD,
                split_size=8,
                y_label="load1",
            ),
        ),
        (
            "visualization",
            "k3s-dev-mem-available",
            metrics_line_visualization(
                title="MemAvailable bytes by node",
                query=(
                    f'{METRICS_NAME_KEYWORD}: "node_memory_MemAvailable_bytes" AND '
                    f"metric.attributes.platform_component: k3s"
                ),
                split_field=K3S_NODE_SPLIT_FIELD,
                split_size=8,
                y_label="bytes",
            ),
        ),
        (
            "visualization",
            "k3s-dev-rootfs-avail",
            metrics_line_visualization(
                title="Root filesystem avail bytes by node",
                query=(
                    f'{METRICS_NAME_KEYWORD}: "node_filesystem_avail_bytes" AND '
                    f"metric.attributes.platform_component: k3s"
                ),
                split_field=K3S_NODE_SPLIT_FIELD,
                split_size=8,
                y_label="bytes",
            ),
        ),
        (
            "visualization",
            "k3s-dev-pods-by-phase",
            metrics_cardinality_table_visualization(
                title="Pods by phase (distinct pods)",
                query=(
                    f'{METRICS_NAME_KEYWORD}: "kube_pod_status_phase" AND '
                    f"metric.attributes.platform_component: k3s"
                ),
                bucket_field=METRICS_PHASE_KEYWORD,
                cardinality_field=METRICS_POD_KEYWORD,
                size=8,
                bucket_label="phase",
                metric_label="pods",
            ),
        ),
        (
            "visualization",
            "k3s-dev-pods-by-namespace",
            metrics_cardinality_table_visualization(
                title="Running pods by namespace",
                query=(
                    f'{METRICS_NAME_KEYWORD}: "kube_pod_status_phase" AND '
                    f'{METRICS_PHASE_KEYWORD}: Running AND '
                    f"metric.attributes.platform_component: k3s"
                ),
                bucket_field=METRICS_NAMESPACE_KEYWORD,
                cardinality_field=METRICS_POD_KEYWORD,
                size=20,
                bucket_label="namespace",
                metric_label="pods",
            ),
        ),
        (
            "visualization",
            "k3s-dev-top-restarts",
            # Restart totals are counters — max over the window ≈ current counter.
            metrics_terms_table_visualization(
                title="Top container restart counters",
                query=(
                    f'{METRICS_NAME_KEYWORD}: '
                    f'"kube_pod_container_status_restarts_total" AND '
                    f"metric.attributes.platform_component: k3s"
                ),
                field=METRICS_POD_KEYWORD,
                size=15,
                field_label="pod",
                value_agg="max",
                value_label="restarts",
            ),
        ),
        (
            "visualization",
            "k3s-dev-deploy-unavailable-table",
            metrics_terms_table_visualization(
                title="Deployments with unavailable replicas",
                query=(
                    f'{METRICS_NAME_KEYWORD}: '
                    f'"kube_deployment_status_replicas_unavailable" AND '
                    f"metric.attributes.platform_component: k3s"
                ),
                field=METRICS_DEPLOYMENT_KEYWORD,
                size=15,
                field_label="deployment",
                value_agg="max",
                value_label="unavailable",
            ),
        ),
        (
            "search",
            "k3s-dev-metrics",
            saved_search(
                title="k3s (dev) / Metrics",
                data_view=METRICS_VIEW,
                time_field=METRICS_TIME_FIELD,
                columns=METRICS_COLUMNS
                + ["metric.attributes.node", "metric.attributes.namespace"],
                query=K3S_LUCENE,
                filters=[],
            ),
        ),
        (
            "search",
            "k3s-dev-node-metrics",
            saved_search(
                title="k3s (dev) / Node exporter",
                data_view=METRICS_VIEW,
                time_field=METRICS_TIME_FIELD,
                columns=METRICS_COLUMNS + ["metric.attributes.node"],
                query=K3S_NODE_LUCENE,
                filters=[],
            ),
        ),
        (
            "search",
            "k3s-dev-kube-metrics",
            saved_search(
                title="k3s (dev) / kube-state-metrics",
                data_view=METRICS_VIEW,
                time_field=METRICS_TIME_FIELD,
                columns=METRICS_COLUMNS
                + [
                    "metric.attributes.namespace",
                    "metric.attributes.pod",
                    "metric.attributes.phase",
                ],
                query=K3S_KUBE_LUCENE,
                filters=[],
            ),
        ),
    ]
    objects.append(
        assemble_dashboard(
            dashboard_id=K3S_DEV_DASHBOARD_ID,
            title="k3s (dev)",
            description=(
                "LAN k3s cluster health (Multipass shared-gitops): node load / "
                "memory / root disk, Ready nodes, pod phases, restart leaders, "
                "unavailable Deployments/DaemonSets. Dev-only — not for GCP. "
                f"Managed by {MANAGED_BY}"
            ),
            panels=[
                ("visualization", "k3s-dev-guide", 0, 0, 48, 10),
                ("visualization", "k3s-dev-nodes-ready", 0, 10, 12, 6),
                ("visualization", "k3s-dev-pods-running", 12, 10, 12, 6),
                ("visualization", "k3s-dev-deploy-unavailable", 24, 10, 12, 6),
                ("visualization", "k3s-dev-ds-unavailable", 36, 10, 12, 6),
                ("visualization", "k3s-dev-load1", 0, 16, 24, 12),
                ("visualization", "k3s-dev-mem-available", 24, 16, 24, 12),
                ("visualization", "k3s-dev-rootfs-avail", 0, 28, 48, 12),
                ("visualization", "k3s-dev-pods-by-phase", 0, 40, 16, 12),
                ("visualization", "k3s-dev-pods-by-namespace", 16, 40, 16, 12),
                ("visualization", "k3s-dev-top-restarts", 32, 40, 16, 12),
                ("visualization", "k3s-dev-deploy-unavailable-table", 0, 52, 24, 12),
                ("search", "k3s-dev-metrics", 24, 52, 24, 12),
            ],
            panel_ref_prefix="k3s_dev",
            time_from="now-1h",
            refresh_ms=30000,
            query=K3S_LUCENE,
            filters=[],
        )
    )
    return objects


DASHBOARD_BUNDLES: dict[str, list[tuple[str, str, dict[str, Any]]]] = {
    "logs-explore": _logs_explore_bundle(),
    "data-persistence": _data_persistence_bundle(),
    "k3s-dev": _k3s_dev_bundle(),
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
    # Pgpool-era DataPersistence panels (postgres-ha cutover).
    ("visualization", "data-persistence-pgpool-frontend-used"),
    ("visualization", "data-persistence-pgpool-frontend-total"),
    ("visualization", "data-persistence-pgpool-frontend-line"),
    ("visualization", "data-persistence-pgpool-backend-used"),
    ("visualization", "data-persistence-nodes-roles"),
    ("visualization", "data-persistence-replication-delay"),
    ("search", "data-persistence-nodes"),
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
