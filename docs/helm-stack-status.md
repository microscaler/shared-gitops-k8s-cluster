# Helm vs raw platform stacks

Updated: 2026-07-15

## Policy

Prefer Flux `HelmRelease` when an upstream chart preserves Service DNS, MetalLB IPs, and Retain PVCs. Keep raw manifests when the chart fights those constraints.

## Status

| Stack | Form | Chart | Notes |
|-------|------|-------|-------|
| postgres-ha | Helm | bitnami/postgresql-ha | bitnamilegacy images |
| platform-openbao | Helm | openbao/openbao | deferred ops (init/unseal) |
| observability | Helm + raw OTel | opensearch-* | Grafana/Loki/Prom/Jaeger removed |
| **redis** | **Helm** | bitnami/redis 20.6.3 | alias Service `redis` + MetalLB .225; existingClaim |
| **minio** | **Helm** | minio/minio 5.4.0 | existingClaim; mountPath `/data`; LB .226 shared |
| imgproxy | raw | — | chart renames Service/ports (`imgproxy-imgproxy:80`); keep raw |
| messaging | raw | — | mailpit only maybe later; mailhog abandoned |
| mosquitto | raw | — | NanoMQ behind historical `mosquitto` name |
| pact | raw | — | broker+dedicated PG; later |
| scheduling | raw | — | faktory + config-watcher sidecar |
| pipeline | raw | — | Fluvio CRDs |
| ai | raw | — | internal llmrouter image |
| cluster | raw | — | registry + prune CronJob |
| cylon-infra | raw | — | site-specific proxy/RADIUS |
| postgres-backup | raw | — | thin CronJob |

## Redis DNS note

Bitnami creates `redis-master`. We keep LoadBalancer Service `redis` selecting the master pod so app DNS and LAN proxy stay unchanged.
