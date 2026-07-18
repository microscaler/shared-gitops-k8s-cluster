# Retired: `postgres-ha`

Replaced by stack **`postgres`** → [`../postgres`](../postgres), which installs
[`lifeguard/charts/postgres`](https://github.com/microscaler/lifeguard/tree/main/charts/postgres)
via Flux (`GitRepository` `lifeguard-charts` + `HelmRelease` `postgres`).

Do not re-enable this directory in `gitops/inventory/platform-stacks.yaml`.
