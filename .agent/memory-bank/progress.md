# Progress

## 2026-07-16 — Helm valuesFrom

Pushed: `52fed52` feat(profiles): Helm valuesFrom overlays for platform charts

Verified on ms02 (rev `main@sha1:52fed52`):
- `profile-config` → 10 resources (includes redis)
- ConfigMaps present; stack-redis dependsOn profile-config-redis
- HelmReleases Ready: postgres-ha, minio, redis, opensearch, dashboards, data-prepper

## Earlier — GitOpsSets audit migration

- `c661f6e` / `21d8484` / `95d742c` / `45302e0`

## Earlier — profiles on main

- `d54a6da` / `8ee45b3`

Next: FreeRADIUS/Squid → SOPS; MetalLB annotation dryness.
