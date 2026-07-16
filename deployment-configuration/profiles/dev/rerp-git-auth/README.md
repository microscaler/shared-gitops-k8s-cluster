# RERP Git write credential

This dev profile owns the repository-scoped SSH deploy key used only by Flux
image automation to update image-policy markers in `microscaler/rerp`.

The SOPS-encrypted Secret contains Flux's standard SSH fields:

- `identity` — dedicated ed25519 private key;
- `identity.pub` — matching public key;
- `known_hosts` — GitHub host keys sourced from GitHub's official metadata API.

The matching public key must be installed on `microscaler/rerp` as a write
deploy key named `shared-k8s Flux image automation`. Do not reuse a developer
key, organisation credential, or the shared GitOps repository credential.

The product `GitRepository` and `ImageUpdateAutomation` must not reference this
Secret until the GitHub deploy key is installed and an isolated pull/push test
has passed.
