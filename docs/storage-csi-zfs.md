# Platform storage B-shape: host ZFS + democratic-csi

Status: **Day-0 NFS + iSCSI smokes proven** (2026-07-15/16). Flux CSI not installed yet — **go all-in on iSCSI** for platform RWO volumes.

## Problem

Static `local-storage` hostPath PVs are pinned to `k8s-worker-1` (`K8S_DATA_NODE`), creating a data magnet (~29 pods). Multipass workers have no ZFS; **ms02** has `rpool` (~834G free).

## Decision

| Use case | Driver / SC |
|----------|-------------|
| Platform RWO (redis, minio, openbao, postgres, …) | **`zfs-generic-iscsi`** → StorageClass `zfs-iscsi` |
| Optional RWX shared files later | `zfs-generic-nfs` → `zfs-nfs` (already smoked) |

## Architecture (iSCSI primary)

- ZVOL parents on ms02:
  - `rpool/k8s/iscsi/vols` (zvols)
  - `rpool/k8s/iscsi/snaps` (sibling — not nested)
- LIO via **targetcli-fb**; portal **`10.177.76.1:3260`**
- Workers: `open-iscsi` / `iscsiadm` (kubelet attaches for in-tree/CSI volumes)
- Future Flux: democratic-csi `zfs-generic-iscsi` + `shareStrategy: targetCli`

NFS parents (kept for optional RWX): `rpool/k8s/nfs/{vols,snaps}` → `/export/k8s/nfs/...`

## Day-0 checklist (done)

### NFS

1. UFW: `10.177.76.0/24` → `2049/tcp`, `111/tcp+udp`, `20048/tcp+udp`
2. ZFS smoke share + mount from `k8s-worker-1` (NFSv4 read/write OK)

### iSCSI

1. Packages: `targetcli-fb`, `open-iscsi` on host; UFW `3260/tcp` from `10.177.76.0/24`
2. ZVOL `rpool/k8s/iscsi/vols/smoke` (1G) + target `iqn.2026-07.local.microscaler:smoke`
3. Manual: discovery → login → `mkfs.ext4` → mount/umount on worker-1
4. K8s: static PV/PVC + `nginx-iscsi-smoke` in ns `csi-smoke`
   - `AttachVolume` succeeded; `/dev/sdb` mounted in pod
   - HTTP served from volume; data survived pod delete

Cleanup smoke later: `kubectl delete ns csi-smoke` + `kubectl delete pv iscsi-smoke-pv` (keep ZVOL/target until CSI cutover or tear down with targetcli).

## Next (Flux — all-in)

1. SSH key + `zfs allow` on `rpool/k8s` for CSI service user
2. Stack `democratic-csi` HelmRelease (`zfs-generic-iscsi`) + SC `zfs-iscsi`
3. Ensure `open-iscsi` on **all** workers (cloud-init / just recipe)
4. Migrate off hostPath magnet: redis → mailpit → openbao → minio → faktory / pact
5. Revisit postgres-ha → `zfs-iscsi` after redis proves stable

## Ops notes

- Portal / shareHost: **`10.177.76.1`**, not `192.168.1.189`
- Ansible nfs_server owns `/etc/exports` — CSI NFS paths use ZFS `sharenfs` only
- Re-check UFW after `cylon-local-infra` ansible if firewall role resets rules
- targetcli config: `/etc/rtslib-fb-target/saveconfig.json` (persist across reboot via `target.service`)
