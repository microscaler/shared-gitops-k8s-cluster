# OpenBao (dev) — Flux HelmRelease

Official [openbao/openbao](https://github.com/openbao/openbao-helm) chart managed by
Flux (`HelmRepository` + `HelmRelease`). No vendored `helm template` output.

| | |
|---|---|
| Chart | `openbao/openbao` **0.28.5** (app v2.6.0) |
| Endpoint | `http://openbao.openbao.svc.cluster.local:8200` |
| Storage | file backend on a `zfs-iscsi` CSI PVC (`dataStorage`, 1Gi, dynamically provisioned) |
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

## Storage

The `dataStorage` PVC is provisioned dynamically by the `zfs-iscsi` CSI class
(democratic-csi) — no hostPath or manual node setup. The chart runs as uid
**100** / gid **1000** with `runAsNonRoot` and sets `fsGroup: 1000`, so the CSI
volume is chowned for the pod automatically. If the STS is stuck after a values
change (OnDelete update strategy), roll the pod: `kubectl -n openbao delete pod openbao-0`.
