# shared-gitops-k8s-cluster — agent rules

> **What this repository is** — FluxCD + GitOpsSets source of truth for Microscaler **platform** clusters, plus Day-0 host edge (kubeconfig, lan-proxy, Multipass cloud-init, Tilt systemd units). The former [`shared-k8s-cluster`](../shared-k8s-cluster/) repo is **retired** — do not point new paths at it. Host edge Ansible: [`docs/day0-host-edge-ansible.md`](./docs/day0-host-edge-ansible.md). Edge topology: [`docs/edge-envoy-vs-metallb.md`](./docs/edge-envoy-vs-metallb.md).

Desktop topology (Mac resolver, L3 route, split DNS): [`cylon-local-infra`](https://github.com/microscaler/cylon-local-infra/blob/main/docs/desktop-dev-environment.md). **Run flux/kubectl and thin Ansible on ms02** (`just cluster-edge-apply`, `just tilt-units-apply`). From Mac: `ssh ms02 'cd ~/Workspace/microscaler/shared-gitops-k8s-cluster && just …'`.

## Before you start

1. Read [`docs/design.md`](./docs/design.md).
2. Read [`README.md`](./README.md).
3. For Multipass / MetalLB topology, read [`docs/`](./docs/) and `config/loadbalancer-ips.env`.

## Core rules

### 1. `dev` = Multipass shared-k8s

Bootstrap target context is **`shared-k8s`** (`kubeconfig/shared-k8s.yaml` in this repo). Do not apply `clusters/dev` to Kind or a random context.

### 2. Inventories are the source of truth

Change stacks / MetalLB / apps in `gitops/inventory/` (+ per-cluster overlays). Do not hand-duplicate Flux `Kustomization` CRs when a GitOpsSet template already covers them.

Platform stacks:
- Catalog: `gitops/inventory/platform-stacks.yaml` (`path`, `depends_on`, `profile`)
- Enable: `mkdir gitops/clusters/<id>/inventory/stacks/<name>/`
- Render: `just sync-stack-inventory <id>` → `stacks.yaml` (committed; consumed by `platform-stacks` GitOpsSet)
- MetalLB check: `just check-metallb-inventory`

### 3. Env config + secrets under `deployment-configuration/profiles/`

**Canonical process** (SMC / metro-aligned; do not invent alternatives):

- Path: `deployment-configuration/profiles/<env>/<component>/`
- Non-secret config → `application.properties` → ConfigMap (`configMapGenerator`)
- Secrets → `application.secrets.env` (SOPS) or `*.secret.yaml`
- Do **not** hardcode env hosts/flags/buckets in Helm values or component ConfigMaps
- Do **not** put secrets under `gitops/root/components/*/secrets/`
- Flux: GitOpsSet `profile-config` → `profile-config-<component>`
- Encrypt/decrypt **on ms02** with `SOPS_AGE_KEY_FILE=~/.config/sops/age/flux-shared-gitops`
- Recipes: `just secrets-encrypt`, `secrets-apply`, `secrets-ensure-age-key`

Authority: [`deployment-configuration/README.md`](./deployment-configuration/README.md).  
Audit: [`docs/secrets-audit.md`](./docs/secrets-audit.md).  
Never commit plaintext, age private keys, git credentials, or kubeconfigs.

### 4. Do not edit generated Flux install lightly

`gitops/root/flux/v2_9_2/flux-install.yaml` is exported from `flux install --export`. Prefer a new version directory over surgical edits. Namespace `flux-system` is managed in `gitops/clusters/base/`, not inside the export.

### 5. Product source stays in app repos; Flux owns reconciliation

Follow the SAM Flux pattern: product repositories own
`deployment-configuration/profiles/<env>/...`; this repository owns the Flux
`GitRepository`/`Kustomization` composition which reconciles those paths.
During migration, product Tilts remain responsible for fast image builds and
may wait on Flux-owned resources, but must not become a second configuration or
workload owner. The target is Tilt builds images and Flux deploys them.

### 6. Multi-cluster readiness

Adding a cluster = inventory row in `gitops/inventory/clusters.yaml` + `gitops/clusters/<id>/` entrypoint. Prefer GitOpsSet Matrix / per-cluster inventory over forking component YAML.
