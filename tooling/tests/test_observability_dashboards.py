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
    assert any(item["type"] == "visualization" and item["id"] == "logs-explore-histogram" for item in parsed)


def test_log_stream_uses_structured_sidebar_columns() -> None:
    assert definitions.LOG_EVENT_CATEGORY_FIELD in definitions.LOG_STREAM_COLUMNS
    assert definitions.LOG_SCOPE_FIELD in definitions.LOG_STREAM_COLUMNS
    assert "serviceName" in definitions.LOG_STREAM_COLUMNS
    assert "body" in definitions.LOG_STREAM_COLUMNS


def test_default_noise_exclusion_uses_structured_fields() -> None:
    query = definitions.LOG_NOISE_EXCLUSION_LUCENE
    assert definitions.LOG_EVENT_CATEGORY_FIELD in query
    assert definitions.LOG_EPOLL_TARGET in query
    assert definitions.LOG_MEMORY_SCOPE in query
    filters = definitions.log_noise_filters()
    assert len(filters) == 3
    assert all(item["meta"]["negate"] is True for item in filters)


def test_saved_search_and_dashboard_apply_noise_filters() -> None:
    objects = definitions.all_dashboard_objects()
    saved_search = next(
        payload
        for object_type, object_id, payload in objects
        if object_type == "search" and object_id == "logs-explore-stream"
    )
    dashboard = next(
        payload
        for object_type, object_id, payload in objects
        if object_type == "dashboard" and object_id == "logs-explore"
    )
    for payload in (saved_search, dashboard):
        source = json.loads(
            payload["attributes"]["kibanaSavedObjectMeta"]["searchSourceJSON"]
        )
        assert definitions.LOG_NOISE_EXCLUSION_LUCENE in source["query"]["query"]
        assert len(source["filter"]) == 3


def test_discover_default_route_matches_noise_query() -> None:
    assert definitions.LOGS_DISCOVER_DEFAULT_ROUTE.startswith(
        "/app/data-explorer/discover/"
    )
    assert "event_category" in definitions.LOGS_DISCOVER_DEFAULT_ROUTE


def test_dashboard_defaults_to_fifteen_minute_window() -> None:
    objects = definitions.all_dashboard_objects()
    dashboard = next(
        payload
        for object_type, object_id, payload in objects
        if object_type == "dashboard" and object_id == "logs-explore"
    )
    assert dashboard["attributes"]["timeFrom"] == "now-15m"
