# shared-gitops-k8s-cluster — agent rules

> **What this repository is** — FluxCD + GitOpsSets source of truth for Microscaler **platform** clusters. Day-0 Multipass/k3s bootstrap remains in [`../shared-k8s-cluster`](../shared-k8s-cluster/).

Desktop topology: [`cylon-local-infra/docs/desktop-dev-environment.md`](https://github.com/microscaler/cylon-local-infra/blob/main/docs/desktop-dev-environment.md). **Run flux/kubectl/just on ms02**, not the Mac.

## Before you start

1. Read [`docs/design.md`](./docs/design.md).
2. Read [`README.md`](./README.md).
3. For Multipass node IPs / LAN proxy, read [`../shared-k8s-cluster/docs/llmwiki/topics/cluster-topology.md`](../shared-k8s-cluster/docs/llmwiki/topics/cluster-topology.md).

## Core rules

### 1. `dev` = Multipass shared-k8s

Bootstrap target context is **`shared-k8s`** (`shared-k8s-cluster/kubeconfig/shared-k8s.yaml`). Do not apply `clusters/dev` to Kind or a random context.

### 2. Inventories are the source of truth

Change stacks / MetalLB / apps in `gitops/inventory/` (+ per-cluster overlays). Do not hand-duplicate Flux `Kustomization` CRs when a GitOpsSet template already covers them.

### 3. Never commit secrets or kubeconfigs

Git credentials, SOPS keys, and kubeconfigs stay out of git. Use `flux create secret git` or sealed secrets under an ignored path.

### 4. Do not edit generated Flux install lightly

`gitops/root/flux/v2_9_2/flux-install.yaml` is exported from `flux install --export`. Prefer a new version directory over surgical edits. Namespace `flux-system` is managed in `gitops/clusters/base/`, not inside the export.

### 5. Product Tilts stay in app repos

This repo does not replace hauliage/sesame Tilt inner loops. Platform reconcile only.

### 6. Multi-cluster readiness

Adding a cluster = inventory row in `gitops/inventory/clusters.yaml` + `gitops/clusters/<id>/` entrypoint. Prefer GitOpsSet Matrix / per-cluster inventory over forking component YAML.
