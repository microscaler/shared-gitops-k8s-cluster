# Agent memory — observability log signal

Updated: 2026-07-20 (Logs mid-row layout: status full-height; avg+donut stacked right)

## Status
- Epoll + memory dropped at collector; health-probe Request logs dropped.
- Request completed/received kept (DEBUG exception) with method/path/duration; tagged `event_category:http`.
- `time_unix_nano` repaired from observed time (no more 1970 in detail).
- `log.attributes.message` copied from body for clearer detail labeling.
- BRRTRouter `d0b931a` promotes Request completed to INFO + status (needs service rebuild/rollout to take effect in images).
- Discover Signal columns include method/path/status/duration_ms.

## Managed dashboards
- **Logs** (`logs-explore`) — HTTP triage, volume, top paths / status / duration, signal stream.
- **DataPersistence** (`data-persistence`) — Lifeguard Postgres primary + streaming replicas + Redis (Pgpool retired).
  - URL: `http://opensearch.dev.microscaler.local/app/dashboards#/view/data-persistence`
  - Source: `dashboard_definitions.py` → `dashboards/data-persistence.ndjson`
  - Metrics index: `shared-observability-metrics` (`otel-v1-apm-metrics*`), time field `time`, value `value`
  - OTel scrape: `postgres-exporter.data:9187` (not postgres-ha); keep `pg_up`, `pg_replication_*`, `pg_stat_replication_pg_wal_lsn_diff`, backends/activity/size
  - Vega: streaming replicas table on `pg_stat_replication_pg_wal_lsn_diff` (`_metrics_vega_url` + `%timefilter%`)

## HTTP triage (done — status pie + mid-row layout)
- Saved search **Logs / HTTP** (`logs-http`): Lucene `event_class:application AND event_category:http`.
- Logs dashboard: guide → volume → Top paths | Status table (full mid height) | Avg + Status % donut (stacked right) → Signal stream (7 panels).
- Mid-row grid: status `x=28,h=14`; avg `x=38,y=17,h=7`; donut `x=38,y=24,h=7`.
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

Vega `href` requires `vis_type_vega.enableExternalUrls: true` in Dashboards
(`helm-values-dashboards.yaml`); otherwise canvas clicks fail silently.

## Top paths RPS + pSLO (done)
- Vega panel `logs-http-top-paths`: path | count | rps/15m | p95 ms | SLO ms (500) | pSLO (ok/breach).
- RPS = count / 900 (dashboard default 15m). OSD 2.19 does not reliably inject `%timefilter%` into Vega signals.
- Status-codes panel empty until access logs carry `log.attributes.status` (rebuild on BRRTRouter `d0b931a`).

## Status colors + volume click-zoom (done)
- Status pie is Vega: **2xx green / 3xx blue / 4xx amber / 5xx red**.
- Volume histogram is Vega: click a bar → dashboard `_g.time` zooms to that 30s bucket.

## Optional next
- Error-rate strip; trace deep-links; rebuild services on BRRTRouter `d0b931a` so `status` lands on access logs.
- Make RPS follow the selected time picker if OSD timefilter→Vega improves.
