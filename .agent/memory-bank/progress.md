# Progress

## 2026-07-16 — OpenGroupware Tilt host registration

Config updated (apply on ms02 still needed if shell was down):
- Ansible `tilt_user_units`: `tilt-opengroupware` port **10852**, workdir `opengroupware`
- `tilt-apps.yaml` + `apps.yaml`: opengroupware / ogw → 10852
- Docs/justfile/cluster-stop + legacy `deploy/tilt-opengroupware.service`

Apply:
```
cd ~/Workspace/microscaler/shared-gitops-k8s-cluster && just tilt-units-apply
systemctl --user enable --now tilt-opengroupware.service
cd ~/Workspace/microscaler/shared-k8s-cluster && just lan-proxy-up
```
UI: `http://tilt-opengroupware.dev.microscaler.local/` (alias `tilt-ogw`)

## 2026-07-16 — Clone rename seasame-idam → sesame-idam

- NFS dir renamed on ms02 (Mac path follows).
- Ansible `tilt_user_units` workdir + `apps.yaml` repo + systemd WorkingDirectory updated.
- `tilt-sesame-idam.service` active with `WorkingDirectory=.../sesame-idam`.
- Reopen Cursor workspace at `.../microscaler/sesame-idam` (old path gone; no symlink).

## 2026-07-16 — Product GitOps cutover (sesame + hauliage)

- Wired `product-components` for `sesame-idam` + `hauliage` (Git URLs: `sesame-idam` / `haulage`).
- Rerp-style split locked in both products:
  - **Flux Job** `scripts/db-init-job.sh` — Pgpool contract, role, database, schema, grants, login verify. No migrations.
  - **Tilt** — `image-*-db-init` publishes bootstrap image; `*-apply-migrations` applies Lifeguard SQL/seeds.
- Commits: sesame `4b0fb07` (+ image automation), hauliage `817935c` (+ image automation).
- Unblocked Pgpool: secret had `rerp,sesame_idam,hauliage` but running pods needed rollout restart to reload `pool_passwd`.

### Bootstrap Ready (2026-07-16 ~17:35)
- Jobs Complete: `sesame-idam-db-init`, `hauliage-db-init` (role/DB/schema only).
- KS Ready: `sesame-idam-idam`, `hauliage-core`.
- Services KS installing HelmReleases — many ImageRepos missing (`dev-0` / no registry tags yet); Helm rate-limit noise while catching up.
- Lesson: never `kubectl apply -k` SOPS bootstrap dirs without decrypt — writes ciphertext as password. Flux SOPS decrypt is the path.
- Lesson: after adding Pgpool custom users, rollout-restart `postgres-ha-pgpool` so `pool_passwd` reloads.

### Still open
- Publish microservice `dev-N` images; enable `FLUX_OWNS_DEPLOY=1` on tilt units.
- Hauliage workers/frontend into profile later.
- `tilt trigger *-apply-migrations` after Flux foundation Ready.

## Earlier — Helm valuesFrom

Pushed: `52fed52` feat(profiles): Helm valuesFrom overlays for platform charts

## Earlier — GitOpsSets / profiles

- `c661f6e` / `21d8484` / `95d742c` / `45302e0` / `d54a6da` / `8ee45b3`
