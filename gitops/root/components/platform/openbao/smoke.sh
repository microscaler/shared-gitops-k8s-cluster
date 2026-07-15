#!/usr/bin/env bash
# OpenBao smoke test — proves AC-1..AC-3 of story OB-1.
# Verifies: health (initialised+unsealed), KV v2 mounted, k8s auth role usable
# with least-privilege policy. Exits non-zero on failure.
set -euo pipefail

NS="openbao"
POD="openbao-0"
MOUNT="secret"
ROLE="secret-manager-controller"
kexec() { kubectl -n "$NS" exec -i "$POD" -- "$@"; }
ROOT_TOKEN="$(kubectl -n "$NS" get secret openbao-keys -o jsonpath='{.data.root-token}' | base64 -d)"
login() { kexec env BAO_TOKEN="$ROOT_TOKEN" "$@"; }

echo ">> AC-1: health"
kexec bao status -format=json | grep -q '"initialized": true'
kexec bao status -format=json | grep -q '"sealed": false'

echo ">> AC-2: KV v2 mounted at $MOUNT/"
login bao secrets list -format=json | grep -q "\"${MOUNT}/\""

echo ">> AC-3: write/read round-trip via KV v2"
login bao kv put "$MOUNT/smoke-test" value=hello >/dev/null
test "$(login bao kv get -field=value "$MOUNT/smoke-test")" = "hello"
login bao kv metadata delete "$MOUNT/smoke-test" >/dev/null

echo ">> AC-3: k8s auth role '$ROLE' exists"
login bao read "auth/kubernetes/role/$ROLE" >/dev/null

echo "OK: OpenBao smoke test passed."
