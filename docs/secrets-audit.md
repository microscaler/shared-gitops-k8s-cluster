# Secrets + config audit — deployment-configuration profiles

**Canonical:** `deployment-configuration/profiles/<env>/<component>/`  
**SOP:** [`deployment-configuration/README.md`](../deployment-configuration/README.md)

## Inventory

| Component | `application.properties` | Secrets | Status |
|-----------|--------------------------|---------|--------|
| pact | yes → `pact-config` | `pact-credentials` | OK |
| messaging | yes → `messaging-config` | — | OK |
| imgproxy | yes → `imgproxy-config` | — | OK |
| postgres-backup | yes → `postgres-backup-config` | uses postgres/minio | OK |
| democratic-csi | yes → `democratic-csi-config` | driver + ssh YAML | OK |
| cylon-infra | yes → `routellm-config` | — | OK |
| observability | — | `opensearch-credentials` | secrets OK; Helm flags still in chart |
| postgres-ha | — | `postgres-credentials` | secrets OK; Helm values still in chart |
| minio | — | `minio-credentials` | secrets OK; Helm values still in chart |
| cylon freeradius/squid | — | passwords in ConfigMaps | **open** |
| ai / llmrouter | — | not in git | **open** |

Flux: GitOpsSet `profile-config` (replaces `profile-secrets`).

## Remaining

1. Extract Helm env knobs (replicas, tags, storage, security flags) for observability / postgres-ha / minio / redis via `valuesFrom` ConfigMap from properties.
2. MetalLB IPs → inventory dryness (not properties).
3. FreeRADIUS / Squid passwords → SOPS secrets.
