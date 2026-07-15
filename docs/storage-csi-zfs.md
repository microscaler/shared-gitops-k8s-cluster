# Platform storage B-shape: host ZFS + democratic-csi (NFS)

Status: **Day-0 smoke proven** (2026-07-15). Flux HelmRelease not installed yet.

## Problem

Static `local-storage` hostPath PVs are pinned to `k8s-worker-1` (`K8S_DATA_NODE`), creating a data magnet (~29 pods). Multipass workers have no ZFS; **ms02** has `rpool` (~834G free).

## Architecture

- Parent datasets on ms02:
  - `rpool/k8s/nfs/vols` → `/export/k8s/nfs/vols` (PVC datasets)
  - `rpool/k8s/nfs/snaps` → `/export/k8s/nfs/snaps` (sibling for CSI snapshots — must not nest under vols)
- Share via ZFS `sharenfs` to `10.177.76.0/24` (Multipass bridge), not Ansible `/etc/exports` (those stay LAN-only).
- Nodes mount `10.177.76.1:/export/k8s/nfs/vols/...` (NFSv4 works).
- Future: Flux `democratic-csi` with driver `zfs-generic-nfs`, `shareHost: 10.177.76.1`.

## Day-0 checklist (done)

1. **UFW** (ms02): allow from `10.177.76.0/24` → `2049/tcp`, `111/tcp+udp`, `20048/tcp+udp`.
2. **ZFS**: create `rpool/k8s/nfs/{vols,snaps}` + smoke child `…/vols/smoke` with `sharenfs=rw=@10.177.76.0/24,no_subtree_check,no_root_squash,insecure`.
3. **Smoke**: from `k8s-worker-1`, `mount -t nfs 10.177.76.1:/export/k8s/nfs/vols/smoke` — read + write OK.

## Next (Flux)

1. SSH key + `zfs allow` on `rpool/k8s` for a CSI service user (avoid root password).
2. Stack `democratic-csi` HelmRelease + StorageClass `zfs-nfs`.
3. Migrate off hostPath magnet in order: redis → mailpit → openbao → minio → faktory / pact.
4. Keep **postgres-ha** on `local-path` until NFS latency is proven acceptable.

## Ops notes

- `shareHost` must be **`10.177.76.1`** (mpqemubr0), not `192.168.1.189`.
- Ansible nfs_server role owns `/etc/exports` for Workspace/hf-archive — do not put CSI paths there; use ZFS `sharenfs`.
- Re-check UFW after `cylon-local-infra` ansible runs if firewall role resets rules.
