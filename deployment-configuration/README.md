# Deployment configuration — profiles (SMC-aligned)

Canonical path for **env-specific config and secrets**:

```
deployment-configuration/profiles/<env>/<component>/
```

Prior art: metro `sam-activity-service/deployment-configuration/profiles/dev-cf`,
secret-manager-controller `deployment-configuration/profiles/dev`.

## Files

| File | Purpose | Cluster object |
|------|---------|----------------|
| `application.properties` | Non-secret app env (`KEY=value`) | ConfigMap via `configMapGenerator` (`envs:`) |
| `helm-values.yaml` / `helm-values-*.yaml` | Non-secret Helm chart overlays (replicas, tags, storage, resources, security flags) | ConfigMap via `configMapGenerator` (`files:`) → HelmRelease `valuesFrom` |
| `application.secrets.env`, `*.secrets.env` | SOPS-encrypted secrets (dotenv); use separate files for least-privilege Secrets | Secret via `secretGenerator` |
| `*.secret.yaml` | SOPS-encrypted Secret YAML (when dotenv unfit) | Secret resources |
| `kustomization.yaml` | Generators + resources for this profile | applied by Flux |

Do **not** hardcode env-specific hosts, flags, usernames, buckets, replicas,
image tags, or storage sizes in `gitops/root/components/` HelmRelease `values`.

| Kind of config | Where |
|----------------|-------|
| Pod/env `KEY=value` | `application.properties` → `configMapKeyRef` / `envFrom` |
| Helm chart knobs | `helm-values.yaml` → ConfigMap → HelmRelease `valuesFrom` |
| Secrets | `application.secrets.env` / `*.secret.yaml` (SOPS) |
| MetalLB IPs | `gitops/inventory/metallb-services.yaml` (+ annotations on Services/HR) |

HelmRelease `spec.values` keeps only structural wiring (chart identity,
`existingSecret`, MetalLB annotations, instance-bound affinity). Flux merges
`valuesFrom` then applies `spec.values` on top (inline wins on conflicts).

Do **not** put secrets in `application.properties` or `helm-values*.yaml`.

## Layout example

```
deployment-configuration/profiles/dev/pact/
  application.properties    # → ConfigMap pact-config
  application.secrets.env   # → Secret pact-credentials (SOPS)
  kustomization.yaml
```

```yaml
# kustomization.yaml (metro pattern)
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: data
configMapGenerator:
  - name: pact-config
    envs: [application.properties]
secretGenerator:
  - name: pact-credentials
    envs: [application.secrets.env]
generatorOptions:
  disableNameSuffixHash: true
```

## Flux

GitOpsSet `profile-config` watches `deployment-configuration/profiles/dev/*` and
creates Flux Kustomization `profile-config-<component>` with SOPS decryption
(`flux-system/sops-age`).

## Recipes (ms02)

```bash
just secrets-encrypt dev <component> /tmp/plain.env
just secrets-apply   dev <component>   # bootstrap ConfigMap+Secret from profile
just secrets-ensure-age-key
```

Edit `application.properties` in place (plaintext, committed). Commit and let
Flux reconcile, or `just secrets-apply` for an immediate ConfigMap refresh.

## Existing profiles (`dev`)

| Component | ConfigMap(s) | Secret(s) |
|-----------|--------------|-----------|
| pact | `pact-config` | `pact-credentials` |
| messaging | `messaging-config` | — |
| imgproxy | `imgproxy-config` | — |
| postgres-backup | `postgres-backup-config` | (uses postgres/minio secrets) |
| democratic-csi | `democratic-csi-config` | driver-config + ssh-key |
| cylon-infra | `routellm-config` | — |
| observability | `observability-helm-values` | `opensearch-credentials` |
| postgres-ha | `postgres-ha-helm-values` | `postgres-credentials` |
| minio | `minio-helm-values` | `minio-credentials` |
| redis | `redis-helm-values` | — |

### Helm `valuesFrom` example

```yaml
# profiles/dev/postgres-ha/kustomization.yaml
configMapGenerator:
  - name: postgres-ha-helm-values
    files:
      - values.yaml=helm-values.yaml
```

```yaml
# gitops/root/components/postgres-ha/helm-release.yaml
spec:
  valuesFrom:
    - kind: ConfigMap
      name: postgres-ha-helm-values
      valuesKey: values.yaml
  values:
    fullnameOverride: postgres-ha
    postgresql:
      existingSecret: postgres-credentials
```

Product and suite profiles are owned by their product repositories and
reconciled by Flux `GitRepository`/`Kustomization` components from this
platform repository, following the SAM Flux pattern. For example, RERP
Accounting lives at
`rerp/deployment-configuration/profiles/dev/rerp/accounting/` and is reconciled
from `gitops/inventory/product-components.yaml` by the `product-components`
GitOpsSet. This repository retains the composition and platform-side
configuration such as Pgpool's matching custom-user source; Tilt must not
independently apply the profile.

Audit: [`docs/secrets-audit.md`](../docs/secrets-audit.md).
