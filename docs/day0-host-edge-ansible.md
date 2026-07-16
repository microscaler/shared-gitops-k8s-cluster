# Day-0 host edge — thin Ansible (this repo)

Flux cannot manage ms02 UFW, systemd units, or k3s TLS SANs. Those sit in a
**thin Ansible layer** under `ansible/` — run **on ms02**.

## Ownership split

| Concern | Home | Why |
|---|---|---|
| Mac `/etc/resolver`, MetalLB static route, ms02 L3 forward, split-horizon DNS | **`cylon-local-infra`** | Desktop topology (picolino ↔ ms02) |
| Multipass/k3s VM create, haproxy **config render** Python | **`shared-k8s-cluster`** | Classic Day-0 bootstrap |
| CSI/multipass UFW, `microscaler-lan-proxy` unit, k8s API LAN, **Tilt user systemd units** | **`shared-gitops-k8s-cluster/ansible`** | Platform needs; Flux cannot own |
| MetalLB Services, democratic-csi Helm, workloads | **Flux in this repo** | Continuous reconcile |

## Apply (on ms02)

```bash
cd ~/Workspace/microscaler/shared-gitops-k8s-cluster
just cluster-edge-apply              # all roles
just cluster-edge-apply multipass_bridge
just cluster-edge-apply lan_proxy,k8s_api_lan
just tilt-units-apply                # ~/.config/systemd/user/tilt-*.service
```

From Mac:

```bash
ssh ms02 'cd ~/Workspace/microscaler/shared-gitops-k8s-cluster && just cluster-edge-apply'
ssh ms02 'cd ~/Workspace/microscaler/shared-gitops-k8s-cluster && just tilt-units-apply'
```

Inventory uses `ansible_connection: local` — ansible-playbook must run on ms02
(`apt install ansible` once).

## Tilt user units + HTTP vhosts

| Piece | Source |
|---|---|
| `~/.config/systemd/user/tilt-*.service` | role **`tilt_user_units`** (`ansible/roles/tilt_user_units/defaults/main.yml`) |
| `microscaler-shared-k8s-infra.service` | same role |
| `tilt-*.dev.microscaler.local` → `127.0.0.1:<port>` | `lan_proxy` + shared-k8s `tilt-apps.yaml` / `tilt_vhosts.py` |

Ports in the Ansible defaults must stay aligned with
`shared-k8s-cluster/tooling/src/microscaler_cli/data/tilt-apps.yaml`.

`shared-k8s just install-systemd` now delegates to `just tilt-units-apply`.

## Kubernetes API LAN path

| Step | Managed by |
|---|---|
| haproxy `192.168.1.189:6443` → CP `:6443` | `lan_proxy` + shared-k8s render |
| k3s tls-san `192.168.1.189` | `k8s_api_lan` (multipass as `casibbald`) |
| Mac kubeconfig `shared-k8s-mac.yaml` | `k8s_api_lan` |

```bash
export KUBECONFIG=~/Workspace/remote/microscaler/shared-k8s-cluster/kubeconfig/shared-k8s-mac.yaml
kubectl get nodes
```

## Dual-path notes

- Prefer `just cluster-edge-apply` / `just tilt-units-apply` over ad-hoc UFW or hand-copied units.
- Multipass CLI tasks use `become_user: casibbald` (root is not authenticated to Multipass).
