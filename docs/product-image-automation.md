# Product image discovery and automation

Status: **discovery enabled; Git writes credential-gated**.

The dev cluster separates three responsibilities:

1. Product Tiltfiles build and push `dev-<nanoseconds>` images.
2. Flux ImageRepository/ImagePolicy objects discover the greatest numeric tag.
3. ImageUpdateAutomation may write the selected tag into the product profile
   only after a repository-scoped write credential is deliberately installed.

RERP Accounting is the first implementation. Its image repositories and
policies are generated from `gitops/inventory/product-components.yaml`; update
markers live with its database Job and Helm releases in the RERP repository.

## Why automation is not installed yet

The `product-rerp` GitRepository currently uses public HTTPS for read-only
reconciliation. ImageUpdateAutomation needs authenticated Git push access.
Installing an automation object without that credential would create a
permanent failing controller and obscure real reconciliation failures.

The activation gate is a `flux-system/rerp-git-auth` Secret backed by a deploy
key or fine-grained token which:

- can write only `microscaler/rerp`;
- cannot administer the repository or the GitHub organisation;
- is accepted for the `main` branch by the repository's branch policy;
- is SOPS-managed or provisioned by the cluster secret controller, never
  committed in plaintext;
- is tested for pull and push before automation is enabled.

## Activation sequence

1. Provision and validate `flux-system/rerp-git-auth`.
2. Add that Secret as `spec.secretRef` on `product-rerp` without changing its
   repository URL or branch.
3. Add one ImageUpdateAutomation scoped to
   `./deployment-configuration/profiles/dev/rerp/` and `main`.
4. Reconcile once and verify that only image-policy marker lines changed.
5. Confirm the product Kustomizations consume the resulting revision and both
   Helm releases become Ready.

Do not broaden the update path to the repository root, bypass protected-branch
policy, or reuse the shared GitOps repository credential.
