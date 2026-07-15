# Active context — shared-gitops-k8s-cluster

Updated: 2026-07-15 (Helm migrations + OpenSearch cutover)

## Deferred

- OpenBao ops polish / postgres-ha standbys

## Done this session

- SOPS deployment-profiles process (standard)
- Observability → OpenSearch Helm; removed Grafana/Loki/Prom/Jaeger/Promtail
- Redis → Bitnami Helm (+ Service alias `redis`)
- MinIO → official charts.min.io Helm (existingClaim `/data`)

## Keep raw (see docs/helm-stack-status.md)

imgproxy, messaging, mosquitto, pact, scheduling, pipeline, ai, cluster, cylon-infra, postgres-backup

## Next

Commit/push + Flux reconcile; verify redis/minio/opensearch pods; optional imgproxy later if we accept Service rename.
