# Active Context

**Last updated:** 2026-07-16 — LiteLLM + Pact Broker on official Helm.

## Helm migrations done

| Workload | Chart | Notes |
|----------|-------|-------|
| imgproxy | imgproxy/imgproxy 1.1.0 | Service :5001→8080 |
| otel-collector | open-telemetry 0.110.7 | MetalLB .231 |
| routellm (LiteLLM) | oci litellm-helm 1.92.0 | Bitnami DB/Redis **off**; memory 1.5Gi; MetalLB .221 |
| pact-broker | pact-broker 6.2.2 | External `pact-postgres` (raw); MetalLB .232 |

## Deferred

- **Fluvio** — still raw CRDs/SC/SPU; upstream Helm exists but is a large cutover (separate story).
- FreeRADIUS / Squid / NanoMQ / llmrouter / postgres-backup CronJob — keep raw (audit).

## Next optional

1. Fluvio Helm cutover (dedicated)
2. Messaging charts (mailpit) or retire MailHog
3. twuni docker-registry for cluster registry
