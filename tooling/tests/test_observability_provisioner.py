"""Contract tests for the OpenSearch observability provisioner."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "gitops/root/components/observability/provision-observability.py"
SPEC = importlib.util.spec_from_file_location("observability_provisioner", SCRIPT)
assert SPEC and SPEC.loader
provisioner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = provisioner
SPEC.loader.exec_module(provisioner)


def test_lifecycle_policy_enforces_seven_day_delete() -> None:
    policy = provisioner.lifecycle_policy(7, ["otel-v1-apm-logs-*"])["policy"]

    assert policy["default_state"] == "hot"
    assert policy["states"][0]["transitions"] == [
        {"state_name": "delete", "conditions": {"min_index_age": "7d"}}
    ]
    assert policy["states"][1]["actions"] == [{"delete": {}}]
    assert policy["ism_template"][0]["index_patterns"] == ["otel-v1-apm-logs-*"]


def test_dashboard_references_are_complete_and_stable() -> None:
    objects = provisioner.dashboard_objects()
    identities = {(object_type, object_id) for object_type, object_id, _ in objects}
    assert len(identities) == len(objects)
    assert ("dashboard", "shared-observability-overview") in identities

    dashboard = next(
        payload
        for object_type, object_id, payload in objects
        if object_type == "dashboard" and object_id == "shared-observability-overview"
    )
    for reference in dashboard["references"]:
        assert (reference["type"], reference["id"]) in identities


def test_alerts_cover_ingest_errors_and_rerp_freshness() -> None:
    monitors = {monitor["name"]: monitor for monitor in provisioner.desired_monitors()}

    assert set(monitors) == {
        "Telemetry metrics stale",
        "Telemetry error logs detected",
        "RERP API metrics stale",
    }
    assert all(monitor["enabled"] for monitor in monitors.values())
    assert all(
        monitor["triggers"][0]["query_level_trigger"]["actions"] == []
        for monitor in monitors.values()
    )


def test_existing_monitors_accepts_alerting_api_root_source_shape() -> None:
    class Client:
        def request(self, *_args: object, **_kwargs: object) -> tuple[int, object]:
            return 200, {
                "hits": {
                    "hits": [
                        {
                            "_id": "monitor-id",
                            "_seq_no": 4,
                            "_primary_term": 1,
                            "_source": {"name": "Telemetry metrics stale"},
                        }
                    ]
                }
            }

    monitors = provisioner.existing_monitors(Client())

    assert monitors["Telemetry metrics stale"][0]["_id"] == "monitor-id"


def test_collector_filters_debug_and_data_prepper_rotates_daily() -> None:
    profile = ROOT / "deployment-configuration/profiles/dev/observability"
    otel = yaml.safe_load((profile / "helm-values-otel.yaml").read_text())
    prepper = yaml.safe_load((profile / "helm-values-data-prepper.yaml").read_text())

    processors = otel["config"]["processors"]
    assert processors["memory_limiter"]["limit_mib"] == 192
    assert "filter/drop-low-severity" in processors
    assert otel["config"]["service"]["pipelines"]["logs"]["processors"] == [
        "memory_limiter",
        "filter/drop-low-severity",
        "batch",
    ]
    assert "debug" not in otel["config"]["exporters"]

    pipelines = prepper["pipelineConfig"]["config"]
    metric_sink = pipelines["otel-metrics-pipeline"]["sink"][0]["opensearch"]
    log_sink = pipelines["otel-logs-pipeline"]["sink"][0]["opensearch"]
    assert metric_sink["index"] == "otel-v1-apm-metrics-%{yyyy.MM.dd}"
    assert log_sink["index"] == "otel-v1-apm-logs-%{yyyy.MM.dd}"
