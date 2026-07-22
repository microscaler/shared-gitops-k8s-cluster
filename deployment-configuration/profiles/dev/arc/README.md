# ARC credentials (dev)

Create a plaintext dotenv, then encrypt:

```bash
# Preferred long-term: GitHub App (org) with Self-hosted runners: Write
# PAT fallback (org admin): github_token=ghp_...  (needs admin:org / manage runners)

cat > /tmp/arc.secrets.env <<'EOF'
github_token=REPLACE_ME
EOF

cd ~/Workspace/microscaler/shared-gitops-k8s-cluster
just secrets-encrypt dev arc /tmp/arc.secrets.env
rm -f /tmp/arc.secrets.env
just secrets-apply dev arc
```

For a GitHub App instead of PAT, use:

```env
github_app_id="123456"
github_app_installation_id="654321"
github_app_private_key="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
```

(`github_token` and App keys are mutually exclusive in one secret.)
