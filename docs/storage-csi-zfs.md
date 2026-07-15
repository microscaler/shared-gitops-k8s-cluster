# Platform storage B-shape: host ZFS + democratic-csi

Status: **Flux `stack-democratic-csi` live** (2026-07-16). Dynamic `zfs-iscsi` PVC smoke passed (nginx on worker-2).

## Problem

Static `local-storage` hostPath PVs are pinned to `k8s-worker-1` (`K8S_DATA_NODE`), creating a data magnet (~29 pods). Multipass workers have no ZFS; **ms02** has `rpool` (~834G free).

## Decision

| Use case | Driver / SC |
|----------|-------------|
| Platform RWO (redis, minio, openbao, …) | **`zfs-generic-iscsi`** → StorageClass `zfs-iscsi` |
| Optional RWX shared files later | `zfs-generic-nfs` → `zfs-nfs` (NFS parents ready; not in Flux yet) |

Keep **postgres-ha on `local-path`** until standbys are healthy; migrate later.

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

`CreateVolume` often leaves targets with **Portals: 0** when `10.177.76.1:3260` already exists on another target. NodeStage then hangs on `iscsiadm` login until the portal is added:

```bash
sudo targetcli "/iscsi/<iqn>/tpg1/portals create 10.177.76.1 3260"
sudo targetcli saveconfig
```

**Mitigation:** CronJob `iscsi-portal-ensure` SSHes as `csi-zfs` and ensures the portal on every IQN. New PVCs may wait up to ~1 minute before NodeStage succeeds.

Manual one-shot (same logic):

```bash
for d in /sys/kernel/config/target/iscsi/iqn.*; do
  [ -d "$d" ] || continue
  sudo targetcli "/iscsi/$(basename "$d")/tpg1/portals create 10.177.76.1 3260" || true
done
sudo targetcli saveconfig
```

## Smoke (done)

Namespace `csi-smoke`: PVCs `zfs-iscsi-smoke{,-2}` + nginx Deployments — Bound, pods Ready after portal ensure.

Tear down when done proving:

```bash
kubectl delete ns csi-smoke
# Retain PVs/zvols until explicitly destroyed via CSI / targetcli + zfs destroy
```

## Next: migrate off hostPath magnet

Order: **redis → mailpit → openbao → minio → faktory / pact**. Pattern per app:

1. GitOps: StorageClass → `zfs-iscsi` (new PVC name or wipe + recreate)
2. Flux reconcile; wait for portal-ensure if NodeStage stalls
3. Delete old hostPath PV/PVC only after data cutover verified
4. Revisit postgres-ha → `zfs-iscsi` after redis proves stable

## Ops notes

- Portal / shareHost: **`10.177.76.1`**, not `192.168.1.189`
- Ansible nfs_server owns `/etc/exports` — CSI NFS paths use ZFS `sharenfs` only
- Re-check UFW after `cylon-local-infra` ansible if firewall role resets rules
- targetcli config: `/etc/rtslib-fb-target/saveconfig.json` (`target.service`)
- SOPS encrypt secrets on ms02: `SOPS_AGE_KEY_FILE=~/.config/sops/age/flux-shared-gitops`
