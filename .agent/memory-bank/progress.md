# Progress — shared-gitops-k8s-cluster

## 2026-07-15

### Phase 2 — done
Flux + GitOpsSets on Multipass `dev` with local registry images.

### Phase 3 — in progress (backup gate)
Enabled / enabling:
- namespaces, cluster, cylon-infra, platform-dev-tls, postgres-ha
- **minio** (Flux component; Retain hostPath; removed from Tilt buckets kustomize)
- **postgres-backup** (CronJob pg_dumpall → MinIO)

### Postgres PVC reuse
- Old primary disks gone; HA PVs patched Retain; `local-path-retain` SC

### Remaining after backup verified
platform-data (redis/messaging/…), observability, ai, openbao
