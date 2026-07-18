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


def test_log_stream_uses_discover_columns() -> None:
    assert definitions.LOG_STREAM_COLUMNS == [
        "observedTime",
        "serviceName",
        "severityText",
        "traceId",
        "body",
    ]


def test_dashboard_defaults_to_fifteen_minute_window() -> None:
    objects = definitions.all_dashboard_objects()
    dashboard = next(
        payload
        for object_type, object_id, payload in objects
        if object_type == "dashboard" and object_id == "logs-explore"
    )
    assert dashboard["attributes"]["timeFrom"] == "now-15m"
