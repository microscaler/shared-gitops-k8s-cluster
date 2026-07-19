# Cluster topology — shared-gitops-k8s-cluster

- **Status**: `draft` — bootstrap scaffold (2026-07-07)
- **Replaces**: [`shared-kind-cluster`](../../../shared-kind-cluster/) Kind + host `kind-registry`
- **Last updated**: 2026-07-07

## Why

Kind on Docker caused:

- Pod network isolated from Multipass (`172.19.x` vs `10.177.76.x`)
- `extraPortMappings` / NodePort / UFW / socat matrices for every service
- Host registry (`localhost:5001`) wired through containerd hacks

This cluster uses **real nodes** on the Multipass L2 bridge with **MetalLB** and an **in-cluster registry**.

## Network

```
ms02 host (10.177.76.1 gateway)
├── k8s-cp-1      10.177.76.210   API :6443
├── k8s-worker-*  .211–.213       workloads
├── registry LB   10.177.76.220   :5000 OCI
├── MetalLB pool  .220–.239
└── resurrection-node-1  .108     FAR (not a k8s node)
```

## Registry

| Pull context | Image prefix |
|--------------|--------------|
| Host / Tilt build | `10.177.76.220:5000/myapp:tag` |
| Pod spec | `registry.registry.svc.cluster.local:5000/myapp:tag` |
| Legacy Kind tags | `localhost:5001/...` → mirrored on k3s nodes |

ConfigMap `kube-public/local-registry-hosting` documents the MetalLB address for Tilt.

## Workspace mount

Workers bind-mount `/home/casibbald/Workspace/microscaler` for Cylon `cylon-daemon` `hostPath`. Control plane has no workspace mount.

## Bootstrap order

1. `just vm-create-cp` — k3s server
2. `just vm-create-workers` — agents join
3. `just vm-mount-workspace`
4. `just cluster-bootstrap` — MetalLB + registry
5. `just apply-platform-namespaces`
6. Migrate platform kustomize from `shared-kind-cluster` (TODO)

## Open items

- Copy `k8s/platform-data/` tree from sibling repo
- Ingress controller (Traefik or nginx) for HTTP services
- Update `cylon` / `hauliage` Tilts for new context + registry host
- Delete `resurrection-node-2/3` after FAR smoke on single node
