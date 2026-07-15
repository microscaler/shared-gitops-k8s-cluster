# Deployment profiles — SOPS secrets (canonical process)

This is the **standard** way to store and ship secrets for platform stacks in
`shared-gitops-k8s-cluster`. Prior art: metro
`sam-activity-service/deployment-configuration/profiles/dev-cf`
(`application.secrets.env` + kustomize `secretGenerator`).

Do **not** put plaintext passwords in Helm values, component YAML, or commits.
Do **not** invent a parallel sealed-secret / raw kubectl-only workflow for new
work unless Day-0 bootstrap forces a one-shot (then still encrypt into git).

## Layout

```
deployment-profiles/<env>/<component>/
  application.secrets.env   # SOPS-encrypted dotenv (committed)
  kustomization.yaml        # secretGenerator → Kubernetes Secret

gitops/root/components/<component>/secrets/
  application.secrets.env   # identical ciphertext (Flux path mirror)
  kustomization.yaml        # included by the stack component
```

| Path | Role |
|------|------|
| `deployment-profiles/...` | **Canonical** human/edit path (metro-compatible) |
| `gitops/root/components/.../secrets/` | **Flux mirror** — kustomize-controller only decrypts under the stack `spec.path` |

Always update **both** with the same ciphertext (`just secrets-sync`).

## Keys

| What | Where |
|------|--------|
| Age private key (encrypt/decrypt on ms02) | `~/.config/sops/age/flux-shared-gitops` |
| Age public (`.sops.yaml`) | `age1lh3s2uyxrqu0u7hqgulnd43q3v0xvktukq3fcxuu6gw97uye59rqgjsd07` |
| Flux in-cluster decrypt | `flux-system/sops-age` key `age.agekey` |
| Rules file | repo-root `.sops.yaml` |

Platform stack GitOpsSets set `spec.decryption.provider: sops` → `sops-age`.

## New secret for a component (checklist)

1. Create plaintext dotenv on ms02 only (never commit):
   ```bash
   cat >/tmp/plain.env <<'EOF'
   MY_SECRET=...
   EOF
   ```
2. Encrypt into the canonical profile:
   ```bash
   just secrets-encrypt dev observability /tmp/plain.env
   ```
3. Sync ciphertext into the Flux component mirror:
   ```bash
   just secrets-sync dev observability
   ```
4. Ensure `deployment-profiles/<env>/<component>/kustomization.yaml` and
   `gitops/root/components/<component>/secrets/kustomization.yaml` both
   `secretGenerator` the same Secret name (`envs: [application.secrets.env]`,
   `disableNameSuffixHash: true`).
5. Reference the Secret from Helm/Deployments (`envFrom` / `secretKeyRef`) —
   never inline values.
6. Optional bootstrap before Flux reconciles:
   ```bash
   just secrets-apply dev observability
   ```
7. Commit **encrypted** files only; shred `/tmp/plain.env`.

## Recipes (ms02)

```bash
just secrets-encrypt dev observability /tmp/plain.env
just secrets-decrypt dev observability
just secrets-sync    dev observability
just secrets-apply   dev observability   # kubectl apply -k profile (decrypt temp)
just secrets-ensure-age-key              # create/apply flux-system/sops-age
```

## File format

Dotenv, Flux-compatible (same as metro):

```
KEY=value
OTHER_KEY=value
```

After SOPS:

```
KEY=ENC[AES256_GCM,...]
sops_age__list_0__map_recipient=age1lh3s2...
sops_mac=ENC[...]
```

## Existing example

- Env/component: `dev` / `observability`
- Secret: `observability/opensearch-credentials`
- Keys: `OPENSEARCH_INITIAL_ADMIN_PASSWORD`, `OPENSEARCH_USERNAME`

## Later (OpenBao / SMC)

OpenBao remains the long-term secret *backend*. This dotenv + SOPS path is the
GitOps-facing contract we dogfood now; SMC can consume the same encrypted files
later without changing layout.
