# Postgres PVC reuse (dev Multipass)

## Short answer

**Old primary/replica disks cannot be reused now.** Those PVCs used `local-path` with `reclaimPolicy: Delete`. When the hand-rolled Deployments/PVCs were removed, the PVs and host directories were deleted. A scan of worker nodes only shows the new HA volumes plus pact-postgres hostPath.

**New HA volumes should be reusable** if we keep `local-path-retain` and follow the rebind runbook below.

## Why Bitnami HA does not take `existingClaim` easily

`postgresql-ha` creates a StatefulSet with per-ordinal PVCs:

| Ordinal | Expected PVC name |
|---------|-------------------|
| 0 | `data-postgres-ha-postgresql-0` |
| 1 | `data-postgres-ha-postgresql-1` |
| 2 | `data-postgres-ha-postgresql-2` |

Chart `persistence.existingClaim` is a **single** shared claim — wrong for multi-replica repmgr. Reuse means pre-bound PVCs with those exact names.

Data layout for bitnamilegacy images is still under `/bitnami/postgresql` (same as the old primary Deployment), so a **retained** primary volume could be rebound to ordinal 0 *if* the PV still existed.

## Future cutover (when disks still exist)

1. Patch PVs: `reclaimPolicy: Retain` (or use StorageClass `local-path-retain`).
2. Scale down / delete the old workload **without** deleting the PV objects.
3. Delete PVCs only; Released PVs stay on disk. Edit PV: clear `claimRef`, set phase Available if needed.
4. Create PVCs named `data-postgres-ha-postgresql-N` with `volumeName: <pv-name>` and matching size/access mode.
5. Install/upgrade HelmRelease so the StatefulSet binds those claims (do not let dynamic provision create empty disks first).

For a single primary → HA ordinal 0 only: bind the old primary PV to `-0`; let `-1`/`-2` provision empty and join via repmgr (or restore from backup into all three).

## Current cluster (2026-07-15)

| Volume | Status |
|--------|--------|
| `postgres-primary-data` / replica PVCs | **Gone** (Delete reclaim) |
| `data-postgres-ha-postgresql-{0,1,2}` | New empty HA disks |
| `/var/lib/data/pact-postgres` (hostPath) | Intact; separate from platform HA |

If you need old app schemas back, restore from backup/dump into Pgpool at `10.177.76.224:5432` — there is nothing left to remount from the old primary PVC.
