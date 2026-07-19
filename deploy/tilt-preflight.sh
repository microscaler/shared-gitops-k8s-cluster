#!/usr/bin/env bash
# Tilt preflight — shared-k8s cluster readiness gate.
#
# Runs as ExecStartPre for the per-project tilt-*.service units so a tilt
# instance fails fast with an actionable message instead of starting against a
# missing kubeconfig or an unreachable API server (which surfaces later as
# confusing build errors inside Tilt).
#
# Fatal:   kubectl present, kubeconfig readable, API server reachable.
# Warning: shared platform namespaces present.
#
# Overrides:
#   KUBECONFIG                   explicit kubeconfig (default: repo kubeconfig/shared-k8s.yaml)
#   TILT_PREFLIGHT_TIMEOUT       API request timeout (default: 10s)
#   TILT_PREFLIGHT_NAMESPACES    space-separated namespaces to check (default: "data observability")
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KUBECONFIG_PATH="${KUBECONFIG:-$REPO_ROOT/kubeconfig/shared-k8s.yaml}"
API_TIMEOUT="${TILT_PREFLIGHT_TIMEOUT:-10s}"
SHARED_NS="${TILT_PREFLIGHT_NAMESPACES:-data observability}"

fail() { echo "preflight: FATAL: $*" >&2; exit 1; }

echo ">> preflight: kubectl"
command -v kubectl >/dev/null 2>&1 || fail "kubectl not found on PATH ($PATH)"

echo ">> preflight: kubeconfig ($KUBECONFIG_PATH)"
[ -r "$KUBECONFIG_PATH" ] || fail "kubeconfig not readable at $KUBECONFIG_PATH — is the shared cluster provisioned?"

export KUBECONFIG="$KUBECONFIG_PATH"

echo ">> preflight: API server reachable"
kubectl cluster-info --request-timeout="$API_TIMEOUT" >/dev/null 2>&1 \
  || fail "cannot reach the Kubernetes API using $KUBECONFIG_PATH — is the shared cluster running?"

echo ">> preflight: shared platform namespaces"
for ns in $SHARED_NS; do
  if kubectl get namespace "$ns" --request-timeout="$API_TIMEOUT" >/dev/null 2>&1; then
    echo "   ok: $ns"
  else
    echo "   warn: namespace '$ns' not found — shared services (postgres/redis/otel) may be unavailable" >&2
  fi
done

echo ">> preflight: ok"
