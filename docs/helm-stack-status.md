# Helm vs raw platform stacks

Updated: 2026-07-16

## Policy

Prefer Flux `HelmRelease` when an upstream chart preserves Service DNS, MetalLB IPs, and Retain PVCs. Keep raw manifests when the chart fights those constraints or is site-specific glue. **Do not vendor charts** — use `HelmRepository` / public `GitRepository` only.

## Status

| Stack | Form | Chart | Notes |
|-------|------|-------|-------|
| postgres-ha | Helm | bitnami/postgresql-ha | bitnamilegacy images; LB alias Service |
| platform-openbao | Helm | openbao/openbao | deferred ops (init/unseal) |
| observability | Helm | opensearch-* + otel-collector | dashboards LB alias |
| redis | Helm | bitnami/redis 20.6.3 | alias Service `redis` + MetalLB .225 |
| minio | Helm | minio/minio 5.4.0 | existingClaim; LB .226 |
| imgproxy | Helm | imgproxy 1.1.0 | official |
| **cluster** | **Helm** | twuni/docker-registry @ git | existingClaim; custom tag-prune CronJob kept |
| **messaging** | **Helm + raw** | jouve/mailpit 0.34.1 | MailHog retired; Inbucket stays raw |
| pact | Helm + raw PG | pact-broker 6.2.2 | dedicated alpine `pact-postgres` kept (PGDATA ≠ Bitnami) |
| pipeline | Helm | fluvio-sys + fluvio-app @ git | SpuGroup + `fluvio-sc` alias |
| cylon-infra/routellm | Helm | litellm-helm 1.92.0 | official OCI |
| democratic-csi | Helm | democratic-csi 0.15.1 | iscsi-portal-ensure CronJob kept |
| mosquitto | raw | — | NanoMQ behind historical `mosquitto` name |
| scheduling | raw | — | faktory + config-watcher sidecar |
| ai | raw | — | internal llmrouter image |
| cylon-infra/proxy | raw | — | Squid + reloader |
| cylon-infra/freeradius | raw | — | site AAA config |
| postgres-backup | raw | — | thin CronJob |
| namespaces / platform-dev-tls | raw | — | platform glue / cert-manager CRs |

## Intentional keep-raw

NanoMQ, FreeRADIUS, Squid, llmrouter, postgres-backup, Faktory (sidecar), pact-postgres (vanilla alpine data dir), MetalLB pools, cert-manager Certificates.
