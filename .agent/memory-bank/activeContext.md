# Active Context

**Last updated:** 2026-07-16 — Helm valuesFrom overlays live on dev.

## Config layout

```
deployment-configuration/profiles/<env>/<component>/
  application.properties     # app KEY=value → ConfigMap (envFrom)
  helm-values.yaml           # Helm overlay → ConfigMap → HR valuesFrom
  application.secrets.env    # SOPS secrets
```

HelmRelease `spec.values` = structural only (existingSecret, MetalLB, affinity).
Env knobs live in `helm-values*.yaml`.

## valuesFrom (Ready)

| Chart | ConfigMap |
|-------|-----------|
| postgres-ha | `postgres-ha-helm-values` |
| minio | `minio-helm-values` |
| redis | `redis-helm-values` (+ new `profile-config-redis`) |
| opensearch / dashboards / data-prepper | `observability-helm-values` (keys) |

## Next (backlog)

1. FreeRADIUS / Squid passwords → SOPS.
2. MetalLB annotation patches / LAN proxy sync.
3. Staging/prod Matrix enablement when clusters exist.
