"""Contract tests for GitOps OpenSearch dashboard bundles."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFINITIONS = ROOT / "gitops/root/components/observability/dashboard_definitions.py"
DASHBOARDS = ROOT / "gitops/root/components/observability/dashboards"

spec = importlib.util.spec_from_file_location("dashboard_definitions", DEFINITIONS)
assert spec and spec.loader
definitions = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = definitions
spec.loader.exec_module(definitions)


def test_dashboard_bundles() -> None:
    assert set(definitions.DASHBOARD_BUNDLES) == {
        "logs-explore",
        "data-persistence",
        "k3s-dev",
    }


def test_k3s_dev_dashboard_is_lan_specific() -> None:
    objects = definitions.all_dashboard_objects()
    dashboard = next(
        payload
        for object_type, object_id, payload in objects
        if object_type == "dashboard" and object_id == "k3s-dev"
    )
    assert dashboard["attributes"]["title"] == "k3s (dev)"
    assert "not for GCP" in dashboard["attributes"]["description"]
    assert "platform_component: k3s" in json.dumps(dashboard)
    ref_ids = {ref["id"] for ref in dashboard["references"]}
    assert {
        "k3s-dev-guide",
        "k3s-dev-nodes-ready",
        "k3s-dev-load1",
        "k3s-dev-mem-available",
        "k3s-dev-pods-by-namespace",
        "k3s-dev-metrics",
    }.issubset(ref_ids)
    guide = next(
        payload
        for object_type, object_id, payload in objects
        if object_type == "visualization" and object_id == "k3s-dev-guide"
    )
    markdown = json.loads(guide["attributes"]["visState"])["params"]["markdown"]
    assert "k8s-cp-1" in markdown
    assert "10.177.76.137" in markdown
    path = DASHBOARDS / "k3s-dev.ndjson"
    assert path.is_file()


def test_dashboard_references_are_complete_and_stable() -> None:
    objects = definitions.all_dashboard_objects()
    identities = {(object_type, object_id) for object_type, object_id, _ in objects}
    assert len(identities) == len(objects)

    dashboard = next(
        payload
        for object_type, object_id, payload in objects
        if object_type == "dashboard" and object_id == "logs-explore"
    )
    for reference in dashboard["references"]:
        assert (reference["type"], reference["id"]) in identities


def test_ndjson_bundle_exists_and_parses() -> None:
    path = DASHBOARDS / "logs-explore.ndjson"
    assert path.is_file()
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    parsed = [json.loads(line) for line in lines]
    assert any(item["type"] == "dashboard" and item["id"] == "logs-explore" for item in parsed)
    assert any(item["type"] == "search" and item["id"] == "logs-explore-stream" for item in parsed)
    assert any(item["type"] == "search" and item["id"] == "logs-runtime-noise" for item in parsed)
    assert any(item["type"] == "search" and item["id"] == "logs-errors" for item in parsed)
    assert any(item["type"] == "search" and item["id"] == "logs-http" for item in parsed)
    assert any(
        item["type"] == "visualization" and item["id"] == "logs-http-top-paths"
        for item in parsed
    )


def test_data_persistence_ndjson_and_panels() -> None:
    path = DASHBOARDS / "data-persistence.ndjson"
    assert path.is_file()
    parsed = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(
        item["type"] == "dashboard" and item["id"] == "data-persistence" for item in parsed
    )
    assert any(
        item["type"] == "visualization"
        and item["id"] == "data-persistence-streaming-replicas"
        for item in parsed
    )
    assert any(
        item["type"] == "search" and item["id"] == "data-persistence-redis" for item in parsed
    )
    assert any(
        item["type"] == "search" and item["id"] == "data-persistence-replication"
        for item in parsed
    )

    objects = definitions.all_dashboard_objects()
    dashboard = next(
        payload
        for object_type, object_id, payload in objects
        if object_type == "dashboard" and object_id == "data-persistence"
    )
    assert dashboard["attributes"]["title"] == "DataPersistence"
    assert dashboard["attributes"]["timeFrom"] == "now-1h"
    assert "Pgpool" not in dashboard["attributes"]["description"]
    assert "streaming replicas" in dashboard["attributes"]["description"]
    ref_ids = {ref["id"] for ref in dashboard["references"]}
    assert {
        "data-persistence-guide",
        "data-persistence-pg-up",
        "data-persistence-streaming-replicas",
        "data-persistence-replication-lag",
        "data-persistence-pg-backends",
        "data-persistence-redis-memory-line",
        "data-persistence-metrics",
    }.issubset(ref_ids)
    assert "data-persistence-pgpool-frontend-used" not in ref_ids

    nodes = next(
        payload
        for object_type, object_id, payload in objects
        if object_type == "visualization"
        and object_id == "data-persistence-streaming-replicas"
    )
    vis_state = json.loads(nodes["attributes"]["visState"])
    assert vis_state["type"] == "vega"
    spec = vis_state["params"]["spec"]
    assert "pg_stat_replication_pg_wal_lsn_diff" in spec
    assert "pgpool2_" not in spec
    # OSD rejects %context%/%timefield% when body.query is set.
    assert "%context%" not in spec
    assert "%timefield%" not in spec
    assert "%timefilter%" in spec
    # Body rows must sit below the header (band scale alone starts at y=0).
    assert '"y":{"value":24}' in spec.replace(" ", "")


def test_discover_is_canonical_field_sidebar_surface() -> None:
    assert definitions.LOGS_DISCOVER_DEFAULT_ROUTE.startswith(
        "/app/data-explorer/discover/"
    )
    assert "shared-observability-logs" in definitions.LOGS_DISCOVER_DEFAULT_ROUTE
    guide = definitions.discover_guide_markdown()
    vis_state = json.loads(guide["attributes"]["visState"])
    assert vis_state["type"] == "markdown"
    assert "Logs / HTTP" in vis_state["params"]["markdown"]
    assert "dropped at the collector" in vis_state["params"]["markdown"]


def test_log_stream_uses_structured_sidebar_columns() -> None:
    assert definitions.LOG_STREAM_COLUMNS[0] == "name"
    assert definitions.LOG_STREAM_COLUMNS[1] == definitions.LOG_APPLICATION_FIELD
    assert "event_class" in definitions.LOG_STREAM_COLUMNS
    assert "path" in definitions.LOG_STREAM_COLUMNS
    assert "has_trace" in definitions.LOG_STREAM_COLUMNS
    assert "log.attributes" not in ",".join(definitions.LOG_STREAM_COLUMNS)
    assert "resource.attributes" not in ",".join(definitions.LOG_STREAM_COLUMNS)


def test_sidebar_popular_fields_namespace_then_application() -> None:
    assert definitions.LOG_SIDEBAR_FILTER_FIELDS[0] == definitions.LOG_NAMESPACE_FIELD
    assert definitions.LOG_SIDEBAR_FILTER_FIELDS[1] == definitions.LOG_APPLICATION_FIELD
    assert definitions.LOG_EVENT_CLASS_FIELD in definitions.LOG_SIDEBAR_FILTER_FIELDS
    assert definitions.LOG_PATH_FIELD in definitions.LOG_SIDEBAR_FILTER_FIELDS
    assert "service@namespace" not in "".join(definitions.LOG_SIDEBAR_FILTER_FIELDS)


def test_log_field_short_labels_strip_otel_prefixes() -> None:
    copies = definitions.LOG_FIELD_SHORT_COPIES
    assert copies["name"] == definitions.LOG_NAMESPACE_FIELD
    assert copies["method"] == definitions.LOG_METHOD_FIELD
    assert copies["event_class"] == definitions.LOG_EVENT_CLASS_FIELD
    assert copies["duration_ms"] == definitions.LOG_DURATION_FIELD
    labels = definitions.LOG_FIELD_SHORT_LABELS
    assert labels[definitions.LOG_NAMESPACE_FIELD] == "name"
    assert labels[definitions.LOG_METHOD_FIELD] == "method"


def test_signal_and_runtime_noise_queries_are_complements() -> None:
    assert definitions.LOG_SIGNAL_LUCENE == "log.attributes.event_class:application"
    assert (
        definitions.LOG_RUNTIME_NOISE_LUCENE
        == "log.attributes.event_class:runtime_noise"
    )
    assert "event_category:http" in definitions.LOG_HTTP_LUCENE
    assert set(definitions.LOG_NOISE_CATEGORIES) == {
        "epoll_io",
        "runtime_metrics",
        "runtime_config",
        "framework_lifecycle",
    }
    filters = definitions.log_signal_filters()
    assert len(filters) == 2
    assert all(item["meta"]["negate"] is True for item in filters)


def test_saved_search_scopes_cover_roadmap() -> None:
    ids = {
        object_id
        for object_type, object_id, _ in definitions.all_dashboard_objects()
        if object_type == "search"
    }
    assert {
        "logs-explore-stream",
        "logs-http",
        "logs-errors",
        "logs-auth",
        "logs-bff",
        "logs-runtime-noise",
    }.issubset(ids)

    http = next(
        payload
        for object_type, object_id, payload in definitions.all_dashboard_objects()
        if object_type == "search" and object_id == "logs-http"
    )
    source = json.loads(http["attributes"]["kibanaSavedObjectMeta"]["searchSourceJSON"])
    assert "http" in source["query"]["query"]
    assert "path" in http["attributes"]["columns"]
    assert "method" in http["attributes"]["columns"]

    noise = next(
        payload
        for object_type, object_id, payload in definitions.all_dashboard_objects()
        if object_type == "search" and object_id == "logs-runtime-noise"
    )
    source = json.loads(noise["attributes"]["kibanaSavedObjectMeta"]["searchSourceJSON"])
    assert source["filter"] == []
    assert "runtime_noise" in source["query"]["query"]


def test_dashboard_includes_http_triage_panels() -> None:
    objects = definitions.all_dashboard_objects()
    dashboard = next(
        payload
        for object_type, object_id, payload in objects
        if object_type == "dashboard" and object_id == "logs-explore"
    )
    assert dashboard["attributes"]["timeFrom"] == "now-15m"
    ref_ids = {ref["id"] for ref in dashboard["references"]}
    assert {
        "logs-explore-discover-guide",
        "logs-explore-histogram",
        "logs-http-top-paths",
        "logs-http-status-codes",
        "logs-http-status-codes-pie",
        "logs-http-avg-duration",
        "logs-signal-stream",
    }.issubset(ref_ids)
    # Saved search kept for Discover; dashboard stream is the Vega panel.
    assert ("search", "logs-explore-stream") in {
        (object_type, object_id) for object_type, object_id, _ in objects
    }
    panels_json = json.loads(dashboard["attributes"]["panelsJSON"])
    panels = {
        ref["id"]: panels_json[i]["gridData"]
        for i, ref in enumerate(dashboard["references"])
    }
    # Status table full height; donut under avg duration (right column).
    assert panels["logs-http-status-codes"]["h"] == 14
    assert panels["logs-http-status-codes"]["x"] == 28
    assert panels["logs-http-avg-duration"]["x"] == 38
    assert panels["logs-http-avg-duration"]["y"] == 17
    assert panels["logs-http-avg-duration"]["h"] == 7
    assert panels["logs-http-status-codes-pie"]["x"] == 38
    assert panels["logs-http-status-codes-pie"]["y"] == 24
    assert panels["logs-http-status-codes-pie"]["h"] == 7
    # Stable panel ids (object_id) so layout updates stick after reimport.
    by_ref = {
        ref["id"]: panels_json[i]
        for i, ref in enumerate(dashboard["references"])
    }
    for object_id, panel in by_ref.items():
        assert panel["gridData"]["i"] == object_id
        assert panel["panelIndex"] == object_id


def test_status_codes_pie_uses_class_colors() -> None:
    pie = next(
        payload
        for object_type, object_id, payload in definitions.all_dashboard_objects()
        if object_type == "visualization" and object_id == "logs-http-status-codes-pie"
    )
    vis_state = json.loads(pie["attributes"]["visState"])
    assert vis_state["type"] == "vega"
    spec = json.loads(vis_state["params"]["spec"])
    spec_text = vis_state["params"]["spec"]
    assert definitions.HTTP_STATUS_COLOR_2XX in spec_text
    assert definitions.HTTP_STATUS_COLOR_3XX in spec_text
    assert definitions.HTTP_STATUS_COLOR_4XX in spec_text
    assert definitions.HTTP_STATUS_COLOR_5XX in spec_text
    assert definitions.LOG_STATUS_FIELD in spec_text
    assert "toNumber(datum.status) >= 500" in spec_text
    # Percentages live in the legend ("200 - 100%"), not as text on the donut.
    assert not any(mark.get("type") == "text" for mark in spec["marks"])
    assert "datum.status + ' - ' + format(datum.percent, '.0%')" in spec_text
    assert {"data": "statuses", "field": "label"} == spec["scales"][0]["domain"]


def test_volume_histogram_click_zooms_time() -> None:
    hist = next(
        payload
        for object_type, object_id, payload in definitions.all_dashboard_objects()
        if object_type == "visualization" and object_id == "logs-explore-histogram"
    )
    vis_state = json.loads(hist["attributes"]["visState"])
    assert vis_state["type"] == "vega"
    spec_text = vis_state["params"]["spec"]
    assert f"/view/{definitions.LOGS_DASHBOARD_ID}" in spec_text
    assert "time:(from:" in spec_text
    assert "fixed_interval" in spec_text
    assert "href" in spec_text


def test_top_paths_includes_rps_and_pslo() -> None:
    top_paths = next(
        payload
        for object_type, object_id, payload in definitions.all_dashboard_objects()
        if object_type == "visualization" and object_id == "logs-http-top-paths"
    )
    vis_state = json.loads(top_paths["attributes"]["visState"])
    assert vis_state["type"] == "vega"
    spec = json.loads(vis_state["params"]["spec"])
    signals = {signal["name"]: signal.get("value") for signal in spec["signals"]}
    assert signals["windowSeconds"] == 900
    assert signals["sloMs"] == definitions.HTTP_P95_SLO_MS
    assert "windowSeconds" in vis_state["params"]["spec"]
    assert "vsSlo" in vis_state["params"]["spec"]
    assert "log.attributes.path.keyword" in vis_state["params"]["spec"]
    assert "p95" in spec["data"][0]["url"]["body"]["aggs"]["paths"]["aggs"]
    assert "datum.p95 < 1" in vis_state["params"]["spec"]
    assert ".3f" in vis_state["params"]["spec"]


def test_signal_stream_has_row_discover_links() -> None:
    stream = next(
        payload
        for object_type, object_id, payload in definitions.all_dashboard_objects()
        if object_type == "visualization" and object_id == "logs-signal-stream"
    )
    vis_state = json.loads(stream["attributes"]["visState"])
    assert vis_state["type"] == "vega"
    spec_text = vis_state["params"]["spec"]
    # Classic Discover (not data-explorer) owns single-doc + surrounding views.
    assert "/app/discover#/doc/shared-observability-logs/" in spec_text
    assert "/app/discover#/context/shared-observability-logs/" in spec_text
    assert "/app/data-explorer/discover/" not in spec_text
    assert "hits.hits" in spec_text
    assert "docUrl" in spec_text
    assert "ctxUrl" in spec_text
    assert "otel-v1-apm-logs-*" in spec_text
    # Single doc needs concrete index + ?id= (not bare doc id in the path).
    assert "datum._index + '?id=' + datum._id" in spec_text
    assert "ctxUrl" in spec_text and "' + datum._id" in spec_text
    # Wide hit rects (not text-only) so canvas clicks register.
    assert '"type":"rect"' in spec_text.replace(" ", "")
    assert "href" in spec_text


def test_dashboards_enables_vega_external_urls() -> None:
    values = (
        ROOT
        / "deployment-configuration/profiles/dev/observability/helm-values-dashboards.yaml"
    ).read_text(encoding="utf-8")
    assert "vis_type_vega.enableExternalUrls: true" in values
