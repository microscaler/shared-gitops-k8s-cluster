# shared-gitops-k8s-cluster

FluxCD GitOps + [gitopssets-controller](https://github.com/weaveworks/gitopssets-controller) for Microscaler platform clusters.

**Day 0** (VMs, k3s, MetalLB CRDs, LAN proxy) lives in [`shared-k8s-cluster`](../shared-k8s-cluster/).  
**Day 1+** (continuous reconcile of platform workloads) lives **here**.

## Clusters

| ID | Role | Topology | Status |
|----|------|----------|--------|
| `dev` | Local platform / product Tilts | Multipass k3s on ms02 (`shared-k8s`) | **active** |
| `staging` | Shared pre-prod (future) | TBD | stub |
| `prod` | Production (future) | TBD | stub |

Multi-cluster dryness: shared `gitops/inventory/` + per-cluster `gitops/clusters/<id>/inventory/` overlays. GitOpsSets render Flux `Kustomization`s from inventory (Matrix-ready).

## Quickstart (dev / Multipass)

On **ms02** (never run Flux/`kubectl` against this cluster from Mac builds):

```bash
cd ~/Workspace/microscaler/shared-k8s-cluster
just cluster-create          # Day 0 — if not already up
export KUBECONFIG=$PWD/kubeconfig/shared-k8s.yaml

cd ~/Workspace/microscaler/shared-gitops-k8s-cluster
# Push this repo to GitHub first, then create the git credentials secret:
#   flux create secret git gitops-auth --url=ssh://git@github.com/microscaler/shared-gitops-k8s-cluster.git ...

just validate-inventory
just bootstrap-dev           # kubectl apply -k gitops/clusters/dev
flux get all -A
```

Design: [`docs/design.md`](docs/design.md).

## Layout

```
gitops/
  inventory/                 # shared inventories (clusters, stacks catalog, metallb, apps)
  root/
    flux/v2_9_2/             # pinned Flux install (Namespace owned separately)
    controllers/gitopssets/  # HelmRelease for gitopssets-controller
    components/              # platform stacks (namespaces first; others migrate next)
    gitopssets/              # GitOpsSet CRs + RBAC templates
  clusters/
    base/                    # shared bootstrap fragments
    {dev,staging,prod}/      # cluster entrypoints + control plane sync path
```

## Commands

| Recipe | Purpose |
|--------|---------|
| `just validate-inventory` | Schema-check inventory YAML |
| `just build-dev` | `kustomize build gitops/clusters/dev` |
| `just bootstrap-dev` | Apply cluster entrypoint (Flux + sync) |
| `just flux-export` | Re-export Flux install into `root/flux/vX_Y_Z` |
