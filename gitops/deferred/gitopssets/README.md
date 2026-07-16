# Deferred / archival GitOpsSets artifacts

**Do not apply from here.** Active path:

| Piece | Path |
|-------|------|
| Controller | `gitops/root/controllers/gitopssets/` |
| GitOpsSets | `gitops/root/gitopssets/` (`platform-stacks`, `profile-config`, `product-components`) |
| Dev control | `gitops/clusters/dev/control/{gitopssets-controller,platform-gitopssets}-ks.yaml`

Refresh images: `just push-gitopssets-images`

## Why this folder exists

Historical copies of control-plane KS and an older `root-gitopssets/` snapshot
(pre–`profile-config`, pre–catalog `dependsOn`). Kept only as reference for
plain-Flux fallback (`stack-namespaces-ks.yaml`) when GitOpsSets cannot run.

## Staging / prod

When enabling GitOpsSets on staging/prod:

1. Remove static `stack-namespaces-ks.yaml` from that cluster’s `control/`
   (name collides with generated `stack-namespaces`).
2. Add a `list` element + `stacks.yaml` path in `platform-stacks` Matrix
   (and a `profile_env` row in `profile-config`).
3. Run `just sync-stack-inventory <id>` and commit the generated file.
