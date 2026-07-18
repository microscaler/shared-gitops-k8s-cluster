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
        "Epoll and memory stats are **dropped at the collector** (not indexed). "
        "Expand a row for structured fields (`log.attributes.message`, method, "
        "path, status, duration_ms)."
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


def _visualization(
    *,
    title: str,
    data_view: str,
    vis_state: dict[str, Any],
    query: str,
    filters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    source_ref = "kibanaSavedObjectMeta.searchSourceJSON.index"
    return {
        "attributes": {
            "title": title,
            "description": f"Managed by {MANAGED_BY}",
            "visState": compact(vis_state),
            "uiStateJSON": "{}",
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
) -> dict[str, Any]:
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
    """Terms pie with slice percentages (status codes, …)."""
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
        "type": "pie",
        "params": {
            "type": "pie",
            "addTooltip": True,
            "addLegend": True,
            "legendPosition": "right",
            "isDonut": True,
            "labels": {
                "show": True,
                "values": True,
                "last_level": True,
                "truncate": 100,
                "percentDecimals": 1,
            },
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
                "type": "terms",
                "schema": "segment",
                "params": bucket_params,
            },
        ],
    }
    return _visualization(
        title=title, data_view=data_view, vis_state=vis_state, query=query
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
                title="Log volume (signal)",
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
    ]
    objects.extend(_saved_search_scopes())
    objects.append(
        assemble_dashboard(
            dashboard_id="logs-explore",
            title="Logs",
            description=(
                "Companion overview with HTTP triage (top paths, status table + "
                "pie, avg latency). Open Discover for the field sidebar and saved "
                "searches (Signal / HTTP / Errors / Auth / BFF / Runtime noise). "
                "Epoll and memory are dropped at the collector; rare "
                "lifecycle/config noise is selectable via Runtime noise. "
                f"Managed by {MANAGED_BY}"
            ),
            panels=[
                ("visualization", "logs-explore-discover-guide", 0, 0, 48, 7),
                ("visualization", "logs-explore-histogram", 0, 7, 48, 10),
                ("visualization", "logs-http-top-paths", 0, 17, 28, 14),
                ("visualization", "logs-http-status-codes", 28, 17, 10, 7),
                ("visualization", "logs-http-status-codes-pie", 28, 24, 10, 7),
                ("visualization", "logs-http-avg-duration", 38, 17, 10, 14),
                ("search", "logs-explore-stream", 0, 31, 48, 24),
            ],
            panel_ref_prefix="logs_explore",
            time_from="now-15m",
            refresh_ms=30000,
        )
    )
    return objects


# ---------------------------------------------------------------------------
# DataPersistence — Postgres HA / Pgpool / Redis (metrics index)
# ---------------------------------------------------------------------------

METRICS_VIEW = "shared-observability-metrics"
METRICS_TIME_FIELD = "time"
METRICS_VALUE_FIELD = "value"
METRICS_NAME_KEYWORD = "name.keyword"
METRICS_HOSTNAME_KEYWORD = "metric.attributes.hostname.keyword"
METRICS_ROLE_KEYWORD = "metric.attributes.role.keyword"
METRICS_DATNAME_KEYWORD = "metric.attributes.datname.keyword"
METRICS_CONSUMER_NS_KEYWORD = "metric.attributes.consumer_namespace.keyword"
METRICS_SLOT_KEYWORD = "metric.attributes.slot_name.keyword"

METRICS_COLUMNS = [
    "time",
    "name",
    "value",
    "serviceName",
    "metric.attributes.platform_component",
    "metric.attributes.hostname",
    "metric.attributes.role",
    "metric.attributes.datname",
    "metric.attributes.consumer_namespace",
]

PG_CONNECTIONS_LUCENE = (
    f'{METRICS_NAME_KEYWORD}: ("pg_stat_database_numbackends" OR '
    f'"pg_settings_max_connections" OR "pg_stat_activity_count")'
)
PG_REPLICATION_LUCENE = (
    f'{METRICS_NAME_KEYWORD}: ("pg_replication_slots_active" OR '
    f'"pg_replication_slots_pg_wal_lsn_diff")'
)
PGPOOL_LUCENE = f"{METRICS_NAME_KEYWORD}: pgpool2_*"
PGPOOL_NODES_LUCENE = (
    f'{METRICS_NAME_KEYWORD}: ("pgpool2_pool_nodes_status" OR '
    f'"pgpool2_pool_nodes_replication_delay" OR '
    f'"pgpool2_pool_backend_stats_status")'
)
REDIS_LUCENE = f"{METRICS_NAME_KEYWORD}: redis_*"
DATA_PLATFORM_LUCENE = (
    f"({PG_CONNECTIONS_LUCENE}) OR ({PGPOOL_LUCENE}) OR ({REDIS_LUCENE})"
)
DB_PRESSURE_LOGS_LUCENE = (
    "body: (*connection* OR *pool* OR *postgres* OR *redis* OR *timeout* OR *Pgpool*)"
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
    """Banner: Discover scopes for Postgres / Pgpool / Redis metrics."""
    markdown = (
        "## DataPersistence — Postgres HA, Pgpool, Redis\n\n"
        f"[**Open metrics (all)**]({_metrics_discover_route(DATA_PLATFORM_LUCENE)}) — "
        "Postgres + Pgpool + Redis gauges.\n"
        f"[**Open nodes / replication**]({_metrics_discover_route(PGPOOL_NODES_LUCENE)}) — "
        "primary vs standby + replication delay.\n"
        f"[**Open Redis**]({_metrics_discover_route(REDIS_LUCENE)}) — "
        "clients, memory, keyspace.\n\n"
        "### What to watch\n"
        "1. **Pgpool nodes** — `role:primary` / `role:standby` status = 1 (up)\n"
        "2. **Replication delay** — `pgpool2_pool_nodes_replication_delay` near 0\n"
        "3. **Frontend slots** — `pgpool2_frontend_used` vs `pgpool2_frontend_total` (64)\n"
        "4. **DB backends** — `pg_stat_database_numbackends` by `datname` "
        "(hauliage / sesame_idam / rerp)\n"
        "5. **Redis** — connected clients + memory used\n\n"
        "### Saved searches (Discover → Open)\n"
        "- **DataPersistence / Platform metrics**\n"
        "- **DataPersistence / Postgres connections**\n"
        "- **DataPersistence / Nodes & replication**\n"
        "- **DataPersistence / Redis**\n"
        "- **DataPersistence / DB pressure logs** (log index)\n\n"
        "Scraped via OTel `prometheus/data` → Data Prepper → "
        "`otel-v1-apm-metrics*`. Managed by shared-gitops-k8s-cluster."
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
    """Single-number gauge from metric `value` (avg/max/sum)."""
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
) -> dict[str, Any]:
    """Latest-window avg(value) by terms bucket (nodes, databases, …)."""
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
                "type": "avg",
                "schema": "metric",
                "params": {
                    "field": METRICS_VALUE_FIELD,
                    "customLabel": "avg value",
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


def metrics_nodes_roles_vega(
    *,
    title: str = "Postgres nodes — role + status + replication delay",
) -> dict[str, Any]:
    """Composite table: hostname × role with status and replication delay."""
    spec = {
        "$schema": "https://vega.github.io/schema/vega/v5.json",
        "padding": 8,
        "autosize": {"type": "fit", "contains": "padding"},
        "data": [
            {
                "name": "status",
                "url": _metrics_vega_url(
                    metric_name="pgpool2_pool_nodes_status",
                    aggs={
                        "hosts": {
                            "terms": {
                                "field": METRICS_HOSTNAME_KEYWORD,
                                "size": 10,
                            },
                            "aggs": {
                                "role": {
                                    "terms": {
                                        "field": METRICS_ROLE_KEYWORD,
                                        "size": 4,
                                    },
                                    "aggs": {
                                        "status": {
                                            "avg": {"field": METRICS_VALUE_FIELD}
                                        }
                                    },
                                }
                            },
                        }
                    },
                ),
                "format": {"property": "aggregations.hosts.buckets"},
                "transform": [
                    {"type": "flatten", "fields": ["role.buckets"], "as": ["roleBucket"]},
                    {
                        "type": "formula",
                        "as": "role",
                        "expr": "datum.roleBucket.key",
                    },
                    {
                        "type": "formula",
                        "as": "status",
                        "expr": "datum.roleBucket.status.value",
                    },
                    {
                        "type": "formula",
                        "as": "hostShort",
                        "expr": "split(datum.key, '.')[0]",
                    },
                ],
            },
            {
                "name": "delay",
                "url": _metrics_vega_url(
                    metric_name="pgpool2_pool_nodes_replication_delay",
                    aggs={
                        "hosts": {
                            "terms": {
                                "field": METRICS_HOSTNAME_KEYWORD,
                                "size": 10,
                            },
                            "aggs": {
                                "delay": {"avg": {"field": METRICS_VALUE_FIELD}}
                            },
                        }
                    },
                ),
                "format": {"property": "aggregations.hosts.buckets"},
                "transform": [
                    {
                        "type": "formula",
                        "as": "hostShort",
                        "expr": "split(datum.key, '.')[0]",
                    },
                    {
                        "type": "formula",
                        "as": "delay",
                        "expr": "datum.delay.value",
                    },
                ],
            },
            {
                "name": "joined",
                "source": "status",
                "transform": [
                    {
                        "type": "lookup",
                        "from": "delay",
                        "key": "key",
                        "fields": ["key"],
                        "values": ["delay"],
                    },
                    {
                        "type": "window",
                        "ops": ["row_number"],
                        "as": ["row"],
                        "sort": [
                            {"field": "role", "order": "ascending"},
                            {"field": "hostShort", "order": "ascending"},
                        ],
                    },
                ],
            },
            {
                "name": "header",
                "values": [
                    {
                        "hostShort": "pod",
                        "role": "role",
                        "status": "status",
                        "delay": "repl delay",
                        "row": 0,
                    }
                ],
            },
        ],
        "scales": [
            {
                "name": "y",
                "type": "band",
                "domain": {"data": "joined", "field": "row"},
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
                                "text": {"field": "hostShort"},
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
                                "x": {"signal": "width * 0.42"},
                                "y": {"value": 14},
                                "text": {"field": "role"},
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
                                "x": {"signal": "width * 0.68"},
                                "y": {"value": 14},
                                "text": {"field": "status"},
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
                                "text": {"field": "delay"},
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
                "type": "text",
                "from": {"data": "joined"},
                "encode": {
                    "update": {
                        "x": {"value": 0},
                        "y": {"scale": "y", "field": "row", "band": 0.5},
                        "text": {"field": "hostShort"},
                        "fontSize": {"value": 12},
                        "fill": {"value": "#111"},
                    }
                },
            },
            {
                "type": "text",
                "from": {"data": "joined"},
                "encode": {
                    "update": {
                        "x": {"signal": "width * 0.42"},
                        "y": {"scale": "y", "field": "row", "band": 0.5},
                        "text": {"field": "role"},
                        "fontSize": {"value": 12},
                        "fontWeight": {"value": "bold"},
                        "fill": {
                            "signal": (
                                "datum.role === 'primary' ? '#0a5bd3' : '#555'"
                            )
                        },
                    }
                },
            },
            {
                "type": "text",
                "from": {"data": "joined"},
                "encode": {
                    "update": {
                        "x": {"signal": "width * 0.68"},
                        "y": {"scale": "y", "field": "row", "band": 0.5},
                        "text": {
                            "signal": "datum.status >= 1 ? 'up' : 'down'"
                        },
                        "fontSize": {"value": 12},
                        "fontWeight": {"value": "bold"},
                        "fill": {
                            "signal": (
                                "datum.status >= 1 ? '#0a7a28' : '#b00020'"
                            )
                        },
                    }
                },
            },
            {
                "type": "text",
                "from": {"data": "joined"},
                "encode": {
                    "update": {
                        "x": {"signal": "width"},
                        "y": {"scale": "y", "field": "row", "band": 0.5},
                        "text": {
                            "signal": (
                                "datum.delay == null ? '—' : "
                                "format(datum.delay, ',.0f')"
                            )
                        },
                        "align": {"value": "right"},
                        "fontSize": {"value": 12},
                        "fill": {
                            "signal": (
                                "datum.delay > 0 ? '#b00020' : '#0a7a28'"
                            )
                        },
                    }
                },
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
        query=PGPOOL_NODES_LUCENE,
        filters=[],
    )


def _data_persistence_bundle() -> list[tuple[str, str, dict[str, Any]]]:
    """Postgres HA + Pgpool masters/replicas + Redis overview."""
    objects: list[tuple[str, str, dict[str, Any]]] = [
        ("visualization", "data-persistence-guide", data_persistence_guide_markdown()),
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
            "data-persistence-pgpool-frontend-used",
            metrics_value_metric_visualization(
                title="Pgpool frontend used",
                query=f'{METRICS_NAME_KEYWORD}: "pgpool2_frontend_used"',
                agg="avg",
                custom_label="frontend used",
            ),
        ),
        (
            "visualization",
            "data-persistence-pgpool-frontend-total",
            metrics_value_metric_visualization(
                title="Pgpool frontend total",
                query=f'{METRICS_NAME_KEYWORD}: "pgpool2_frontend_total"',
                agg="max",
                custom_label="frontend total",
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
            "data-persistence-nodes-roles",
            metrics_nodes_roles_vega(),
        ),
        (
            "visualization",
            "data-persistence-replication-delay",
            metrics_line_visualization(
                title="Replication delay by node (Pgpool)",
                query=(
                    f'{METRICS_NAME_KEYWORD}: "pgpool2_pool_nodes_replication_delay"'
                ),
                split_field=METRICS_HOSTNAME_KEYWORD,
                y_label="delay",
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
                title="Postgres activity (idle+active client backends)",
                query=(
                    f'{METRICS_NAME_KEYWORD}: "pg_stat_activity_count" AND '
                    'metric.attributes.backend_type: "client backend" AND '
                    '(metric.attributes.state: "idle" OR '
                    'metric.attributes.state: "active")'
                ),
                split_field=METRICS_DATNAME_KEYWORD,
                y_label="sessions",
            ),
        ),
        (
            "visualization",
            "data-persistence-pgpool-frontend-line",
            metrics_line_visualization(
                title="Pgpool frontend used (time series)",
                query=f'{METRICS_NAME_KEYWORD}: "pgpool2_frontend_used"',
                y_label="frontend used",
            ),
        ),
        (
            "visualization",
            "data-persistence-pgpool-backend-used",
            metrics_line_visualization(
                title="Pgpool backend used",
                query=f'{METRICS_NAME_KEYWORD}: "pgpool2_backend_used"',
                y_label="backend used",
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
            "data-persistence-nodes",
            saved_search(
                title="DataPersistence / Nodes & replication",
                data_view=METRICS_VIEW,
                time_field=METRICS_TIME_FIELD,
                columns=METRICS_COLUMNS,
                query=PGPOOL_NODES_LUCENE,
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
                "Postgres HA connections, Pgpool frontend/backend slots, "
                "primary vs standby node health, replication delay, and Redis "
                "clients/memory/keyspace. Open Discover saved searches for "
                "field sidebar triage. Managed by "
                f"{MANAGED_BY}"
            ),
            panels=[
                ("visualization", "data-persistence-guide", 0, 0, 48, 8),
                ("visualization", "data-persistence-pg-max-connections", 0, 8, 9, 6),
                ("visualization", "data-persistence-pgpool-frontend-used", 9, 8, 10, 6),
                ("visualization", "data-persistence-pgpool-frontend-total", 19, 8, 9, 6),
                ("visualization", "data-persistence-redis-clients", 28, 8, 10, 6),
                ("visualization", "data-persistence-redis-memory", 38, 8, 10, 6),
                ("visualization", "data-persistence-nodes-roles", 0, 14, 28, 12),
                ("visualization", "data-persistence-backends-table", 28, 14, 20, 12),
                ("visualization", "data-persistence-replication-delay", 0, 26, 24, 12),
                ("visualization", "data-persistence-pg-backends", 24, 26, 24, 12),
                ("visualization", "data-persistence-pg-activity", 0, 38, 24, 12),
                ("visualization", "data-persistence-pgpool-frontend-line", 24, 38, 24, 12),
                ("visualization", "data-persistence-pgpool-backend-used", 0, 50, 24, 12),
                ("visualization", "data-persistence-redis-memory-line", 24, 50, 24, 12),
                ("visualization", "data-persistence-redis-clients-line", 0, 62, 24, 12),
                ("visualization", "data-persistence-redis-keyspace", 24, 62, 24, 12),
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


DASHBOARD_BUNDLES: dict[str, list[tuple[str, str, dict[str, Any]]]] = {
    "logs-explore": _logs_explore_bundle(),
    "data-persistence": _data_persistence_bundle(),
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
