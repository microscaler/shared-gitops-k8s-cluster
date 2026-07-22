# Agent memory — observability log signal

Updated: 2026-07-22 (OTel memory pressure — doubled again)

## Status
- **2026-07-22:** Same soft-refuse pattern recurred — OTel at ~1147Mi against
  limiter 1152Mi / pod 1536Mi (~300 refuses / 15m). Prepper healthy (~647Mi,
  0 restarts). Doubled OTel pod 1536→3072Mi, limiter 1152→2304Mi,
  spike 256→512Mi. Observe before further scrape cuts.
- **2026-07-21:** Empty dashboards — OTel `memory_limiter` refused scrapes
  (`data refused due to high memory usage`), then Data Prepper CPU-throttled
  at 500m (`DeadlineExceeded` exports). Raised OTel 512→1536Mi / limiter
  1152Mi (`6e7fb6f`); Prepper CPU 500m→2 / mem 768→1536Mi (`f3cc51c`);
  scrape only kube-state `:8080`; drop `kube_pod_info`.
- Epoll + memory dropped at collector; health-probe Request logs dropped.
- Request completed/received kept (DEBUG exception) with method/path/duration; tagged `event_category:http`.
- `time_unix_nano` repaired from observed time (no more 1970 in detail).
- `log.attributes.message` copied from body for clearer detail labeling.
- BRRTRouter `d0b931a` promotes Request completed to INFO + status (needs service rebuild/rollout to take effect in images).
- Discover Signal columns include method/path/status/duration_ms.

## Managed dashboards
- **Logs** (`logs-explore`) — HTTP triage, volume, top paths (p95 + Δ vs prior 15m) / status / duration, signal stream.
- **HTTP latency** (`http-latency`) — investigation room: overall p50/p95, path p95 timelines, top-path Δ, slow (≥500ms) Discover.
  - URL: `http://opensearch.dev.microscaler.local/app/dashboards#/view/http-latency`
  - Logs stays smoke-alarm; this board is trends / deviations.
- **DataPersistence** (`data-persistence`) — Lifeguard Postgres primary + streaming replicas + Redis (Pgpool retired).
  - URL: `http://opensearch.dev.microscaler.local/app/dashboards#/view/data-persistence`
  - Source: `dashboard_definitions.py` → `dashboards/data-persistence.ndjson`
  - Metrics index: `shared-observability-metrics` (`otel-v1-apm-metrics*`), time field `time`, value `value`
  - OTel scrape: `postgres-exporter.data:9187` (not postgres-ha); keep `pg_up`, `pg_replication_*`, `pg_stat_replication_pg_wal_lsn_diff`, backends/activity/size
  - Vega: streaming replicas table on `pg_stat_replication_pg_wal_lsn_diff` (`_metrics_vega_url` + `%timefilter%`)
- **k3s (dev)** (`k3s-dev`) — LAN Multipass k3s only (not GCP).
  - URL: `http://opensearch.dev.microscaler.local/app/dashboards#/view/k3s-dev`
  - Scrapes: `node-exporter` DaemonSet + `kube-state-metrics` via OTel `prometheus/k3s`
  - Filter: `metric.attributes.platform_component: k3s`
  - Nodes: k8s-cp-1 `10.177.76.137`, workers `.175` / `.141` / `.44`
  - KPI pitfall: metric `sum` over the time range totals every scrape → use
    cardinality (nodes/pods) or Vega `top_hits` then sum (unavailable replicas).
    OpenSearch has no `top_metrics` (ES-only) — that caused Bad Request tiles.
  - Phase gauges: always filter `value: 1` — kube-state emits every phase with
    0/1; cardinality without it counts all pods in every phase.
  - MemAvailable / rootfs: Vega scaled lines (MiB / GiB), not raw bytes.
  - Deploy unavailable table: namespace → Deployment → unavailable.
- Stale Loadlinker/Platform/Sesame dashboards are in `DEPRECATED_SAVED_OBJECTS` (deleted on provision).
  OSD *Recently viewed* is browser localStorage — clear nav history if old titles linger.

## HTTP triage (done — status pie + mid-row layout)
- Saved search **Logs / HTTP** (`logs-http`): Lucene `event_class:application AND event_category:http`.
- Logs dashboard: guide → volume → Top paths | Status table (full mid height) | Avg + Status % donut (stacked right) → Signal stream (7 panels).
- Mid-row grid (no guide): status `x=28,y=10,h=14`; avg `x=38,y=10,h=7`; donut `x=38,y=17,h=7`.
- Markdown guide panels removed from all managed dashboards (space).
- Panel `gridData.i` / `panelIndex` = object_id (not position) so layout updates stick.
- Provisioner deletes each dashboard before NDJSON import (overwrite alone left stale react-grid).
- Banner notes collector drops + HTTP deep-link; verified in OSD after delete+reimport.
- Provision: `just observability-provision-now` (ms02); generator: `tooling/generate_observability_dashboards.py`.

## Short Discover columns (in progress / local)
- OSD Data Explorer ignores index-pattern `customLabel` for headers.
- Ingest pipeline `observability-logs-short-fields` copies long OTel paths → root `name`, `method`, `path`, `status`, `duration_ms`, `event_class`, `event_category`, `has_trace`.
- Saved-search columns use those short names; Lucene/filters stay on `log.attributes.*`.
- Pre-pipeline docs lack short fields (empty cells until they age out).

## Detail view tip
Discover still has expand → Table/JSON. On the Logs dashboard, the **Signal stream**
Vega panel exposes **doc** / **around** on every row (same as View single document /
View surrounding documents) so you do not need to expand first.

Link shapes (OSD 2.19): use classic Discover, not data-explorer:
- **doc** → `/app/discover#/doc/<indexPattern>/<index>?id=<docId>` (Table/JSON)
- **around** → `/app/discover#/context/<indexPattern>/<docId>`
`/app/data-explorer/discover/#/doc|context/...` silently falls back to the search list.

Vega `href` requires `vis_type_vega.enableExternalUrls: true` in Dashboards
(`helm-values-dashboards.yaml`); otherwise canvas clicks fail silently.

## Top paths RPS + Δ + pSLO (done)
- Vega panel `logs-http-top-paths`: path | count | rps/15m | p95 ms | Δ ms | pSLO.
- Δ ms = current p95 − prior equal 15m window (`now-30m…now-15m`); amber >50ms/50%, red >200ms or SLO breach.
- RPS = count / 900 (dashboard default 15m). OSD 2.19 does not reliably inject `%timefilter%` into Vega signals.
- Status-codes panel empty until access logs carry `log.attributes.status` (rebuild on BRRTRouter `d0b931a`).

## HTTP latency board (done)
- Dashboard `http-latency`: request count, p50/p95/avg KPIs, overall p50/p95 timeline + SLO line, top-path p95 timeline, top-paths Δ table, slow (≥500ms) saved search — no markdown guide panel (space).
- Default time `now-1h`; linked from Logs guide.

## Status colors + volume click-zoom (done)
- Status pie is Vega: **2xx green / 3xx blue / 4xx amber / 5xx red**.
- Donut has no on-arc labels; legend shows `200 - 100%` (status + integer %).
- Volume histogram is Vega: click a bar → dashboard `_g.time` zooms to that 30s bucket.

## Optional next
- Error-rate strip; trace deep-links; rebuild services on BRRTRouter `d0b931a` so `status` lands on access logs.
- Make RPS follow the selected time picker if OSD timefilter→Vega improves.
- k3s-dev: CPU % (from `node_cpu_seconds_total` rate), MetalLB VIP / Envoy panels, Flux HelmRelease health.
