# Progress

## 2026-08-29 — Flux commit for business OTEL

- Committed otel business classify, short-field pipeline fields, PW dashboards,
  otel-logs agent, docs; push so Flux stops acquitting live patches.

2026-08-29 — OSD dashboards + live business events

- Regenerated + imported NDJSON (`pricewhisperer-services` 13 objs, `logs-explore` 16).
- Live OS hits: market `pw business event` with operation/error_kind/symbol.
- Docs: Discover queries for PW business in `docs/observability-opensearch.md`.
- Collector classify `event_category:business` pending Flux apply.

## 2026-08-29 — PW OTEL instrumentation (audit implementation)

- Added `microservices/pw_telemetry` (BusinessEvent + init_worker).
- Wired into market/orders/news/calendar/brokerage impls + 4 ingestors.
- Workspace: `pw_telemetry` member + opentelemetry `[patch]` aligned with BRRTRouter.
- ms02: `cargo test -p pw_telemetry` OK; `cargo check` on instrumented crates OK.

## 2026-08-29 — PW telemetry coverage audit (read-only)

- BRRTRouter baseline: `otel.rs` OTLP via `OTEL_EXPORTER_OTLP_ENDPOINT`;
  `service.rs` `http_request` span + INFO "Request completed"; MetricsMiddleware `/metrics`.
  `TracingMiddleware` exists but is **not** wired in PW mains.
- Trader READY services: 0 well-instrumented; market/orders/news/calendar/brokerage = partial
  (`eprintln!`); rest = framework-only stubs.
- Ingestors: `tracing_subscriber::fmt().json().init()` only — no microscaler_observability/OTLP.
- Top gaps: confirm_order/IBKR, get_ticker, candles/hot-tier, place_order risk, options chain,
  ingestor OTLP bootstrap.

## 2026-08-29 — PW observability parity with Hauliage

- PriceWhisperer: prometheus.io annotations on microservice chart; `common.yaml`
  observability + `RUST_LOG=debug` / stack `0x40000` (hauliage-style).
- shared-gitops: `prometheus/pw` receiver in `helm-values-otel.yaml` + docs.
- OTLP for HTTP services was already live; this pass adds metrics scrape parity.

## 2026-08-29 — Hauliage/loadlinker OTLP path inventory (read-only)

- Apps push OTLP **gRPC** to `http://otel-collector.observability.svc.cluster.local:4317`
  via `OTEL_EXPORTER_OTLP_ENDPOINT` (Helm chart → Deployment env).
- Init: `brrtrouter::otel::init_logging_with_config` → `microscaler_observability::init`
  (traces + logs). Metrics stay Prometheus scrape (`prometheus/loadlinker`).
- Product source of truth: `hauliage` repo (`github.com/microscaler/haulage`)
  `deployment-configuration/profiles/dev/hauliage/core/services/values/common.yaml`
  + `helm/hauliage-microservice/templates/deployment.yaml`.
- shared-gitops owns collector only (`observability` stack); no hauliage OTEL
  profile ConfigMap in platform repo. Namespace = `loadlinker`; `OTEL_SERVICE_NAME`
  = short service id (`bff`, `fleet`, …).

## 2026-08-29 — PriceWhisperer OTLP inventory (read-only)

- Confirmed repo path `PriceWhisperer`; ns `pw` live Deployments inventoried via k8s MCP (manifests + live env).
- BRRTRouter services: OTLP already wired (parity with hauliage consignments).
- Workers / pw-mock / SPAs: gaps documented; recommended change list in chat.
- No code changes this session.

## 2026-08-29 — otel-collector-logs nginx SPA scrape

- Added HelmRelease `otel-collector-logs` (DaemonSet filelog) for nginx SPA
  stdout: `pw` trader/website/platform + `loadlinker` frontend → Data Prepper
  `:21892` → OpenSearch. Tags `log.source=nginx`; drops `kube-probe`.
- Gateway `otel-collector` Deployment unchanged (apps OTLP path).
- Docs: `docs/observability-opensearch.md` data-flow diagram + component table
  + retention note updated. No commit yet.

## 2026-07-16 — OpenGroupware Tilt host registration

Config updated (apply on ms02 still needed if shell was down):
- Ansible `tilt_user_units`: `tilt-opengroupware` port **10852**, workdir `opengroupware`
- `tilt-apps.yaml` + `apps.yaml`: opengroupware / ogw → 10852
- Docs/justfile/cluster-stop + legacy `deploy/tilt-opengroupware.service`

Apply:
```
cd ~/Workspace/microscaler/shared-gitops-k8s-cluster && just tilt-units-apply
systemctl --user enable --now tilt-opengroupware.service
cd ~/Workspace/microscaler/shared-k8s-cluster && just lan-proxy-up
```
UI: `http://tilt-opengroupware.dev.microscaler.local/` (alias `tilt-ogw`)

## 2026-07-16 — Clone rename seasame-idam → sesame-idam

- NFS dir renamed on ms02 (Mac path follows).
- Ansible `tilt_user_units` workdir + `apps.yaml` repo + systemd WorkingDirectory updated.
- `tilt-sesame-idam.service` active with `WorkingDirectory=.../sesame-idam`.
- Reopen Cursor workspace at `.../microscaler/sesame-idam` (old path gone; no symlink).

## 2026-07-16 — Product GitOps cutover (sesame + hauliage)

- Wired `product-components` for `sesame-idam` + `hauliage` (Git URLs: `sesame-idam` / `haulage`).
- Rerp-style split locked in both products:
  - **Flux Job** `scripts/db-init-job.sh` — Pgpool contract, role, database, schema, grants, login verify. No migrations.
  - **Tilt** — `image-*-db-init` publishes bootstrap image; `*-apply-migrations` applies Lifeguard SQL/seeds.
- Commits: sesame `4b0fb07` (+ image automation), hauliage `817935c` (+ image automation).
- Unblocked Pgpool: secret had `rerp,sesame_idam,hauliage` but running pods needed rollout restart to reload `pool_passwd`.

### Bootstrap Ready (2026-07-16 ~17:35)
- Jobs Complete: `sesame-idam-db-init`, `hauliage-db-init` (role/DB/schema only).
- KS Ready: `sesame-idam-idam`, `hauliage-core`.
- Services KS installing HelmReleases — many ImageRepos missing (`dev-0` / no registry tags yet); Helm rate-limit noise while catching up.
- Lesson: never `kubectl apply -k` SOPS bootstrap dirs without decrypt — writes ciphertext as password. Flux SOPS decrypt is the path.
- Lesson: after adding Pgpool custom users, rollout-restart `postgres-ha-pgpool` so `pool_passwd` reloads.

### Still open
- Publish microservice `dev-N` images; enable `FLUX_OWNS_DEPLOY=1` on tilt units.
- Hauliage workers/frontend into profile later.
- `tilt trigger *-apply-migrations` after Flux foundation Ready.

## Earlier — Helm valuesFrom

Pushed: `52fed52` feat(profiles): Helm valuesFrom overlays for platform charts

## Earlier — GitOpsSets / profiles

- `c661f6e` / `21d8484` / `95d742c` / `45302e0` / `d54a6da` / `8ee45b3`
