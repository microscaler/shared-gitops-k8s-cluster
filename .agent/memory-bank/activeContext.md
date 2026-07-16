# Active Context

**Last updated:** 2026-07-16 — imgproxy + otel-collector on official Helm.

## Done this session

- Helm `valuesFrom` for postgres-ha / minio / redis / observability
- GitOpsSets catalog migration
- **imgproxy** → official chart `imgproxy/imgproxy` 1.1.0 (`fullnameOverride: imgproxy`)
  - Service :5001 → pod :8080 (chart probe requirement)
- **otel-collector** → official `open-telemetry/opentelemetry-collector` 0.110.7
  - MetalLB `.231` retained; config in `helm-values-otel.yaml`

## Next Helm migrations (from audit)

1. LiteLLM (routellm) — `oci://ghcr.io/berriai/litellm-helm` (BETA)
2. Pact Broker — pact-foundation chart (no Bitnami Postgres subchart)
3. Fluvio — upstream Helm (larger)

## Keep raw

NanoMQ, FreeRADIUS, Squid, llmrouter, postgres-backup CronJob, namespaces, MetalLB pool CRs, cert-manager Certificates.
