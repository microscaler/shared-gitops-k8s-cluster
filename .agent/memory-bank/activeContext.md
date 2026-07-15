# Active context — shared-gitops-k8s-cluster

Updated: 2026-07-15

## Status

Phase 1 scaffold **complete** in `shared-gitops-k8s-cluster`.

## Locked decisions

- Separate GitOps repo (this one)
- Multi-cluster: `dev` / `staging` / `prod`
- Multipass shared-k8s = **`dev`**
- GitOpsSets for stack dryness

## Next

1. Create GitHub remote `microscaler/shared-gitops-k8s-cluster` and push
2. `just create-git-secret` + `just bootstrap-dev` on ms02
3. Phase 3: migrate manifests from shared-k8s-cluster/k8s into components
