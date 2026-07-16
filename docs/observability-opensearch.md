# OpenSearch-native observability

Status: **active in dev**. OpenSearch is the storage, analysis, dashboard, and
alert-evaluation platform. Grafana, Prometheus Server, Loki, Promtail, and
Jaeger are not part of the stack.

## Data flow

```text
applications/exporters
        │ OTLP gRPC/HTTP
        ▼
OpenTelemetry Collector
        │ traces :21890, metrics :21891, logs :21892
        ▼
Data Prepper
        │
        ▼
OpenSearch 2.19.x ── OpenSearch Dashboards 2.19.x
```

The Collector's Prometheus-format endpoint is a compatibility exporter only.
There is no Prometheus database or Grafana deployment. OpenSearch is the
durable metric store.

| Component | Dev delivery |
|-----------|--------------|
| OpenSearch | HelmRelease `opensearch`, single node, `zfs-iscsi` 30 GiB PVC |
| Dashboards | HelmRelease `opensearch-dashboards`, MetalLB `.227:5601` |
| Data Prepper | HelmRelease `data-prepper`, image 2.11, OTLP pipelines and pod-local server metrics on `:4900` |
| OTel Collector | HelmRelease `otel-collector`, OTLP MetalLB `.231` |
| Provisioner | Ten-minute CronJob reconciling lifecycle, saved objects, and monitors |

LAN entrypoint: `opensearch.dev.microscaler.local:5601`.

## Dev retention and volume control

`deployment-configuration/profiles/dev/observability/application.properties`
sets `OBSERVABILITY_RETENTION_DAYS=7`.

- Data Prepper writes daily `otel-v1-apm-metrics-YYYY.MM.DD` and
  `otel-v1-apm-logs-YYYY.MM.DD` indices.
- OpenSearch ISM policies delete metrics and logs when the index age reaches
  seven days.
- The legacy unsuffixed metrics and logs indices are attached to the same
  policies and stop receiving writes after the Data Prepper rollout.
- Dev stores `INFO` and above. Explicit `DEBUG` and `TRACE` records are dropped
  by the Collector before export; pod logs remain available for immediate
  development diagnosis.
- Dev telemetry indices use one primary and zero replicas because OpenSearch is
  deliberately single-node. This avoids permanently yellow indices and wasted
  capacity.
- The provisioner reconciles both legacy and daily indices, including indices
  created before their template existed, so all matching indices receive the
  lifecycle policy and single-node settings.

Seven days is a dev troubleshooting window, not an audit or financial-record
retention policy. Production retention and topology must be sized separately.

## Managed dashboard and alerts

The provisioner owns the `Shared observability overview` dashboard with:

- metric sample volume grouped by service;
- stored log volume grouped by service;
- recent error logs; and
- RERP API metric records.

OpenSearch Alerting evaluates these query-level monitors every five minutes:

- `Telemetry metrics stale` — no metric documents in ten minutes;
- `Telemetry error logs detected` — ERROR/FATAL records in five minutes;
- `RERP API metrics stale` — no `api_requests_total` records in ten minutes.

Alerts are visible and acknowledgeable in OpenSearch Dashboards. Notification
actions are intentionally empty until a secret-backed email/webhook channel and
ownership/escalation policy are selected; monitor evaluation does not depend on
that later integration.

## Reconcile and verify

Run cluster commands on ms02 with the shared-k8s kubeconfig:

```bash
export KUBECONFIG=~/Workspace/microscaler/shared-k8s-cluster/kubeconfig/shared-k8s.yaml

flux reconcile kustomization profile-config-observability --with-source
flux reconcile kustomization stack-observability --with-source
just observability-provision-now
```

Expected terminal line:

```text
observability provisioning passed: retention=7d monitors=3 saved_objects=7
```

The provisioner is idempotent. Re-running it updates only objects carrying its
stable IDs/names and refuses to replace an unexpected lifecycle policy already
attached to a legacy index.

Implementation references:

- [OpenSearch ISM policies](https://docs.opensearch.org/latest/im-plugin/ism/policies/)
- [OpenSearch Alerting API](https://docs.opensearch.org/latest/observing-your-data/alerting/api/)
- [Data Prepper OpenSearch sink](https://docs.opensearch.org/latest/data-prepper/pipelines/configuration/sinks/opensearch/)
- [OpenTelemetry filtering and transformation](https://opentelemetry.io/docs/collector/transforming-telemetry/)

## Current dev security boundary

OpenSearch security is disabled in the current private dev cluster. This is not
a production design. Before any non-dev exposure, enable the Security plugin,
TLS, least-privilege Data Prepper credentials, dashboard RBAC, and protected
alert notification metadata.
