# Active context — shared-gitops-k8s-cluster

Updated: 2026-07-15

## Status

Phase 3: **ns `data` platform workloads on Flux**, including mosquitto (NanoMQ).

## Flux stacks (dev)

- namespaces, cluster, cylon-infra, platform-dev-tls
- postgres-ha, minio, postgres-backup
- redis, messaging, pact, imgproxy, **mosquitto**

## Toggle mosquitto

Enable: `gitops/clusters/dev/inventory/stacks/mosquitto/.gitkeep`  
Disable: remove that directory and push (Flux prune).

Hauliage Tilt no longer builds/deploys nanomq (local Tiltfile change; commit in hauliage when ready).

## Next

Fix postgres-ha standbys; scheduling/pipeline/observability/ai/openbao
