# Platform storage B-shape: host ZFS + democratic-csi

Status: **Flux `stack-democratic-csi` live** (2026-07-16). **postgres-ha prove-out passed** — 3/3 on `zfs-iscsi` with hard anti-affinity (one pod per worker); HelmRelease Ready.

## Problem

Static `local-storage` hostPath PVs are pinned to `k8s-worker-1` (`K8S_DATA_NODE`), creating a data magnet (~29 pods). Multipass workers have no ZFS; **ms02** has `rpool` (~834G free).

## Decision

| Use case | Driver / SC |
|----------|-------------|
| Platform RWO (postgres-ha, redis, minio, openbao, …) | **`zfs-generic-iscsi`** → StorageClass `zfs-iscsi` |
| Optional RWX shared files later | `zfs-generic-nfs` → `zfs-nfs` (NFS parents ready; not in Flux yet) |

## Architecture

- ZVOL parents: `rpool/k8s/iscsi/{vols,snaps}` (sibling snaps — not nested)
- LIO via **targetcli-fb**; portal **`10.177.76.1:3260`**
- Workers: `open-iscsi` on all Multipass nodes
- Flux stack: `gitops/root/components/democratic-csi/`
- CSI SSH user: `csi-zfs` @ `10.177.76.1`, key `/etc/microscaler/csi/csi-zfs_ed25519`

NFS parents (optional RWX later): `rpool/k8s/nfs/{vols,snaps}` → `/export/k8s/nfs/...`

## Day-0 host (done)

1. UFW from `10.177.76.0/24`: NFS (`2049`, `111`, `20048`), iSCSI (`3260/tcp`), SSH (`22/tcp`)
2. Packages: `targetcli-fb`, `open-iscsi` on host; `open-iscsi` on **all** workers
3. User `csi-zfs` + `zfs allow` on `rpool/k8s` + passwordless sudo for `zfs` / `targetcli`
4. Manual NFS + iSCSI smokes passed before Flux

## Flux stack (done)

| Resource | Notes |
|----------|--------|
| HelmRelease `democratic-csi` | chart `0.15.1`, driver `zfs-generic-iscsi` |
| SC `zfs-iscsi` | Retain, Immediate, ext4 |
| Secret `democratic-csi-driver-config` | SOPS: SSH + ZFS dataset paths |
| Secret `democratic-csi-ssh-key` | SOPS: same private key for portal CronJob |
| CronJob `iscsi-portal-ensure` | every minute — see caveat below |

Inventory: `gitops/clusters/dev/inventory/stacks/democratic-csi/`

### Known caveat: LIO portals

`CreateVolume` often leaves targets with **Portals: 0** when `10.177.76.1:3260` already exists on another target. NodeStage then hangs on `iscsiadm` login until the portal is added.

**Mitigation:** CronJob `iscsi-portal-ensure` SSHes as `csi-zfs` and ensures the portal on every IQN (up to ~1 minute delay on first attach).

## Workload cutover: postgres-ha (in progress)

Prove-out: 3× RWO on `zfs-iscsi` + **hard** pod anti-affinity / topology spread (one PG pod per node).

STS `volumeClaimTemplates` are immutable — cutover deletes STS + PVCs, then Helm recreates on `zfs-iscsi`. Take `just postgres-backup-now` first.

```bash
flux suspend hr postgres-ha -n data
kubectl -n data delete sts postgres-ha-postgresql
kubectl -n data delete pvc data-postgres-ha-postgresql-0 \
  data-postgres-ha-postgresql-1 data-postgres-ha-postgresql-2
# optional: delete Released local-path PVs
flux resume hr postgres-ha -n data
flux reconcile hr postgres-ha -n data --with-source
```

## Smoke (done)

Namespace `csi-smoke`: PVCs `zfs-iscsi-smoke{,-2,-3}` + nginx — Bound/Ready after portal ensure.

## Next after postgres

Migrate hostPath magnet: **redis → mailpit → openbao → minio → faktory / pact**.

## Ops notes

- Portal / shareHost: **`10.177.76.1`**, not `192.168.1.189`
- Ansible nfs_server owns `/etc/exports` — CSI NFS paths use ZFS `sharenfs` only
- Re-check UFW after `cylon-local-infra` ansible if firewall role resets rules
- targetcli config: `/etc/rtslib-fb-target/saveconfig.json` (`target.service`)
- SOPS encrypt secrets on ms02: `SOPS_AGE_KEY_FILE=~/.config/sops/age/flux-shared-gitops`
