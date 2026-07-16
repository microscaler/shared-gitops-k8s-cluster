# Platform storage B-shape: host ZFS + democratic-csi

Status: **Flux `stack-democratic-csi` live**. **postgres-ha prove-out passed**. **Bulk cutover of hostPath magnet → `zfs-iscsi` in progress** (redis, mailpit, minio, openbao, pact, faktory, opensearch, registry).

## Problem

Static `local-storage` hostPath PVs were pinned to `k8s-worker-1` (`K8S_DATA_NODE`), creating a data magnet. Multipass workers have no ZFS; **ms02** has `rpool`.

## Decision

| Use case | Driver / SC |
|----------|-------------|
| Platform RWO | **`zfs-generic-iscsi`** → StorageClass `zfs-iscsi` |
| Optional RWX later | `zfs-generic-nfs` → `zfs-nfs` (parents ready; not in Flux yet) |

## Cutover pattern (immutable PVC / STS)

1. Git: drop static PV; PVC (or Helm `storageClass`) → `zfs-iscsi`
2. Suspend stack / scale down consumers
3. Delete old PVC (+ Released hostPath PV)
4. Flux recreate → portal-ensure CronJob heals LIO portals (~1 min)
5. Resume / scale up

**MinIO:** wipe loses `postgres-backups` bucket — re-run `just postgres-backup-now` after Ready.

**OpenBao:** wipe requires re-init / unseal bootstrap.

## Flux democratic-csi

| Resource | Notes |
|----------|--------|
| HelmRelease `democratic-csi` | chart `0.15.1`, driver `zfs-generic-iscsi` |
| SC `zfs-iscsi` | Retain, Immediate, ext4 |
| CronJob `iscsi-portal-ensure` | every minute — CreateVolume often leaves Portals:0 |

## Ops notes

- Portal: **`10.177.76.1:3260`**
- Host UFW (bridge → iSCSI/NFS/SSH): `just cluster-edge-apply tags=multipass_bridge` — see [`day0-host-edge-ansible.md`](./day0-host-edge-ansible.md)
- SOPS: `SOPS_AGE_KEY_FILE=~/.config/sops/age/flux-shared-gitops`
- Do not set Bitnami `postgresql.configuration` to a one-line snippet (replaces whole conf)
