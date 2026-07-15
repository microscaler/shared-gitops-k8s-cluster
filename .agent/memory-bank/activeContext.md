# Active context — shared-gitops-k8s-cluster

Updated: 2026-07-15

## Status

Phase 3: **ns `data` platform workloads on Flux** (except hauliage `mosquitto`).

## Flux stacks (dev)

- namespaces, cluster, cylon-infra, platform-dev-tls
- postgres-ha, minio, postgres-backup
- **redis**, **messaging**, **pact**, **imgproxy**

## Still Tilt (shared-k8s-cluster)

- scheduling (faktory), pipeline (fluvio), observability, ai
- `mosquitto` in data ns is product (hauliage), not platform-data

## Notes

- Retain hostPath: minio, redis, mailpit, pact-postgres
- Heal: `just heal-minio-pvc`, `just heal-hostpath-pvc mailpit|pact`
- Backup: `just postgres-backup-now`

## Next

observability / scheduling / pipeline / openbao; fix postgres-ha Helm STS Ready
