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
        │ transform/classify-log-signal (event_category on logs, no drop)
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

### Field filter sidebar (Logz.io-style)

OpenSearch **Dashboard** embeds cannot host a left-hand Selected / Available
fields panel. That UI is **Discover only**.

| Surface | Left field sidebar | Use for |
|---------|--------------------|---------|
| **Discover** (canonical) | Yes — Search field names, Selected / Available / Popular | Day-to-day log triage and filtering |
| **Dashboard `logs-explore`** | No — query bar + filter pills only | Overview / embeds; banner links to Discover |

Primary log exploration is GitOps-managed:

- **Discover (default landing)** — field sidebar, histogram, and document table (Signal scope)
- **Dashboard (`logs-explore`)** — Discover banner + signal histogram + stream
- **Filter hierarchy** — **namespace** → **application** → **time** → **event_class** / **event_category**
- **Selected / Popular fields** — `k8s.namespace.name`, `serviceName`, `severityText`, `event_class`, `event_category`, `has_trace`
- **Namespaces** — real cluster namespaces (`loadlinker`, `sesame-idam`, `rerp`). No `microscaler` ns
- **Epoll drop (collector)** — may `add/del/mod fd … epoll select` is dropped by `filter/drop-epoll-io` before export (was ~99% of volume)
- **Runtime noise tagging** — Collector sets `event_class:runtime_noise` with `event_category`:
  - `runtime_metrics` — BRRTRouter memory stats
  - `runtime_config` — may `set workers=` / `set stack size=`
  - `framework_lifecycle` — BRRTRouter handler registration, validator cache, routing table, metrics path pre-register
  These stay indexed; open **Logs / Runtime noise** to select them. Epoll is not indexed.
- **Landing page** — Discover saved searches (Signal); provisioner sets `defaultIndex` to logs. Do not set `opensearchDashboards.defaultRoute` in helm values (OSD 2.19 rejects it)

### Saved searches (Discover → Open)

| Title | Purpose |
|-------|---------|
| **Logs / Signal** | Application logs only (`event_class:application`) — default triage |
| **Logs / Errors** | WARN+ within signal |
| **Logs / Auth** | `sesame-idam` signal |
| **Logs / BFF** | `loadlinker` + `serviceName:bff` signal |
| **Logs / Runtime noise** | System noise (`event_class:runtime_noise`) — select *for* trash |

### Two-click filter path

1. Expand **namespace** → Filter for `sesame-idam` (or `loadlinker` / `rerp`)
2. Expand **serviceName** → values are now scoped to that namespace
3. Adjust **time** last; optionally filter `event_category` / `has_trace`

Source: `gitops/root/components/observability/dashboards/logs-explore.ndjson`.
Regenerate after editing `dashboard_definitions.py`:

```bash
python3 tooling/generate_observability_dashboards.py
```

Direct URLs:

| View | URL |
|------|-----|
| **Discover (field sidebar)** | `http://opensearch.dev.microscaler.local/app/data-explorer/discover` |
| Dashboard | `http://opensearch.dev.microscaler.local/app/dashboards#/view/logs-explore` |

**Example Lucene queries** (search bar):

| Goal | Query |
|------|-------|
| Signal (default) | `log.attributes.event_class:application` |
| Runtime noise only | `log.attributes.event_class:runtime_noise` |
| Memory stats only | `log.attributes.event_category:runtime_metrics` |
| may config only | `log.attributes.event_category:runtime_config` |
| BRRTRouter lifecycle only | `log.attributes.event_category:framework_lifecycle` |
| Errors | `log.attributes.event_class:application AND severityText:(ERROR OR FATAL OR WARN)` |
| Auth ns | `resource.attributes.k8s@namespace@name:sesame-idam AND log.attributes.event_class:application` |
| With trace | `log.attributes.has_trace:true` |
| Free text | `"connection pool"` |

Index patterns (Discover or raw queries):

| Pattern | Time field | Key fields |
|---------|------------|------------|
| `otel-v1-apm-logs*` | `observedTimestamp` | `k8s.namespace.name`, `serviceName`, `event_class`, `event_category`, `has_trace`, `body`, `severityText` |
| `otel-v1-apm-metrics*` | `time` | `serviceName`, `name`, `value` |
| `otel-v1-apm-span-*` | `startTime` | `traceId`, `spanId`, `serviceName`, `name` |

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
observability provisioning passed: retention=7d monitors=9 dashboard_bundles=1 saved_objects=3
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
