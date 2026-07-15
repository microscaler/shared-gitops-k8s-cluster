# Active context — shared-gitops-k8s-cluster

Updated: 2026-07-15

## Status

Phase 3 gated on **postgres backups → MinIO** before more platform components.

## Locked decisions

- Separate GitOps repo (this one)
- Multi-cluster: `dev` / `staging` / `prod`
- Multipass shared-k8s = **`dev`**
- GitOpsSets for stack dryness
- Postgres: Bitnami HA + bitnamilegacy; `local-path-retain`
- **Backups:** `pg_dumpall` CronJob → MinIO bucket `postgres-backups`
- **MinIO:** hostPath `/var/lib/data/minio` on worker-1, PV reclaim **Retain**

## Stacks to enable (before redis/etc.)

1. `minio`
2. `postgres-backup` (after postgres-ha Ready)

Docs: `docs/postgres-backup.md`, `docs/postgres-pvc-reuse.md`
Recipes: `just heal-minio-pvc`, `just postgres-backup-now`

## Next

1. Commit + push gitops (minio + backup + retain SC)
2. Heal Terminating minio PVC on cluster
3. Verify first dump in `postgres-backups`
4. Then continue platform-data / observability / …
