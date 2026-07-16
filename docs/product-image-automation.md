# Product image discovery and automation

Status: **active and end-to-end proven for RERP Accounting dev images**.

The dev cluster separates three responsibilities:

1. Product Tiltfiles build and push `dev-<nanoseconds>` images.
2. Flux ImageRepository/ImagePolicy objects discover the greatest numeric tag.
3. ImageUpdateAutomation may write the selected tag into the product profile
   only after its configured Flux credential passes isolated read and dry-run
   push validation.

RERP Accounting is the first implementation. Its image repositories and
policies are generated from `gitops/inventory/product-components.yaml`; update
markers live with its database Job and Helm releases in the RERP repository.

## Credential boundary

The `product-rerp` GitRepository and its ImageUpdateAutomation use the existing
`flux-system/gitops-auth` SSH credential that bootstraps the shared GitOps
repository. This is a Flux-owned GitHub machine credential, not a developer
workstation key. Its public key is already authorised for both repositories,
so duplicating the private key into another Secret would create needless key
copies and rotation drift.

The activation gate requires the credential to:

- authenticate to `microscaler/rerp` for read and dry-run push;
- be accepted for the `main` branch by the repository's branch policy;
- remain owned by the Flux bootstrap lifecycle and never be copied or committed
  in plaintext;
- pass pull and push validation before automation is enabled.

## Activation sequence

1. Validate `flux-system/gitops-auth` against `microscaler/rerp`.
2. Use the SSH repository URL and add that Secret as `spec.secretRef` on
   `product-rerp` without changing its branch.
3. Add one ImageUpdateAutomation scoped to
   `./deployment-configuration/profiles/dev/rerp/` and `main`.
4. Reconcile once and verify that only image-policy marker lines changed.
5. Confirm the product Kustomizations consume the resulting revision and both
   Helm releases become Ready.

Automation is limited by both an RERP-only policy selector and update path
`./deployment-configuration/profiles/dev/rerp`. A proving run must retag an
existing dev image, then verify that Flux changes only the matching image marker
and that the workload returns Ready.

The first proving run selected Invoice tag `dev-1784204646457677023`, wrote
only its image-policy marker in RERP commit `16907bf`, and completed the Invoice
rollout and Accounting deployment acceptance successfully.

Do not broaden the update path to the repository root, bypass protected-branch
policy, or copy the shared private key into product-owned configuration.
