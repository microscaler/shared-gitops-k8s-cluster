#!/usr/bin/env bash
# Rolling resize of the ARC runner VMs to K8S_RUNNER_CPUS / K8S_RUNNER_MEM (config/cluster.env), one node at a time,
# without killing a CI job: cordon -> wait until no runner pod is busy on it (an idle runner pod is deleted; ARC
# recreates it elsewhere) -> drain -> multipass stop -> set cpus/memory -> start -> wait Ready -> uncordon.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . config/cluster.env; set +a
CPUS=${K8S_RUNNER_CPUS}; MEM=${K8S_RUNNER_MEM}; WAIT_MAX=${WAIT_MAX:-5400}
busy_pods() { # runner pods on node $1 whose EphemeralRunner has a job
  local node=$1
  for p in $(kubectl -n arc-runners get pods --field-selector spec.nodeName="$node" -o name 2>/dev/null | grep runner | sed 's#pod/##'); do
    job=$(kubectl -n arc-runners get ephemeralrunner "$p" -o jsonpath='{.status.jobRequestId}' 2>/dev/null || true)
    if [ -n "$job" ] && [ "$job" != "0" ]; then echo "$p"; else kubectl -n arc-runners delete ephemeralrunner "$p" --wait=false >/dev/null 2>&1 || true; fi
  done
}
for vm in ${K8S_RUNNERS//,/ }; do
  cur=$(multipass info "$vm" --format json | python3 -c 'import sys,json; i=json.load(sys.stdin)["info"]; print(list(i.values())[0].get("cpu_count",""))')
  echo "$(date -u +%T) $vm: cpus now ${cur}, target ${CPUS} / ${MEM}"
  kubectl cordon "$vm"
  waited=0
  while b=$(busy_pods "$vm"); [ -n "$b" ]; do
    [ $waited -ge $WAIT_MAX ] && { echo "$vm still busy after ${WAIT_MAX}s ($b); leaving it cordoned, skipping"; continue 2; }
    echo "$(date -u +%T) $vm busy: $b"; sleep 60; waited=$((waited+60))
  done
  kubectl drain "$vm" --ignore-daemonsets --delete-emptydir-data --force --timeout=300s >/dev/null
  multipass stop "$vm"
  multipass set "local.$vm.cpus=$CPUS"
  multipass set "local.$vm.memory=$MEM"
  multipass start "$vm"
  until kubectl get node "$vm" --no-headers 2>/dev/null | grep -qw Ready; do sleep 10; done
  kubectl uncordon "$vm"
  echo "$(date -u +%T) $vm: done ($(kubectl get node "$vm" -o jsonpath='{.status.capacity.cpu} CPU {.status.capacity.memory}'))"
done
