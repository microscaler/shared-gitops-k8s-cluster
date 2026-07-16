# shared-gitops-k8s-cluster

FluxCD GitOps + [gitopssets-controller](https://github.com/weaveworks/gitopssets-controller) for Microscaler platform clusters.

**Day 0 VMs / k3s / render scripts** live in [`shared-k8s-cluster`](../shared-k8s-cluster/).  
**Day 0 host edge** (CSI UFW, lan-proxy systemd unit, k8s API LAN) is thin Ansible here: [`docs/day0-host-edge-ansible.md`](docs/day0-host-edge-ansible.md) / `just cluster-edge-apply`.  
**Day 1+** (continuous reconcile of platform and progressively product
workloads) is Flux composition in this repo; product profiles remain in their
own repositories.
**Desktop** (Mac resolver, L3 route, DNS) is [`cylon-local-infra`](../cylon-local-infra/) (Mac-local checkout).

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

## Product components (SAM model)

Product repositories own their complete environment profile; the shared
cluster owns only Flux composition. The first component is RERP Accounting:

```text
microscaler/rerp
└── deployment-configuration/profiles/dev/rerp/accounting/
                                      ↑
shared-gitops-k8s-cluster             │ Flux source + reconcile
├── gitops/inventory/product-components.yaml
└── gitops/root/gitopssets/product-components.yaml
```

`product-components.yaml` separates repository sources, ordered component
paths, and image repositories so one monorepo source can serve several
independently installed suites. RERP Accounting uses two components: foundation
first, then services. To add a component:

1. Add the suite-qualified Kustomize/SOPS profile to the product repository.
2. Add its product source once, then add one component row for each reconciled
   suite/profile path.
3. Run `just validate-inventory` and server-side dry-run the GitOpsSets.
4. Merge the product profile before enabling its shared-cluster component.

Tilt is the image-build inner loop. It must not decrypt/apply configuration or
render/apply Helm workloads. Flux owns the product rollout. Image discovery is
active; Git-writing automation remains off until the scoped credential gate in
[`docs/product-image-automation.md`](docs/product-image-automation.md) is met.

## Layout

```
deployment-configuration/    # env config + SOPS secrets (SMC-aligned)
  profiles/<env>/<component>/
    application.properties   # non-secret KEY=value → ConfigMap
    application.secrets.env  # SOPS dotenv → Secret
    *.secret.yaml            # SOPS Secret YAML when dotenv unfit
    kustomization.yaml
gitops/
  inventory/                 # clusters, platform stacks, product components, metallb, apps
  root/
    flux/v2_9_2/             # pinned Flux install (Namespace owned separately)
    controllers/gitopssets/  # HelmRelease for gitopssets-controller
    components/              # platform stacks (no embedded env config/secrets)
    gitopssets/              # GitOpsSet CRs (platform-stacks + profile-config)
    gitopssets/product-components.yaml # product GitRepository/Kustomization composition
  clusters/
    base/                    # shared bootstrap fragments
    {dev,staging,prod}/      # cluster entrypoints + control plane sync path
```

Secrets SOP: [`deployment-configuration/README.md`](deployment-configuration/README.md).

## Commands

| Recipe | Purpose |
|--------|---------|
| `just validate-inventory` | Schema-check inventory YAML |
| `just validate-product-components` | Validate product inventory and server-dry-run its GitOpsSet |
| `just build-dev` | `kustomize build gitops/clusters/dev` |
| `just bootstrap-dev` | Apply cluster entrypoint (Flux + sync) |
| `just flux-export` | Re-export Flux install into `root/flux/vX_Y_Z` |
| `just secrets-encrypt` | Encrypt plaintext dotenv → `deployment-configuration/profiles/...` |
| `just secrets-apply` | `kubectl apply -k` a profile (bootstrap) |
| `just secrets-ensure-age-key` | Apply `flux-system/sops-age` from ms02 age key |
