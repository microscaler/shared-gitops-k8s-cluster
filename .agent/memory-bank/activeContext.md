# Active Context

**Last updated:** 2026-07-16 — registry + mailpit on Helm; MailHog retired; Fluvio already Helm.

## Helm migrations done

| Workload | Chart | Notes |
|----------|-------|-------|
| imgproxy | imgproxy/imgproxy 1.1.0 | Service :5001→8080 |
| otel-collector | open-telemetry 0.110.7 | MetalLB .231 |
| routellm (LiteLLM) | oci litellm-helm 1.92.0 | Bitnami DB/Redis **off**; MetalLB .221 |
| pact-broker | pact-broker 6.2.2 | External `pact-postgres` (raw); MetalLB .232 |
| Fluvio | fluvio-sys/app @ public git | pin `5267394…`; SpuGroup + `fluvio-sc` alias |
| **registry** | twuni/docker-registry @ git `803018a` | existingClaim; custom tag-prune CronJob kept |
| **mailpit** | jouve/mailpit 0.34.1 OCI | alias LB Service; MailHog removed |

## Intentional keep-raw

FreeRADIUS / Squid / NanoMQ / llmrouter / postgres-backup / Faktory (config-watcher) / pact-postgres (alpine PGDATA) / namespaces / cert-manager CRs / MetalLB pools.

## Next optional

1. Inbucket community chart (low value)
2. Faktory only if sidecar can stay out-of-band
3. pact-postgres → Helm only with wipe or CNPG (do not Bitnami onto alpine PVC)
