# Active context

## Goal
All-in on host ZFS + democratic-csi iSCSI to kill w1 data magnet.

## Proven
- NFS smoke (earlier)
- iSCSI: ZVOL + LIO + manual login + k8s nginx on static iSCSI PV (ns csi-smoke) — PASS, data persists across pod recreate

## Next
Flux democratic-csi zfs-generic-iscsi + SC zfs-iscsi; open-iscsi on all workers; migrate redis first.
