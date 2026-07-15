#!/usr/bin/env bash
# OpenBao bootstrap for the shared-k8s dev cluster.
#
# Idempotent: initialises + unseals OpenBao (once), stores the unseal key and
# root token in the `openbao-keys` Secret, then enables the KV v2 engine, the
# Kubernetes auth method, the controller policy, and the controller role.
#
# Re-run after a pod restart to unseal again (dev cluster has no auto-unseal).
#
# Prereqs: kubectl context pointing at the shared-k8s cluster; OpenBao pod Running
# (Ready comes only after unseal — do not wait for Ready before init).
# Usage:   ./bootstrap.sh
set -euo pipefail

NS="openbao"
POD="openbao-0"
MOUNT="secret"
CONTROLLER_SA="secret-manager-controller"
CONTROLLER_NS="octopilot-system"
ROLE="secret-manager-controller"
POLICY="secret-manager-controller"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Do not use kubectl exec -i here — it can hang waiting on stdin during init.
kexec() { kubectl -n "$NS" exec "$POD" -- "$@"; }

echo ">> Waiting for OpenBao pod to be Running..."
kubectl -n "$NS" wait --for=jsonpath='{.status.phase}'=Running "pod/$POD" --timeout=180s
# Chart uses OnDelete + sealed-aware probes; wait until bao answers at all
for _ in $(seq 1 30); do
  if kexec bao status -format=json >/dev/null 2>&1 || kexec bao status >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

# --- Initialise (once) -------------------------------------------------------
if kexec bao status -format=json 2>/dev/null | grep -q '"initialized": true'; then
  echo ">> Already initialised."
else
  echo ">> Initialising (1 key share, threshold 1 — dev only)..."
  INIT_JSON="$(kexec bao operator init -key-shares=1 -key-threshold=1 -format=json)"
  UNSEAL_KEY="$(echo "$INIT_JSON" | grep -o '"unseal_keys_b64": \[[^]]*\]' | grep -o '"[A-Za-z0-9+/=]\{20,\}"' | head -1 | tr -d '"')"
  ROOT_TOKEN="$(echo "$INIT_JSON" | grep -o '"root_token": *"[^"]*"' | sed 's/.*"root_token": *"//; s/"$//')"
  kubectl -n "$NS" create secret generic openbao-keys \
    --from-literal=unseal-key="$UNSEAL_KEY" \
    --from-literal=root-token="$ROOT_TOKEN" \
    --dry-run=client -o yaml | kubectl apply -f -
  echo ">> Stored unseal key + root token in secret/openbao-keys."
fi

UNSEAL_KEY="$(kubectl -n "$NS" get secret openbao-keys -o jsonpath='{.data.unseal-key}' | base64 -d)"
ROOT_TOKEN="$(kubectl -n "$NS" get secret openbao-keys -o jsonpath='{.data.root-token}' | base64 -d)"

# --- Unseal ------------------------------------------------------------------
if kexec bao status -format=json 2>/dev/null | grep -q '"sealed": false'; then
  echo ">> Already unsealed."
else
  echo ">> Unsealing..."
  kexec bao operator unseal "$UNSEAL_KEY" >/dev/null
fi

# --- Configure (idempotent) --------------------------------------------------
login() { kexec env BAO_TOKEN="$ROOT_TOKEN" "$@"; }

echo ">> Enabling KV v2 at '$MOUNT/' (if absent)..."
login bao secrets list -format=json | grep -q "\"${MOUNT}/\"" \
  || login bao secrets enable -path="$MOUNT" -version=2 kv

echo ">> Enabling Kubernetes auth (if absent)..."
login bao auth list -format=json | grep -q '"kubernetes/"' \
  || login bao auth enable kubernetes

echo ">> Configuring Kubernetes auth (uses the pod's own SA token/CA)..."
login sh -c 'bao write auth/kubernetes/config \
  kubernetes_host="https://${KUBERNETES_SERVICE_HOST}:${KUBERNETES_SERVICE_PORT}"'

echo ">> Writing controller policy '$POLICY'..."
kubectl -n "$NS" cp "$SCRIPT_DIR/controller-policy.hcl" "$POD:/tmp/controller-policy.hcl"
login bao policy write "$POLICY" /tmp/controller-policy.hcl

echo ">> Writing controller role '$ROLE' (SA $CONTROLLER_SA in $CONTROLLER_NS)..."
login bao write "auth/kubernetes/role/$ROLE" \
  bound_service_account_names="$CONTROLLER_SA" \
  bound_service_account_namespaces="$CONTROLLER_NS" \
  policies="$POLICY" \
  ttl=1h

echo ">> Bootstrap complete. Endpoint: http://openbao.openbao.svc.cluster.local:8200"
