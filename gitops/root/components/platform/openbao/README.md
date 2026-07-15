# OpenBao (dev) — Flux HelmRelease

Official [openbao/openbao](https://github.com/openbao/openbao-helm) chart managed by
Flux (`HelmRepository` + `HelmRelease`). No vendored `helm template` output.

| | |
|---|---|
| Chart | `openbao/openbao` **0.28.5** (app v2.6.0) |
| Endpoint | `http://openbao.openbao.svc.cluster.local:8200` |
| Storage | file backend on Retain hostPath PV `openbao-data-pv` → `/var/lib/openbao/data` @ `k8s-worker-1` |
| TLS | disabled (HTTP); front with `platform-dev-tls` later |

## Apply path

Enable stack: `gitops/clusters/dev/inventory/stacks/platform-openbao/.gitkeep`  
Flux reconciles `stack-platform-openbao` → HR installs the chart.

## Bootstrap (once) / unseal (after restart)

OpenBao starts **sealed**. After the STS is Ready:

```bash
./gitops/root/components/platform/openbao/bootstrap.sh
./gitops/root/components/platform/openbao/smoke.sh
```

Creates `secret/openbao-keys` (ns `openbao`) — **never commit**. Configures KV v2,
Kubernetes auth, and the secret-manager-controller role/policy.

## Storage permissions

Chart runs as uid **100** / gid **1000** with `runAsNonRoot`. After creating the
hostPath (or if init fails with permission denied):

```bash
multipass exec k8s-worker-1 -- sudo chown -R 100:1000 /var/lib/openbao/data
multipass exec k8s-worker-1 -- sudo chmod 775 /var/lib/openbao/data
kubectl -n openbao delete pod openbao-0   # OnDelete STS
```
