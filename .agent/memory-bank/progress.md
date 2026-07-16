# Progress

## 2026-07-16 — GitOpsSets audit migration

Pushed:
- `c661f6e` feat(gitopssets): catalog-driven stacks with dependsOn and profiles
- `21d8484` chore(gitopssets): add sync/check recipes and inventory validation
- `95d742c` fix(gitopssets): grant image toolkit RBAC to platform SA

Verified on ms02 (rev `main@sha1:95d742c`):
- `just validate-inventory` OK (dev/staging/prod stacks.yaml)
- `just check-metallb-inventory` OK
- All GitOpsSets Ready: platform-stacks, profile-config, product-components
- `platform-gitopssets` KS Ready
- All `stack-*` and `profile-config-*` Ready
- Sample dependsOn: pact → namespaces + profile-config-pact; postgres-backup → postgres-ha + minio + profile-config

## Earlier — profiles on main

- `d54a6da` feat(profiles): deployment-configuration + SOPS + application.properties
- `8ee45b3` fix(csi): encrypt only Secret data/stringData for Flux SOPS

Next: Helm chart env knobs via valuesFrom; cylon FreeRADIUS/Squid secrets.
