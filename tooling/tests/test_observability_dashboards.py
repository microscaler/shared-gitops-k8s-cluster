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


def test_dashboard_bundles_cover_products() -> None:
    assert set(definitions.DASHBOARD_BUNDLES) == {
        "platform-postgres-connections",
        "platform-data-namespace",
        "platform-apm-correlation",
        "platform-logs-explore",
        "loadlinker-logs-explore",
        "loadlinker-health",
        "loadlinker-bff-edge",
        "loadlinker-sesame-auth",
        "sesame-logs-explore",
        "sesame-platform-health",
        "sesame-auth-critical-path",
    }


def test_dashboard_references_are_complete_and_stable() -> None:
    objects = definitions.all_dashboard_objects()
    identities = {(object_type, object_id) for object_type, object_id, _ in objects}
    assert len(identities) == len(objects)

    for dashboard_id in definitions.DASHBOARD_BUNDLES:
        dashboard = next(
            payload
            for object_type, object_id, payload in objects
            if object_type == "dashboard" and object_id == dashboard_id
        )
        for reference in dashboard["references"]:
            assert (reference["type"], reference["id"]) in identities


def test_ndjson_bundles_exist_and_parse() -> None:
    for bundle_name in definitions.DASHBOARD_BUNDLES:
        path = DASHBOARDS / f"{bundle_name}.ndjson"
        assert path.is_file(), f"missing generated bundle {path.name}"
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert lines, f"{path.name} is empty"
        parsed = [json.loads(line) for line in lines]
        assert any(item["type"] == "dashboard" for item in parsed)


def test_loadlinker_p0_query_present() -> None:
    assert "bff" in definitions.LOADLINKER_P0_QUERY
    assert "bidding" in definitions.LOADLINKER_P0_QUERY


def test_standard_log_columns_defined() -> None:
    assert "traceId" in definitions.STANDARD_LOG_COLUMNS
    assert "severityText" in definitions.STANDARD_LOG_COLUMNS


def test_log_hub_bundles_exist() -> None:
    for bundle_id in (
        "platform-logs-explore",
        "loadlinker-logs-explore",
        "sesame-logs-explore",
    ):
        assert bundle_id in definitions.DASHBOARD_BUNDLES


def test_slo_targets_are_positive() -> None:
    assert definitions.SLO_BFF_P95_MS > 0
    assert definitions.SLO_AUTHZ_P95_MS > 0
