# Postgres PVC reuse (dev Multipass / Kind)

## 2026-07-18 cutover (HA → Lifeguard primary-direct)

| Volume | Role |
|--------|------|
| `data-postgres-ha-postgresql-1` | Was **elected primary** (PG **17**); candidate to rebind |
| `data-postgres-ha-postgresql-{0,2}` | Standbys — discard after dump safety net |
| `postgres-primary-data` (20Gi empty) | Fresh PG15 volume from first chart install — delete before rebind |

**Hard constraint:** HA ran `bitnamilegacy/postgresql-repmgr:17.x`. Remount only onto **PostgreSQL 17** (`lifeguard/charts/postgres` `appVersion: "17"`). PG15 cannot open those disks.

### Rebind primary disk

1. `pg_dumpall` from HA primary (safety).
2. Suspend/delete Flux `HelmRelease postgres-ha` and STS (PVs are `Retain`).
3. Delete HA PVCs; clear `claimRef` on the primary PV (`pvc-…` for ordinal **1**).
4. Delete empty `postgres-primary-data` PVC + its PV if unused.
5. Create PVC `postgres-primary-data` with `volumeName: <primary-pv>`, `storage: 10Gi`, `storageClassName: zfs-iscsi`.
6. HelmRelease `postgres` uses chart image tag `17` and `persistence.size: 10Gi`.
7. Pod may need one-time cleanup of standby/repmgr recovery files if Bitnami refuses to start as primary — prefer dump restore if boot fails.

### If remount fails

Restore the dump into the new primary via `psql`, then re-run product `*-db-init` / `setup-db.sh` only if roles/schemas are missing.
