#!/usr/bin/env bash
# Ensure the shared-k8s API is reachable before app Tilts start.
# VM create / Multipass bootstrap lives in this repo's multipass/ + cluster/
# recipes when needed; this oneshot is a readiness gate, not a provisioner.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KCFG="${KUBECONFIG:-${REPO_ROOT}/kubeconfig/shared-k8s.yaml}"

if [[ ! -f "${KCFG}" ]]; then
  echo "cluster-start: missing kubeconfig ${KCFG}" >&2
  exit 1
fi

export KUBECONFIG="${KCFG}"
if ! kubectl get nodes --request-timeout=15s --no-headers 2>/dev/null | grep -q Ready; then
  echo "cluster-start: no Ready nodes via ${KCFG}" >&2
  echo "  Check Multipass VMs / k3s, then: kubectl --kubeconfig=${KCFG} get nodes" >&2
  exit 1
fi

echo "cluster-start: shared-k8s API ready ($(kubectl get nodes --no-headers 2>/dev/null | wc -l | tr -d ' ') node(s))"
