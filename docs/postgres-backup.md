# Postgres logical backups → MinIO

- **Status**: active (dev)
- **Date**: 2026-07-15
- **Depends on**: `stack-postgres-ha`, `stack-minio`

## Why

HA Postgres disks were recreated empty after a Delete-reclaim cutover. Before migrating
more platform components we need a recoverable dump path. Backups land in MinIO so the
object store (Retain hostPath) is the recovery source of truth.

## Topology

| Piece | Detail |
|-------|--------|
| Dump | `pg_dumpall` from `postgres-ha-postgresql-0` (primary), gzip |
| Upload | `minio/mc` → bucket `postgres-backups` |
| Schedule | CronJob every 6h; on-demand via `just postgres-backup-now` |
| Retention | Delete objects older than 7 days |
| Content gate | Every uploaded dump must contain each `REQUIRED_DATABASES` entry (`rerp` in dev) |
| MinIO disk | PV `minio-pv` → hostPath `/var/lib/data/minio` on `k8s-worker-1`, **Retain** |

## Enable on dev

```bash
mkdir -p gitops/clusters/dev/inventory/stacks/{minio,postgres-backup}
touch gitops/clusters/dev/inventory/stacks/minio/.gitkeep
touch gitops/clusters/dev/inventory/stacks/postgres-backup/.gitkeep
git commit && git push
flux reconcile source git shared-gitops -n flux-system
```

Enable **minio** first (or together); backup Jobs retry until MinIO and the primary accept connections.

## Verify

```bash
kubectl -n data get cj postgres-backup
just postgres-backup-now
# From a debug pod or LAN:
# mc alias set local http://10.177.76.226:9000 minio 'minio-dev-password-change-me'
# mc ls local/postgres-backups/
```

The Job validates required database creation and connection sections before it
uploads. An object in MinIO is therefore evidence that the configured product
databases were present, but it is not a substitute for the disposable restore
drill below.

## Restore (dev)

```bash
# Download dump
mc cp local/postgres-backups/postgres-all-STAMP.sql.gz .
gunzip -c postgres-all-STAMP.sql.gz | \
  PGPASSWORD=postgres psql -h 10.177.76.224 -U postgres -d postgres
```

Prefer restoring against Pgpool LB (`postgres` Service) once HA is healthy. For a
brand-new empty cluster, restore after `stack-postgres-ha` is Ready.

Never test a whole-cluster `pg_dumpall --clean` restore against the live dev
cluster. Use a disposable PostgreSQL container or an isolated recovery cluster,
then prove that the `rerp` database opens and contains the expected schema.

The automated disposable drill is:

```bash
just postgres-backup-restore-drill rerp
```

It retrieves the latest MinIO object without printing credentials or dump
content, restores into a temporary PostgreSQL 17 container, checks the `rerp`
schema table count, and destroys the container and downloaded dump.

## MinIO PVC stuck Terminating

```bash
just heal-minio-pvc
```

Manual outline: scale down minio/imgproxy → clear PVC/PV finalizers (Retain keeps
hostPath) → Flux/`kubectl apply -k` recreates claim against the same path → scale imgproxy back.
## Related

- [`postgres-pvc-reuse.md`](./postgres-pvc-reuse.md) — volume reclaim / rebind
- Components: `gitops/root/components/minio`, `gitops/root/components/postgres-backup`
