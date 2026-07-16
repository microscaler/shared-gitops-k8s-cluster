# Progress

## Done (2026-07-16) — secrets → SOPS

- Audited gitops components for plaintext Secrets
- Migrated postgres-ha, minio, pact to `deployment-profiles/dev/*` + Flux `secrets/` mirrors
- postgres-ha HelmRelease: `existingSecret: postgres-credentials` (no inline passwords)
- Applied to cluster via `just secrets-apply`
- Fixed `just secrets-encrypt` in-place encrypt for `.sops.yaml` path_regex
- Docs: `docs/secrets-audit.md`, updated `deployment-profiles/README.md`, `AGENTS.md`

## Open

- cylon-infra FreeRADIUS/Squid passwords still in ConfigMaps
- ai/llmrouter optional API keys profile when needed
- Rotate preserved dev passwords before non-dev
