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


def test_single_logs_dashboard_bundle() -> None:
    assert set(definitions.DASHBOARD_BUNDLES) == {"logs-explore"}


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
        "logs-http-avg-duration",
        "logs-explore-stream",
    }.issubset(ref_ids)


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
