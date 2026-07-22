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
| Parallelism | `minRunners: 1`, `maxRunners: 12` pool (~6/node via 2Gi requests + topology spread) |

> Chart `gha-runner-scale-set` 0.14.x is **not** used for the scale set: its
> `toYaml\|nindent` rendering breaks image tags under Kubernetes SSA. Controller
> stays Helm; the AutoscalingRunnerSet is GitOps YAML.

Add a second node: append `k8s-runner-2` to `K8S_RUNNERS` in `config/cluster.env`, then:

```bash
just --justfile day0.justfile vm-create-runners
```

## Runner image (toolchain)

Stock `ghcr.io/actions/actions-runner` lacks `gcc`/`pip`. We bake them into:

`10.177.76.220:5000/microscaler/actions-runner:2.336.0-ci`

Dockerfile: `gitops/root/components/arc/runner-image/Dockerfile`

```bash
just arc-runner-image-build   # docker build; push registry or import to K8S_RUNNERS
just arc-runner-rollout       # recreate AutoscalingRunnerSet pods
```

If the in-cluster registry PVC is full, the build recipe imports the image into
each `k8s-runner-*` node via `k3s ctr` (scale set uses `imagePullPolicy: IfNotPresent`).

Packages: `build-essential`, `pkg-config`, `libssl-dev`, `python3-pip`,
`python3-venv`, `jq`, `uuid-runtime`, `mold`, `curl`, `git`,
`docker-compose-plugin` (fallback `docker-compose-v2`).

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
