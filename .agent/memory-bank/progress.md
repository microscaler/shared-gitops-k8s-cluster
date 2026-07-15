# Progress — shared-gitops-k8s-cluster

## 2026-07-15

### Phase 2 — done
Flux + GitOpsSets on Multipass `dev` with local registry images.

### Phase 3 — in progress
Enabled Flux stacks (all Ready):
- `stack-namespaces`
- `stack-cluster` (registry, MetalLB pool, housekeeping)
- `stack-cylon-infra`
- `stack-platform-dev-tls`

Remaining: `platform-data`, `observability`, `ai`, `platform-openbao`

shared-k8s-cluster: Tilt no longer applies cylon-infra (commit local, not necessarily pushed).
