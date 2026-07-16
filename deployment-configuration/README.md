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
| `application.properties` | Non-secret env config (`KEY=value`) | ConfigMap via `configMapGenerator` |
| `application.secrets.env` | SOPS-encrypted secrets (dotenv) | Secret via `secretGenerator` |
| `*.secret.yaml` | SOPS-encrypted Secret YAML (when dotenv unfit) | Secret resources |
| `kustomization.yaml` | Generators + resources for this profile | applied by Flux |

Do **not** hardcode env-specific hosts, flags, usernames, or buckets in
`gitops/root/components/` Helm values or ConfigMaps. Put them in
`application.properties` and reference the generated ConfigMap
(`configMapKeyRef` / `envFrom`).

Do **not** put secrets in `application.properties` — use
`application.secrets.env` (or `*.secret.yaml`).

MetalLB IPs stay in `gitops/inventory/metallb-services.yaml` (not properties).

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

| Component | ConfigMap | Secret(s) |
|-----------|-----------|-----------|
| pact | `pact-config` | `pact-credentials` |
| messaging | `messaging-config` | — |
| imgproxy | `imgproxy-config` | — |
| postgres-backup | `postgres-backup-config` | (uses postgres/minio secrets) |
| democratic-csi | `democratic-csi-config` | driver-config + ssh-key |
| cylon-infra | `routellm-config` | — |
| observability | — | `opensearch-credentials` |
| postgres-ha | — | `postgres-credentials` |
| minio | — | `minio-credentials` |

Still to extract from Helm values (replicas, tags, storage): observability,
postgres-ha, minio, redis — use Helm `valuesFrom` ConfigMap when ready.

Audit: [`docs/secrets-audit.md`](../docs/secrets-audit.md).
