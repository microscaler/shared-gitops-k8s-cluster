# Active context

## Goal
Finish Day-1 GitOps cutover so shared-k8s-cluster can be pushed as Day-0-only and deleted locally (remote kept).

## Just done
- Pushed shared-gitops-k8s-cluster main → origin @ 6cdd320 (OpenSearch, SOPS, redis/minio Helm, postgres-ha env harden).
- Branch tracks origin/main cleanly.

## Still blocked
- stack-observability suspended (must resume so Flux matches git).
- postgres-ha HelmRelease suspended/stalled; standbys fail (PGDATA deleted after clone).
- shared-k8s-cluster still ahead + dirty; Tilt still applies platform k8s/.
