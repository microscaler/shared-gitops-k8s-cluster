# shared-gitops-k8s-cluster

FluxCD GitOps + [gitopssets-controller](https://github.com/weaveworks/gitopssets-controller) for Microscaler platform clusters — **and** Day-0 Multipass/k3s host edge.

The former `shared-gitops-k8s-cluster` repo is **retired**. Kubeconfig, lan-proxy, Multipass cloud-init, Tilt systemd units, and platform reconcile all live here.

| Layer | Home |
|-------|------|
| Day 0 VMs / k3s / MetalLB seed | `day0.justfile` (`just cluster-create`) |
| Day 0 host edge (UFW, lan-proxy unit, k8s API LAN, Tilt units) | `ansible/` (`just cluster-edge-apply`) |
| Day 1+ platform + product reconcile | Flux (`gitops/`) |
| Desktop (Mac resolver, L3 route, DNS) | [`cylon-local-infra`](../cylon-local-infra/) |

## Clusters

| ID | Role | Topology | Status |
|----|------|----------|--------|
| `dev` | Local platform / product Tilts | Multipass k3s on ms02 (`shared-k8s`) | **active** |
| `staging` | Shared pre-prod (future) | TBD | stub |
| `prod` | Production (future) | TBD | stub |

## Quickstart (dev / Multipass)

On **ms02**:

```bash
cd ~/Workspace/microscaler/shared-gitops-k8s-cluster
just cluster-create          # Day 0 — if not already up
export KUBECONFIG=$PWD/kubeconfig/shared-k8s.yaml

# Push this repo to GitHub first, then create git credentials:
#   flux create secret git gitops-auth --url=ssh://git@github.com/microscaler/shared-gitops-k8s-cluster.git ...

just validate-inventory
just bootstrap-dev           # kubectl apply -k gitops/clusters/dev
just cluster-edge-apply      # lan-proxy + Tilt user units + UFW
flux get all -A
```

Mac kubectl:

```bash
export KUBECONFIG=~/Workspace/remote/microscaler/shared-gitops-k8s-cluster/kubeconfig/shared-k8s-mac.yaml
kubectl get nodes
```

Design: [`docs/design.md`](docs/design.md). Day-0 Ansible: [`docs/day0-host-edge-ansible.md`](docs/day0-host-edge-ansible.md). Remote Tilt: [`docs/remote-tilt-workflow.md`](docs/remote-tilt-workflow.md). Topology: [`docs/llmwiki/topics/cluster-topology.md`](docs/llmwiki/topics/cluster-topology.md).

## Product components (SAM model)

Product repositories own their complete environment profile; the shared
cluster owns only Flux composition. See [`docs/product-image-automation.md`](docs/product-image-automation.md).

**Tilt** is the image-build inner loop for product apps. It must not decrypt/apply
configuration or render/apply Helm platform workloads. Flux owns platform rollout.

## Layout

```
day0.justfile                # Multipass/k3s lifecycle (just cluster-create)
ansible/                     # host edge (lan-proxy, tilt units, UFW)
config/                      # cluster.env, lan-*, tilt-cluster.env
deploy/                      # preflight, cluster-start/stop, lan-proxy unit
kubeconfig/                  # shared-k8s.yaml (+ mac variant)
multipass/                   # cloud-init templates
tools/                       # lan-proxy / DNS / registry helpers
deployment-configuration/    # env config + SOPS secrets (SMC-aligned)
gitops/                      # Flux inventories, clusters, components
docs/                        # design, day0, remote-tilt, llmwiki
```
