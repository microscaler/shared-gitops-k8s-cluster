# Progress — shared-gitops-k8s-cluster

## Done (2026-07-16)

- [x] Host Day-0 for democratic-csi (csi-zfs user, zfs allow, UFW, open-iscsi on workers)
- [x] Flux stack `democratic-csi` (chart 0.15.1, driver zfs-generic-iscsi, SC zfs-iscsi)
- [x] Dynamic PVC smoke (csi-smoke nginx ×2)
- [x] Portal-ensure CronJob + SOPS `democratic-csi-ssh-key` (LIO Portals:0 workaround)
- [x] Docs: `docs/storage-csi-zfs.md` updated to Flux-live status

## Done (2026-07-15)

- [x] Adopt SOPS dotenv as standard secrets process
- [x] age key + flux-system/sops-age + observability credentials
- [x] NFS + iSCSI host smokes; choose iSCSI for platform RWO

## Done (postgres prove-out)

- [x] postgres-ha → `zfs-iscsi` (STS PVC recreate cutover)
- [x] Hard anti-affinity + topology spread: one PG pod per worker
- [x] HelmRelease Ready; stack-postgres-ha Ready @ `349ffd8`

## Next

- Migrate redis → mailpit → openbao → minio → faktory / pact
- Day-0-only shared-k8s-cluster cutover
- Optional: tear down `csi-smoke`

## Backlog

- Optional Flux `zfs-nfs` for RWX
- Migrate remaining inline passwords onto deployment-profiles when stacks touched
