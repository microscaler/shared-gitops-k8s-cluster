# Progress — shared-gitops-k8s-cluster

## 2026-07-15

- [x] Scaffold repo (README, AGENTS, justfile, design)
- [x] Flux v2.9.2 export (Namespace stripped)
- [x] Inventories: clusters, stacks, metallb, apps
- [x] clusters/{dev,staging,prod} entrypoints + control
- [x] gitopssets-controller HelmRelease + RBAC + platform-stacks GitOpsSet
- [x] namespaces component (real); other stacks stub ConfigMaps
- [x] Inventory validator (venv + just validate-inventory)
- [x] kustomize build greened for namespaces, control, dev bootstrap
- [ ] GitHub remote + first push
- [ ] bootstrap-dev against live cluster
- [ ] Migrate platform-data / observability / …
