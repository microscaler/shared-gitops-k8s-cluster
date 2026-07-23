# GitHub Actions Runner Controller (ARC)

Org-scoped ephemeral runners on the Multipass **k3s** cluster, replacing the
standalone Multipass VM `gha-runner-1` (`cylon-images/multipass-gha-runner`, deprecated).

## Workflows

```yaml
runs-on: [self-hosted, linux, x64, microscaler]
```

ARC registers scale-set name `microscaler` plus labels `self-hosted`, `linux`, `x64`
(`deployment-configuration/profiles/dev/arc/helm-values.yaml`).

## Topology

| Piece | Where |
|--------|--------|
| Nodes | Multipass `k8s-runner-*` (Day-0 `K8S_RUNNERS`) — 4 CPU / 12G / 100G |
| Node label | `node.microscaler.io/role=gha-runner` |
| Node taint | `node.microscaler.io/gha-runner=true:NoSchedule` |
| Controller | namespace `arc-systems` (HelmRelease `arc`, chart `0.14.2`) |
| Scale set | namespace `arc-runners` — raw `AutoscalingRunnerSet` (`runner-scale-set.yaml`) |
| Mode | Docker-in-Docker (native sidecar `restartPolicy: Always`) |
| Parallelism | `minRunners: 1`, `maxRunners: 18` pool (~9/node via ~768Mi/250m requests + topology spread) |
| DinD pull cache | `dind-registry-proxy` in `arc-runners` (MITM HTTPS proxy) — DinD uses `HTTP(S)_PROXY` + proxy CA. Caches `ghcr.io` / Docker Hub. Classic `--registry-mirror` is Hub-only, so not used alone. |

> Chart `gha-runner-scale-set` 0.14.x is **not** used for the scale set: its
> `toYaml\|nindent` rendering breaks image tags under Kubernetes SSA. Controller
> stays Helm; the AutoscalingRunnerSet is GitOps YAML.

Add another node: append `k8s-runner-N` to `K8S_RUNNERS` in `config/cluster.env`, then:

```bash
just --justfile day0.justfile vm-create-runners
```

Current pool: `k8s-runner-1` … `k8s-runner-3` (4 CPU / 12G each).

## Runner image (toolchain)

Stock `ghcr.io/actions/actions-runner` lacks `gcc`/`pip`. We bake them into:

`10.177.76.220:5000/microscaler/actions-runner:2.336.0-ci3`

Dockerfile: `gitops/root/components/arc/runner-image/Dockerfile`

```bash
just arc-runner-image-build   # docker build; push registry or import to K8S_RUNNERS
just arc-runner-rollout       # recreate AutoscalingRunnerSet pods
```

If the in-cluster registry PVC is full, the build recipe imports the image into
each `k8s-runner-*` node via `k3s ctr` (scale set uses `imagePullPolicy: IfNotPresent`).

### Tools (from `octopilot/actions` requirements)

| Tool | Why |
|------|-----|
| Docker Compose v2 CLI plugin | `test` → `hack/test-deps` (`docker compose up`) |
| Helm 3.16.4 | `lint` / `test` Helm chart paths |
| mold, pkg-config, libssl-dev, build-essential | Rust `-sys` crates + fast link |
| python3-full, python3-venv, pipx | PEP 668 — no system `pip install --user` |
| pre-commit (via pipx → `/usr/local/bin`) | `lint` Install pre-commit step |
| jq, curl, git, uuid-runtime | general CI |

Language toolchains (Rust/Node/Go/Python versions) stay on `actions/setup-*`
+ caches; do not bake every SDK into the image.

Runner Multipass nodes (`multipass/cloud-init-k3s-runner.yaml`) also install
`docker.io` + Compose so host-side tooling matches; Day-0 uses
`render_cloud_init.py runner`.

## Bootstrap (ms02)

```bash
cd ~/Workspace/microscaler/shared-gitops-k8s-cluster

# 1) Runner node pool
just --justfile day0.justfile vm-create-runners

# 2) GitHub credentials (PAT with admin:org, or GitHub App — see profiles/dev/arc/README.md)
just secrets-encrypt dev arc /tmp/arc.secrets.env
just secrets-apply dev arc

# 3) Stack is Flux-owned (inventory stacks/arc). Force reconcile after push:
kubectl -n flux-system annotate gitrepository shared-gitops-k8s-cluster \
  reconcile.fluxcd.io/requestedAt="$(date -u +%Y-%m-%dT%H:%M:%SZ)" --overwrite
# or apply locally while iterating:
kubectl apply -k gitops/root/components/namespaces
kubectl apply -k gitops/root/components/arc
```

## Verify

```bash
kubectl get nodes -l node.microscaler.io/role=gha-runner -o wide
kubectl -n arc-systems get pods,helmrelease
kubectl -n arc-runners get pods,autoscalingrunnerset,helmrelease
gh api /orgs/microscaler/actions/runners --jq '.runners[] | {name,status,busy,labels:[.labels[].name]}'
```

## Deprecate Multipass classic runner

Once ARC shows Idle runners and a smoke workflow succeeds:

```bash
# Remove classic org runner registration (on the VM)
cd ~/Workspace/microscaler/cylon-images/multipass-gha-runner
# stop service + remove from GitHub, then:
just purge
```

Do not schedule new work on `gha-runner-1`.

## DinD registry proxy (revertible)

Ephemeral DinD has an empty image store each job. To cache `ghcr.io` / Hub pulls:

1. `dind-registry-proxy` Deployment (MITM on `:3128`, PVC `20Gi`)
2. DinD sidecar installs `/ca.crt` into trust store and sets `HTTP(S)_PROXY`

Verify:

```bash
kubectl -n arc-runners get deploy,svc,pvc dind-registry-proxy
# From a runner job / DinD: second pull of ghcr.io/octopilot/op should be LAN-fast
kubectl -n arc-runners logs deploy/dind-registry-proxy --tail=50
```

Revert:

1. Remove `dind-registry-proxy.yaml` from `gitops/root/components/arc/kustomization.yaml`
2. Restore DinD `args: [dockerd, --host=unix:///var/run/docker.sock, --group=123]` (drop `command` / PROXY env)
3. Delete Deployment/Service/PVC `dind-registry-proxy` if Flux does not prune

## Agent status (capacity)

- **2026-07-23:** Added `k8s-runner-3` (4 CPU / 12G); resurrection-node-1 parked at
  1 CPU / 2G while Cylon FAR is idle. Pool still `maxRunners: 18` (~6/node).
- **2026-07-23:** Pool lowered to `maxRunners: 18` — 30 was too high in practice.
- **2026-07-23:** DinD OCI pull cache via `rpardini/docker-registry-proxy` (MITM).
  Classic `--registry-mirror` is Hub-only; this path covers `ghcr.io/octopilot/op`.
- **2026-07-23:** Per-pod requests ~768Mi + 250m CPU (limits DinD 3Gi / runner 2Gi)
  on `k8s-runner-*` nodes with topology spread.
