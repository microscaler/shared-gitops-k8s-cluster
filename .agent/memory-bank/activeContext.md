# Active context

## Goal
Kill w1 hostPath magnet — all platform RWO on democratic-csi `zfs-iscsi`.

## Done
- democratic-csi + portal-ensure
- postgres-ha on zfs-iscsi (hard anti-affinity)
- Bulk migrate: redis, mailpit, minio, openbao, pact, faktory, opensearch, registry
- Commits: `7ae3247`, `5f8d04a`

## Notes
- OpenBao needs re-init/unseal (empty volume)
- MinIO wiped — re-run postgres-backup after Ready
- imgproxy shares minio RWO PVC — must co-locate with minio
- Fluvio static hostPath PVs removed; SpuGroup CRD has no storageClass (unused SPUs)

## Next
- OpenBao bootstrap if needed
- Optional: tear down csi-smoke
- Slim shared-k8s-cluster to Day 0
