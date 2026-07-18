# Retired: Bitnami postgresql-ha + Pgpool

Replaced by stack **`postgres`** → [`../postgres`](../postgres) installing
[`lifeguard/charts/postgres`](https://github.com/microscaler/lifeguard/tree/main/charts/postgres)
via Flux `GitRepository` `lifeguard-charts` + `HelmRelease` `data/postgres`.

Profile secrets/values archive: `deployment-configuration/retired/dev/postgres-ha/`.
