# Progress — shared-gitops-k8s-cluster

## Done (2026-07-15)

- [x] Adopt SOPS dotenv as standard secrets process (AGENTS, design, README, just recipes)
- [x] Create age key on ms02 for shared-gitops SOPS
- [x] Apply `flux-system/sops-age` for Flux decryption
- [x] Apply `observability/opensearch-credentials`
- [x] Encrypt dotenv at `deployment-profiles/dev/observability/application.secrets.env`
- [x] Mirror under component `secrets/` for Flux
- [x] Wire OpenSearch HelmRelease `envFrom` → credentials
- [x] Enable SOPS decryption on platform-stacks GitOpsSet

## In progress

- OpenSearch observability cutover (Helm + OTel + remove old stack)

## Backlog

- Migrate remaining inline passwords (minio, postgres-ha, pact, …) onto deployment-profiles when those stacks are next touched
