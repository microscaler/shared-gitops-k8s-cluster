# Active context

## Goal
Platform storage B-shape (host ZFS + democratic-csi NFS) to kill k8s-worker-1 data magnet; then finish Day-0 slim of shared-k8s-cluster.

## Done (2026-07-16)
- UFW: NFS/rpc from 10.177.76.0/24 → host
- ZFS: rpool/k8s/nfs/{vols,snaps} + smoke share
- Smoke mount from k8s-worker-1 NFSv4 read/write OK
- Doc: docs/storage-csi-zfs.md

## Next
- Scaffold Flux democratic-csi (zfs-generic-nfs) + SC zfs-nfs
- SSH/zfs allow for CSI user
- Migrate redis first off local-storage hostPath
