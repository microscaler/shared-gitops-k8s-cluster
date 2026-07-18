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


def test_discover_is_canonical_field_sidebar_surface() -> None:
    assert definitions.LOGS_DISCOVER_DEFAULT_ROUTE.startswith(
        "/app/data-explorer/discover/"
    )
    assert "shared-observability-logs" in definitions.LOGS_DISCOVER_DEFAULT_ROUTE
    guide = definitions.discover_guide_markdown()
    vis_state = json.loads(guide["attributes"]["visState"])
    assert vis_state["type"] == "markdown"
    assert "Runtime noise" in vis_state["params"]["markdown"]


def test_log_stream_uses_structured_sidebar_columns() -> None:
    assert definitions.LOG_STREAM_COLUMNS[0] == definitions.LOG_NAMESPACE_FIELD
    assert definitions.LOG_STREAM_COLUMNS[1] == definitions.LOG_APPLICATION_FIELD
    assert definitions.LOG_EVENT_CLASS_FIELD in definitions.LOG_STREAM_COLUMNS
    assert definitions.LOG_HAS_TRACE_FIELD in definitions.LOG_STREAM_COLUMNS


def test_sidebar_popular_fields_namespace_then_application() -> None:
    assert definitions.LOG_SIDEBAR_FILTER_FIELDS[0] == definitions.LOG_NAMESPACE_FIELD
    assert definitions.LOG_SIDEBAR_FILTER_FIELDS[1] == definitions.LOG_APPLICATION_FIELD
    assert definitions.LOG_EVENT_CLASS_FIELD in definitions.LOG_SIDEBAR_FILTER_FIELDS
    assert "service@namespace" not in "".join(definitions.LOG_SIDEBAR_FILTER_FIELDS)


def test_signal_and_runtime_noise_queries_are_complements() -> None:
    assert definitions.LOG_SIGNAL_LUCENE == "log.attributes.event_class:application"
    assert (
        definitions.LOG_RUNTIME_NOISE_LUCENE
        == "log.attributes.event_class:runtime_noise"
    )
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
        "logs-errors",
        "logs-auth",
        "logs-bff",
        "logs-runtime-noise",
    }.issubset(ids)

    noise = next(
        payload
        for object_type, object_id, payload in definitions.all_dashboard_objects()
        if object_type == "search" and object_id == "logs-runtime-noise"
    )
    source = json.loads(noise["attributes"]["kibanaSavedObjectMeta"]["searchSourceJSON"])
    assert source["filter"] == []
    assert "runtime_noise" in source["query"]["query"] or "epoll" in source["query"]["query"]


def test_dashboard_defaults_to_fifteen_minute_window() -> None:
    objects = definitions.all_dashboard_objects()
    dashboard = next(
        payload
        for object_type, object_id, payload in objects
        if object_type == "dashboard" and object_id == "logs-explore"
    )
    assert dashboard["attributes"]["timeFrom"] == "now-15m"
