# Day-0 host edge — thin Ansible (this repo)

Flux cannot manage ms02 UFW, systemd units, or k3s TLS SANs. Those sit in a
**thin Ansible layer** under `ansible/` — run **on ms02**.

## Ownership split

| Concern | Home | Why |
|---|---|---|
| Mac `/etc/resolver`, MetalLB static route, ms02 L3 forward, split-horizon DNS | **`cylon-local-infra`** | Desktop topology (picolino ↔ ms02) |
| Multipass cloud-init, kubeconfig, haproxy render (`tools/`), lan-proxy unit, k8s API LAN, **Tilt user systemd units** | **`shared-gitops-k8s-cluster`** | Single Day-0 + GitOps home (`shared-gitops-k8s-cluster` retired) |
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

## Tilt user units + HTTP edge

| Piece | Source |
|---|---|
| `~/.config/systemd/user/tilt-*.service` | role **`tilt_user_units`** (`ansible/roles/tilt_user_units/defaults/main.yml`) |
| `microscaler-shared-k8s-infra.service` | same role (`deploy/cluster-start.sh` readiness gate) |
| `*.dev.microscaler.local` → Envoy → Services | GitOps stack **`envoy-gateway`** (HTTPRoute + annotations) |
| lan-proxy `:80/:443` | TCP passthrough to `ENVOY_GATEWAY_LB_IP` (`.234`) — no manual vhosts |

`config/lan-http-vhosts.yaml` is retired (`vhosts: []`). Add hosts via HTTPRoute under
`gitops/root/components/envoy-gateway/httproutes/` (see that component’s README).

## Kubernetes API LAN path

| Step | Managed by |
|---|---|
| haproxy `192.168.1.189:6443` → CP `:6443` | `lan_proxy` + `tools/configure_lan_proxy.py` |
| k3s tls-san `192.168.1.189` | `k8s_api_lan` (multipass as `casibbald`) |
| Mac kubeconfig `shared-k8s-mac.yaml` | `k8s_api_lan` |

```bash
export KUBECONFIG=~/Workspace/remote/microscaler/shared-gitops-k8s-cluster/kubeconfig/shared-k8s-mac.yaml
kubectl get nodes
```

## Notes

- Prefer `just cluster-edge-apply` / `just tilt-units-apply` over ad-hoc UFW or hand-copied units.
- Multipass CLI tasks use `become_user: casibbald` (root is not authenticated to Multipass).
- Variable name `shared_k8s_root` in Ansible still means “platform root”; it now points at this repo.
