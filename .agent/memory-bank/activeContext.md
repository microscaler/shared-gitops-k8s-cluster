# Active context

## Goal
All-in on host ZFS + democratic-csi iSCSI to kill w1 data magnet.

## Proven
- democratic-csi + SC `zfs-iscsi` + portal-ensure CronJob
- **postgres-ha on zfs-iscsi** with hard anti-affinity: STS 3/3, HR Ready
  - pods on w1 / w2 / w3; PVCs `zfs-iscsi`
  - Fixed invalid `postgresql.configuration` snippet (replaced whole conf)

## Next
1. Migrate hostPath magnet: redis → mailpit → openbao → minio → faktory/pact
2. Slim shared-k8s-cluster to Day 0
3. Optional: tear down `csi-smoke`
