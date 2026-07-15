# Active context

## Goal
All-in on host ZFS + democratic-csi iSCSI to kill w1 data magnet.

## Proven
- NFS + iSCSI Day-0 smokes
- Flux `stack-democratic-csi` Ready; SC `zfs-iscsi`; dynamic PVC nginx smoke (2 volumes) Ready
- Caveat: CreateVolume often leaves LIO **Portals:0** → CronJob `iscsi-portal-ensure` mitigates

## Next
1. Reconcile portal-ensure CronJob + SSH secret; verify CronJob Succeeded
2. Migrate hostPath magnet: redis → mailpit → openbao → minio → faktory/pact
3. postgres-ha stay on local-path until standbys healthy; CSI later
4. Slim shared-k8s-cluster to Day 0, push remote, delete local copy
