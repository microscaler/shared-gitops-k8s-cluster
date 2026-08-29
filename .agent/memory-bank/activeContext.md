# Active Context

**Last updated:** 2026-08-29 — committing PW business OTEL so Flux keeps it.

## Just done

### Commit path for Flux (2026-08-29)

Live patches alone get overwritten: profile-config + provisioner CronJob
reconcile from git. Commit/push includes:
- `event_category:business` classify + `prometheus/pw` scrape in helm-values-otel
- short-field copies (operation/outcome/error_kind/symbol) in provisioner
- PW business Discover searches + dashboard panels (regenerated NDJSON)
- otel-collector-logs DaemonSet for nginx SPA filelog
- docs/observability-opensearch.md Discover queries

Provisioner CronJob was temporarily suspended while pipeline was patched live;
resume after Flux applies new provisioner ConfigMap.

### OSD + business telemetry verification

- Confirmed `event_category:business` on new `pw business event` docs after
  live otel CM patch (pre-commit).
- `search_tickers` returns 200 + business events; `get_ticker` still WrongType/db
  and can hang the may worker after errors.


### Registry push: digest did not match (2026-08-29)

**Symptom:** Tilt `image-pricewhisperer-backtests` fails on
`docker buildx … oci-mediatypes=true` retag to `:dev-<ns>` with
`provided digest did not match uploaded content` (zot @ 10.177.76.220:5000).

**Fix:**
1. `BRRTRouter/tooling/.../build_image_simple.py` — push `:tilt` via buildx OCI
   (with retries) instead of plain `docker push` schema2.
2. `PriceWhisperer/Tiltfile` (+ `.ui`) — prefer `buildx imagetools create` for
   `:dev-*` (no blob re-upload); fall back to buildx FROM with 3 retries.

### Zot wipe + recreate (2026-08-29)

Suspended `stack-cluster`, deleted deploy/zot + pvc/zot-data + Released PV
(Retain). Resumed Flux → fresh **60Gi** PVC, zot Ready, empty catalog.
MetalLB Service `registry` @ `10.177.76.220:5000` preserved.
Next: republish product images via Tilt (PW/hauliage/sesame).


### PW observability parity (code on NFS)

Helm scrape annotations + common.yaml + shared-gitops `prometheus/pw` — unpushed.
