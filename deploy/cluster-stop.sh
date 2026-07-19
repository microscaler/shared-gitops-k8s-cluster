#!/usr/bin/env bash
# Intentionally a no-op. Do not tear down Multipass/k3s from a user systemd stop.
# Cluster lifecycle is explicit (cluster/ + multipass recipes), not tied to Tilt.
set -euo pipefail
echo "cluster-stop: no-op (shared-k8s VMs are not stopped by this unit)"
