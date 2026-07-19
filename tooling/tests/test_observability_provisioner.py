"""Contract tests for the OpenSearch observability provisioner."""

from __future__ import annotations

import importlib.util
import json
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


def test_trace_policy_keeps_rollover_and_adds_seven_day_delete() -> None:
    policy = provisioner.trace_lifecycle_policy(7)["policy"]

    current = policy["states"][0]
    assert current["name"] == "current_write_index"
    assert current["actions"][0]["rollover"] == {
        "min_size": "50gb",
        "min_index_age": "24h",
        "copy_alias": False,
    }
    assert current["transitions"] == [
        {"state_name": "delete", "conditions": {"min_index_age": "7d"}}
    ]
    assert policy["states"][1]["actions"] == [{"delete": {}}]


def test_correlation_queries_reference_trace_fields() -> None:
    assert "traceId" in provisioner.CORRELATED_LOGS_QUERY
    assert "traceId" in provisioner.ERROR_LOGS_WITH_TRACE_QUERY
    assert provisioner.TRACES_PATTERN == "otel-v1-apm-span-*"


def test_dashboard_import_helpers_exist() -> None:
    assert hasattr(provisioner, "import_dashboard_bundles")
    assert hasattr(provisioner, "cleanup_deprecated_saved_objects")


def test_logs_short_fields_pipeline_copies_otel_paths() -> None:
    pipeline = provisioner.logs_short_fields_pipeline()
    script = pipeline["processors"][0]["script"]["source"]
    assert "ctx['method'] = ctx['log.attributes.method']" in script
    assert (
        "ctx['name'] = ctx['resource.attributes.k8s@namespace@name']" in script
    )
    template = provisioner.logs_index_template("otel-v1-apm-logs-*")
    assert (
        template["template"]["settings"]["default_pipeline"]
        == provisioner.LOGS_SHORT_FIELDS_PIPELINE
    )
    assert "method" in template["template"]["mappings"]["properties"]


def test_index_field_specs_apply_short_custom_labels() -> None:
    class FakeClient:
        def request(self, path: str, **_kwargs):
            assert "index_patterns/_fields_for_wildcard" in path
            return 200, {
                "fields": [
                    {
                        "name": "log.attributes.method",
                        "type": "string",
                        "esTypes": ["keyword"],
                        "searchable": True,
                        "aggregatable": True,
                    },
                    {
                        "name": "resource.attributes.k8s@namespace@name",
                        "type": "string",
                        "esTypes": ["keyword"],
                        "searchable": True,
                        "aggregatable": True,
                    },
                    {
                        "name": "serviceName",
                        "type": "string",
                        "esTypes": ["keyword"],
                        "searchable": True,
                        "aggregatable": True,
                    },
                ]
            }

    fields = json.loads(
        provisioner.fetch_index_fields(
            FakeClient(),
            "otel-v1-apm-logs*",
            popular_fields=["log.attributes.method"],
        )
    )
    by_name = {field["name"]: field for field in fields}
    assert by_name["log.attributes.method"]["customLabel"] == "method"
    assert (
        by_name["resource.attributes.k8s@namespace@name"]["customLabel"] == "name"
    )
    assert "customLabel" not in by_name["serviceName"]


def test_alerts_cover_ingest_errors_and_rerp_freshness() -> None:
    monitors = {monitor["name"]: monitor for monitor in provisioner.desired_monitors()}

    assert set(monitors) == {
        "Telemetry metrics stale",
        "Telemetry error logs detected",
        "RERP API metrics stale",
        "Postgres metrics stale",
        "Redis metrics stale",
        "Loadlinker P0 error burst",
        "Sesame auth error logs",
        "Loadlinker P0 traces stale",
        "Sesame auth traces stale",
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


def test_matching_indices_includes_legacy_and_daily_indices() -> None:
    class Client:
        requested_path = ""

        def request(self, path: str, **_kwargs: object) -> tuple[int, object]:
            self.requested_path = path
            return 200, [
                {"index": "otel-v1-apm-logs-2026.07.16"},
                {"index": "otel-v1-apm-logs"},
            ]

    client = Client()
    indices = provisioner.matching_indices(client, "otel-v1-apm-logs*")

    assert indices == ["otel-v1-apm-logs", "otel-v1-apm-logs-2026.07.16"]
    assert client.requested_path.startswith("_cat/indices/otel-v1-apm-logs*")


def test_collector_filters_debug_and_data_prepper_rotates_daily() -> None:
    profile = ROOT / "deployment-configuration/profiles/dev/observability"
    otel = yaml.safe_load((profile / "helm-values-otel.yaml").read_text())
    prepper = yaml.safe_load((profile / "helm-values-data-prepper.yaml").read_text())

    assert prepper["image"]["tag"] == "2.11.0"

    processors = otel["config"]["processors"]
    assert processors["memory_limiter"]["limit_mib"] == 384
    assert "filter/drop-low-severity" in processors
    assert processors["filter/drop-no-recorded-value"]["metrics"]["datapoint"] == [
        "flags == 1"
    ]
    assert otel["config"]["service"]["pipelines"]["logs"]["processors"] == [
        "memory_limiter",
        "filter/drop-epoll-io",
        "filter/drop-health-probes",
        "transform/classify-log-signal",
        "filter/drop-low-severity",
        "batch",
    ]
    assert "filter/drop-epoll-io" in processors
    assert "filter/drop-health-probes" in processors
    assert "transform/classify-log-signal" in processors
    assert "debug" not in otel["config"]["exporters"]
    assert otel["config"]["service"]["pipelines"]["metrics"]["processors"] == [
        "memory_limiter",
        "filter/drop-no-recorded-value",
        "batch",
    ]
    metrics_receivers = otel["config"]["service"]["pipelines"]["metrics"]["receivers"]
    assert "otlp" in metrics_receivers
    assert "prometheus/data" in metrics_receivers
    data_scrape = otel["config"]["receivers"]["prometheus/data"]["config"][
        "scrape_configs"
    ]
    job_names = {job["job_name"] for job in data_scrape}
    assert job_names == {"postgres", "redis"}
    postgres_job = next(job for job in data_scrape if job["job_name"] == "postgres")
    assert (
        "postgres-exporter.data.svc.cluster.local:9187"
        in postgres_job["static_configs"][0]["targets"]
    )
    keep = postgres_job["metric_relabel_configs"][0]["regex"]
    assert "pg_up" in keep
    assert "pg_stat_replication_pg_wal_lsn_diff" in keep
    assert "pgpool" not in keep

    pipelines = prepper["pipelineConfig"]["config"]
    metric_sink = pipelines["otel-metrics-pipeline"]["sink"][0]["opensearch"]
    log_sink = pipelines["otel-logs-pipeline"]["sink"][0]["opensearch"]
    assert metric_sink["index"] == "otel-v1-apm-metrics-%{yyyy.MM.dd}"
    assert log_sink["index"] == "otel-v1-apm-logs-%{yyyy.MM.dd}"


def test_dashboards_config_disables_data_sources_for_gitops_index_patterns() -> None:
    profile = ROOT / "deployment-configuration/profiles/dev/observability"
    dashboards = yaml.safe_load((profile / "helm-values-dashboards.yaml").read_text())
    config = dashboards["config"]["opensearch_dashboards.yml"]
    assert "data_source.enabled: false" in config
    # OSD 2.19 rejects opensearchDashboards.defaultRoute (CrashLoop).
    assert "defaultRoute" not in config


def test_helm_values_changes_trigger_release_reconciliation() -> None:
    profile = ROOT / "deployment-configuration/profiles/dev/observability"
    kustomization = yaml.safe_load((profile / "kustomization.yaml").read_text())
    helm_values = next(
        generator
        for generator in kustomization["configMapGenerator"]
        if generator["name"] == "observability-helm-values"
    )

    assert helm_values["options"]["labels"]["reconcile.fluxcd.io/watch"] == "Enabled"
