# Observability: OpenSearch (Helm) + OTel → Data Prepper

Stack path: `gitops/root/components/observability/`

| Piece | How |
|-------|-----|
| OpenSearch | HelmRelease `opensearch` (chart 2.38.0), single-node, security off, PVC `local-path-retain` |
| Dashboards | HelmRelease + MetalLB Service `.227:5601` |
| Data Prepper | HelmRelease — OTLP ingest → OpenSearch |
| OTel collector | Raw Deployment, LB `.231` — exporters → Data Prepper |
| Credentials | SOPS `deployment-profiles/dev/observability/application.secrets.env` → Secret `opensearch-credentials` |

Removed: Grafana, Loki, Prometheus, Promtail, Jaeger.

LAN: `opensearch.dev.microscaler.local` / `grafana.dev.microscaler.local` → Dashboards; `:3000` TCP proxy remaps to 5601.
