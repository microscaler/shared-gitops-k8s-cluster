# Active Context

**Last updated:** 2026-07-16 — application.properties migration started.

## Profiles (SMC)

```
deployment-configuration/profiles/dev/<component>/
  application.properties   # → ConfigMap
  application.secrets.env  # → Secret (SOPS)
```

Migrated to properties: pact, messaging, imgproxy, postgres-backup, democratic-csi, cylon-infra/routellm.

Flux GitOpsSet renamed: `profile-config` (was profile-secrets).

Still in Helm values: observability, postgres-ha, minio, redis (replicas/tags/storage).
