# Secrets + config audit — deployment-configuration profiles

**Canonical:** `deployment-configuration/profiles/<env>/<component>/`  
**SOP:** [`deployment-configuration/README.md`](../deployment-configuration/README.md)

## Inventory

| Component | App properties | Helm valuesFrom | Secrets | Status |
|-----------|----------------|-----------------|---------|--------|
| pact | `pact-config` | — | `pact-credentials` | OK |
| messaging | `messaging-config` | — | — | OK |
| imgproxy | — | `imgproxy-helm-values` | — | OK |
| postgres-backup | `postgres-backup-config` | — | uses postgres/minio | OK |
| democratic-csi | `democratic-csi-config` | — | driver + ssh YAML | OK |
| cylon-infra | `routellm-config` | — | — | OK |
| observability | — | `observability-helm-values` (OS/dashboards/prepper/otel) | `opensearch-credentials` | OK |
| postgres-ha | — | `postgres-ha-helm-values` | `postgres-credentials` | OK |
| minio | — | `minio-helm-values` | `minio-credentials` | OK |
| redis | — | `redis-helm-values` | — | OK |

Flux: GitOpsSet `profile-config` (replaces `profile-secrets`).

## Remaining

1. FreeRADIUS / Squid passwords → SOPS secrets (still in ConfigMaps).
2. MetalLB annotation patches / LAN proxy sync (inventory check OK).
3. ai / llmrouter secrets not in git (**open**).
