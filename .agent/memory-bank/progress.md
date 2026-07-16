# Progress

## 2026-07-16 — profiles on main

Pushed:
- `d54a6da` feat(profiles): deployment-configuration + SOPS + application.properties + ansible
- `8ee45b3` fix(csi): encrypt only Secret data/stringData for Flux SOPS

Observed:
- All `profile-config-*` Ready
- Platform stacks Ready after recreating pact Deployments (SSA value→valueFrom conflict)
- HelmReleases Ready; data/observability/democratic-csi/cylon pods Running

Next: extract remaining Helm chart env knobs (observability, postgres-ha, minio, redis).
