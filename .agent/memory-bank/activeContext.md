# Active context

## Goal
Finish Day-1 GitOps cutover so shared-k8s-cluster can be Day-0-only (push + delete local checkout; keep GitHub).

## Done just now
- Resumed stack-observability; cluster reconciling from origin/main @ 319bf4b.
- OpenSearch / Dashboards / Data Prepper HRs Ready.
- Redis HR Ready (PVC chown + volumePermissions + retries).
- MinIO HR Ready.
- postgres-ha upgrade in progress from git; primary up; standbys still 1/2 (known clone/PGDATA issue).

## Next
- Stabilize postgres-ha standbys via gitops values only, then stack-postgres-ha Ready.
- Slim shared-k8s-cluster to Day 0 and push.
