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

The Collector also scrapes Postgres HA, Pgpool, and Redis Prometheus exporters in
the `data` namespace. Dev Dashboards runs with `data_source.enabled: false` so
GitOps-provisioned index patterns register without a separate data-source object.

| Component | Dev delivery |
|-----------|--------------|
| OpenSearch | HelmRelease `opensearch`, single node, `zfs-iscsi` 30 GiB PVC |
| Dashboards | HelmRelease `opensearch-dashboards`, MetalLB `.227:5601` |
| Data Prepper | HelmRelease `data-prepper`, image 2.11, OTLP pipelines |
| OTel Collector | HelmRelease `otel-collector`, OTLP MetalLB `.231`, Prometheus scrape |
| Pgpool exporter | Deployment `postgres-ha-pgpool-exporter` in `data`, `:9719` |
| Provisioner | Ten-minute CronJob reconciling lifecycle, saved objects, and monitors |

LAN entrypoints:

| URL | Purpose |
|-----|---------|
| `http://opensearch.dev.microscaler.local/` | OpenSearch Dashboards (preferred) |
| `http://192.168.1.189:5601/` | Legacy LAN proxy |
| `http://10.177.76.227:5601/` | MetalLB (ms02 / in-cluster) |
| `192.168.1.189:4317` / `10.177.76.231:4317` | OTLP gRPC ingest |

## Dev retention and volume control

`deployment-configuration/profiles/dev/observability/application.properties`
sets `OBSERVABILITY_RETENTION_DAYS=7`.

- Data Prepper writes daily `otel-v1-apm-metrics-YYYY.MM.DD` and
  `otel-v1-apm-logs-YYYY.MM.DD` indices.
- OpenSearch ISM policies delete metrics and logs when the index age reaches
  seven days. Raw spans retain Data Prepper's daily rollover and are deleted at
  the same age instead of accumulating indefinitely.
- The legacy unsuffixed metrics and logs indices are attached to the same
  policies and stop receiving writes after the Data Prepper rollout.
- Dev stores `INFO` and above. Explicit `DEBUG` and `TRACE` records are dropped
  by the Collector before export; pod logs remain available for immediate
  development diagnosis.
- Prometheus staleness markers carry the OpenTelemetry
  `NO_RECORDED_VALUE` flag rather than a measurement. The Collector drops those
  flagged points before Data Prepper so they cannot become false zeroes or
  invalid null-valued gauges in OpenSearch.
- Dev telemetry indices use one primary and zero replicas because OpenSearch is
  deliberately single-node. This avoids permanently yellow indices and wasted
  capacity.
- The provisioner reconciles both legacy and daily indices, including indices
  created before their template existed, so all matching indices receive the
  lifecycle policy and single-node settings.

Seven days is a dev troubleshooting window, not an audit or financial-record
retention policy. Production retention and topology must be sized separately.

## Managed dashboards (GitOps NDJSON)

Dashboard bundles live in
`gitops/root/components/observability/dashboards/*.ndjson` (one file per
dashboard, including referenced visualizations and saved searches). Regenerate
after editing `dashboard_definitions.py`:

```bash
python3 tooling/generate_observability_dashboards.py
```

The provisioner imports NDJSON bundles, reconciles index patterns dynamically,
and deletes deprecated saved objects from earlier iterations.

### Dashboard tiers

| Tier | Purpose |
|------|---------|
| **Log hubs** | Unified log triage — errors, WARN, trace-correlated, DB pressure |
| **Health / SLO** | Traces and metrics only; link out to log hubs |
| **War room** | Cross-signal pivot by traceId (incident response) |
| **Platform** | Postgres, Pgpool, Redis infrastructure |

| Dashboard ID | Purpose |
|--------------|---------|
| **platform-logs-explore** | All services — ERROR, WARN, trace-correlated logs |
| **loadlinker-logs-explore** | Loadlinker P0 + P1 log triage |
| **sesame-logs-explore** | All six Sesame-IDAM services |
| **platform-postgres-connections** | Postgres/Pgpool saturation split by `loadlinker` / `sesame-idam` |
| **platform-data-namespace** | Shared `data` namespace Postgres, Pgpool, Redis |
| **platform-apm-correlation** | Incident war room: traceId pivot across logs, spans, DB |
| **loadlinker-health** | P0 RED: `bff`, `bidding`, `consignments`, `notifications` |
| **loadlinker-bff-edge** | BFF routes, SLO p95 target 500 ms |
| **loadlinker-sesame-auth** | BFF → Sesame auth dependency (traces) |
| **sesame-platform-health** | All six Sesame-IDAM services |
| **sesame-auth-critical-path** | Login, session, authz-core (authz SLO p95 50 ms) |

Dev SLO starting points (refine against measured baselines):

| Service / path | Target |
|----------------|--------|
| Loadlinker BFF p95 | 500 ms |
| Loadlinker bidding p95 | 800 ms |
| Sesame authz-core p95 | 50 ms |

Index patterns (use in **Discover**):

| Pattern | Time field | Correlation keys |
|---------|------------|------------------|
| `otel-v1-apm-metrics*` | `time` | `serviceName`, `metric.attributes.consumer_namespace` |
| `otel-v1-apm-logs*` | `observedTime` | `serviceName`, `traceId`, `spanId`, `body` |
| `otel-v1-apm-span-*` | `startTime` | `traceId`, `spanId`, `serviceName`, `name` |

**Cross-signal correlation:** pick a `traceId` from **HTTP request spans** or
**Errors with trace context**, paste into Discover on logs or traces, and align
the time picker with **Postgres connections** to relate app events to DB pressure.

OpenSearch Alerting evaluates these query-level monitors every five minutes:

- `Telemetry metrics stale` — no metric documents in ten minutes;
- `Telemetry error logs detected` — ERROR/FATAL records in five minutes;
- `RERP API metrics stale` — no `api_requests_total` records in ten minutes;
- `Postgres metrics stale` — no `pg_*` metric documents in ten minutes;
- `Redis metrics stale` — no `redis_*` metric documents in ten minutes.

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
observability provisioning passed: retention=7d monitors=5 saved_objects=24
```

Cluster health may show **yellow** on a single-node dev cluster because
OpenSearch plugin indices still declare replica shards that cannot be assigned.
Telemetry indices use zero replicas; yellow status does not block Dashboards or
ingest.

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
