# Day-0 Multipass/k3s lifecycle for shared-gitops-k8s-cluster (ms02).
# Invoked from the main justfile: `just cluster-create` / `just --justfile day0.justfile …`
# Platform workloads after Day 0 are Flux-owned — do not re-enable platform Tilt.

set shell := ["bash", "-uc"]
set dotenv-path := "config/cluster.env"
set dotenv-load

default:
    @just --list

# -----------------------------------------------------------------------------
# Multipass VMs — 1 control plane + 3 workers
# -----------------------------------------------------------------------------

# Launch control plane VM and install k3s server.
vm-create-cp:
    #!/usr/bin/env bash
    set -euo pipefail
    source config/cluster.env
    if ! multipass info "${K8S_CP}" &>/dev/null; then
        python3 tools/render_cloud_init.py server --output .multipass/k8s-cp-cloud-init.yaml
        multipass launch 24.04 \
            --name "${K8S_CP}" \
            --cpus "${K8S_CP_CPUS}" \
            --memory "${K8S_CP_MEM}" \
            --disk "${K8S_CP_DISK}" \
            --cloud-init .multipass/k8s-cp-cloud-init.yaml
    else
        echo "Control plane ${K8S_CP} already exists."
    fi
    just k3s-install-server
    multipass list

# Install k3s server on control plane (idempotent).
k3s-install-server:
    #!/usr/bin/env bash
    set -euo pipefail
    source config/cluster.env
    ip="$(just _vm-ipv4 "${K8S_CP}")"
    echo "Control plane ${K8S_CP} at ${ip}"
    mkdir -p .cluster
    echo "K8S_CP_IP=${ip}" > .cluster/runtime.env
    if multipass exec "${K8S_CP}" -- test -f /etc/rancher/k3s/k3s.yaml 2>/dev/null; then
        echo "k3s server already installed on ${K8S_CP}."
        exit 0
    fi
    echo "Installing k3s server on ${K8S_CP} (${ip})..."
    multipass exec "${K8S_CP}" -- sudo bash -c \
        "curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC='server --tls-san ${ip} --node-ip ${ip} --write-kubeconfig-mode 644 --disable traefik --disable servicelb --cluster-init' sh -"
    for i in $(seq 1 120); do
        if multipass exec "${K8S_CP}" -- test -f /etc/rancher/k3s/k3s.yaml 2>/dev/null; then
            echo "k3s server ready on ${K8S_CP} (${ip})."
            exit 0
        fi
        sleep 5
    done
    echo "ERROR: k3s did not start on ${K8S_CP}" >&2
    multipass exec "${K8S_CP}" -- sudo journalctl -u k3s -n 30 --no-pager >&2 || true
    exit 1

# Return primary IPv4 for a Multipass instance.
_vm-ipv4 vm:
    #!/usr/bin/env bash
    set -euo pipefail
    vm="{{vm}}"
    for i in $(seq 1 60); do
        ip="$(multipass info "${vm}" 2>/dev/null | awk '/IPv4/ {print $2; exit}')"
        if [[ -n "${ip}" && "${ip}" != "--" ]]; then
            echo "${ip}"
            exit 0
        fi
        sleep 3
    done
    echo "ERROR: no IPv4 for ${vm}" >&2
    exit 1

# Launch workers, join cluster, wait for Ready nodes.
vm-create-workers: vm-create-cp
    #!/usr/bin/env bash
    set -euo pipefail
    source config/cluster.env
    token="$(multipass exec "${K8S_CP}" -- sudo cat /var/lib/rancher/k3s/server/node-token)"
    cp_ip="$(just _vm-ipv4 "${K8S_CP}")"
    for worker in ${K8S_WORKERS//,/ }; do
        if ! multipass info "${worker}" &>/dev/null; then
            python3 tools/render_cloud_init.py agent \
                --worker-ip "0.0.0.0" \
                --k3s-token "${token}" \
                --output ".multipass/${worker}-cloud-init.yaml"
            multipass launch 24.04 \
                --name "${worker}" \
                --cpus "${K8S_WORKER_CPUS}" \
                --memory "${K8S_WORKER_MEM}" \
                --disk "${K8S_WORKER_DISK}" \
                --cloud-init ".multipass/${worker}-cloud-init.yaml"
        else
            echo "Worker ${worker} already exists."
        fi
        worker_ip="$(just _vm-ipv4 "${worker}")"
        echo "${worker}=${worker_ip}" >> .cluster/runtime.env
        just k3s-install-agent "${worker}" "${worker_ip}" "${token}" "${cp_ip}"
    done
    just cluster-fetch-kubeconfig
    echo "Waiting for 4 Ready nodes..."
    export KUBECONFIG="$(pwd)/kubeconfig/shared-k8s.yaml"
    for i in $(seq 1 90); do
        ready="$(kubectl get nodes --no-headers 2>/dev/null | grep -c ' Ready ' || true)"
        if [[ "${ready}" -ge 4 ]]; then break; fi
        sleep 5
    done
    kubectl get nodes -o wide

# Join a worker to the cluster (idempotent).
k3s-install-agent worker ip token cp_ip:
    #!/usr/bin/env bash
    set -euo pipefail
    source config/cluster.env
    worker="{{worker}}"
    ip="{{ip}}"
    token="{{token}}"
    cp_ip="{{cp_ip}}"
    if multipass exec "${worker}" -- test -f /etc/rancher/k3s/k3s-agent.env 2>/dev/null; then
        if multipass exec "${worker}" -- systemctl is-active --quiet k3s-agent 2>/dev/null; then
            echo "k3s agent already running on ${worker}."
            exit 0
        fi
    fi
    echo "Installing k3s agent on ${worker} (${ip})..."
    multipass exec "${worker}" -- sudo bash -c \
        "curl -sfL https://get.k3s.io | K3S_URL=https://${cp_ip}:6443 K3S_TOKEN='${token}' INSTALL_K3S_EXEC='agent --node-ip ${ip}' sh -"
    for i in $(seq 1 60); do
        if multipass exec "${worker}" -- systemctl is-active --quiet k3s-agent 2>/dev/null; then
            echo "k3s agent ready on ${worker}."
            exit 0
        fi
        sleep 5
    done
    echo "ERROR: k3s agent did not start on ${worker}" >&2
    exit 1

# Bind-mount ms02 workspace into workers (cylon-daemon hostPath).
vm-mount-workspace:
    #!/usr/bin/env bash
    set -euo pipefail
    source config/cluster.env
    for worker in ${K8S_WORKERS//,/ }; do
        if ! multipass info "${worker}" &>/dev/null; then
            echo "ERROR: ${worker} missing" >&2
            exit 1
        fi
        multipass mount "${WORKSPACE_HOST}" "${worker}:${WORKSPACE_GUEST}" || true
        multipass exec "${worker}" -- test -f "${WORKSPACE_GUEST}/cylon/Cargo.toml"
        echo "OK: workspace mounted on ${worker}"
    done

# Rolling worker resize to cluster.env sizing (drain -> stop -> set disk/mem -> start -> uncordon).
workers-resize:
    python3 tools/manage_workers.py resize

# Push kubelet image-GC / eviction config (multipass cloud-init parity) to existing nodes.
workers-apply-k3s-config:
    python3 tools/manage_workers.py apply-k3s-config

# Stop and delete all cluster VMs. DESTRUCTIVE.
vm-delete:
    #!/usr/bin/env bash
    set -euo pipefail
    source config/cluster.env
    echo "WARNING: deleting Multipass VMs for shared-k8s cluster."
    for vm in ${K8S_CP} ${K8S_WORKERS//,/ }; do
        multipass stop "${vm}" 2>/dev/null || true
        multipass delete "${vm}" --purge 2>/dev/null || true
    done
    multipass list

# -----------------------------------------------------------------------------
# kubectl context
# -----------------------------------------------------------------------------

cluster-fetch-kubeconfig: k3s-install-server
    #!/usr/bin/env bash
    set -euo pipefail
    source config/cluster.env
    if [[ -f .cluster/runtime.env ]]; then source .cluster/runtime.env; fi
    cp_ip="${K8S_CP_IP:-$(just _vm-ipv4 "${K8S_CP}")}"
    mkdir -p kubeconfig
    multipass exec "${K8S_CP}" -- sudo cat /etc/rancher/k3s/k3s.yaml \
        | sed "s/127.0.0.1/${cp_ip}/g" \
        > kubeconfig/shared-k8s.yaml
    chmod 600 kubeconfig/shared-k8s.yaml
    export KUBECONFIG="$(pwd)/kubeconfig/shared-k8s.yaml"
    kubectl config rename-context default "${K8S_CONTEXT}" 2>/dev/null || true
    echo "Kubeconfig: $(pwd)/kubeconfig/shared-k8s.yaml (context ${K8S_CONTEXT})"

context:
    #!/usr/bin/env bash
    set -euo pipefail
    source config/cluster.env
    export KUBECONFIG="$(pwd)/kubeconfig/shared-k8s.yaml"
    kubectl config use-context "${K8S_CONTEXT}"

# -----------------------------------------------------------------------------
# Cluster bootstrap — MetalLB + in-cluster registry
# -----------------------------------------------------------------------------

cluster-bootstrap: cluster-fetch-kubeconfig
    #!/usr/bin/env bash
    set -euo pipefail
    source config/cluster.env
    export KUBECONFIG="$(pwd)/kubeconfig/shared-k8s.yaml"
    echo "Installing MetalLB..."
    kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.9/config/manifests/metallb-native.yaml
    echo "Waiting for MetalLB controller..."
    kubectl rollout status deployment/controller -n metallb-system --timeout=180s
    kubectl rollout status daemonset/speaker -n metallb-system --timeout=180s
    echo "Applying cluster addons (registry + IP pool)..."
    kubectl apply -k k8s/cluster
    echo "Waiting for registry LoadBalancer..."
    for i in $(seq 1 60); do
        ip="$(kubectl get svc registry -n registry -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)"
        if [[ -n "${ip}" ]]; then break; fi
        sleep 3
    done
    kubectl get svc -n registry
    just registry-verify
    just registry-configure-nodes

# Push containerd registry mirrors to all k3s nodes (required for in-cluster image pulls).
registry-configure-nodes:
    python3 tools/configure_k3s_registries.py --apply-nodes

registry-configure: registry-configure-host registry-configure-nodes

# Verify in-cluster registry responds on MetalLB IP.
registry-verify: context
    #!/usr/bin/env bash
    set -euo pipefail
    source config/cluster.env
    export KUBECONFIG="$(pwd)/kubeconfig/shared-k8s.yaml"
    kubectl rollout status deployment/registry -n registry --timeout=180s
    for i in $(seq 1 30); do
        if curl -sf "http://${REGISTRY_LB_IP}:${REGISTRY_PORT}/v2/" >/dev/null; then
            echo "OK: registry at http://${REGISTRY_LB_IP}:${REGISTRY_PORT}/"
            echo "Push: docker tag myimage:latest ${REGISTRY_LB_IP}:${REGISTRY_PORT}/myimage:latest"
            echo "      docker push ${REGISTRY_LB_IP}:${REGISTRY_PORT}/myimage:latest"
            echo "Alias: ${REGISTRY_HOST_ALIAS} → ${REGISTRY_LB_IP}:${REGISTRY_PORT} (k3s registries.yaml on nodes)"
            exit 0
        fi
        sleep 3
    done
    echo "ERROR: registry not responding at ${REGISTRY_LB_IP}:${REGISTRY_PORT}" >&2
    kubectl get pods -n registry >&2
    exit 1

# Add MetalLB registry to Docker insecure-registries on ms02 (requires sudo).
registry-configure-host:
    #!/usr/bin/env bash
    set -euo pipefail
    source config/cluster.env
    sudo python3 tools/configure_docker_registry.py
    sudo systemctl restart docker
    echo "Docker restarted with insecure-registries for ${REGISTRY_LB_IP}:${REGISTRY_PORT}"

registry-smoke-push: registry-verify
    #!/usr/bin/env bash
    set -euo pipefail
    source config/cluster.env
    docker pull registry:2
    docker tag registry:2 "${REGISTRY_LB_IP}:${REGISTRY_PORT}/smoke/registry:2"
    docker push "${REGISTRY_LB_IP}:${REGISTRY_PORT}/smoke/registry:2"
    echo "OK: pushed smoke image to in-cluster registry"

# Platform manifests are Flux-owned under gitops/ — do not copy Kind/Tilt trees here.
migrate-platform-from-kind:
    @echo "REMOVED: platform is Flux-owned in shared-gitops-k8s-cluster (gitops/root/components)"

patch-loadbalancer-services:
    @echo "SKIP: MetalLB Services are Flux/inventory-owned — just check-metallb-inventory"

apply-loadbalancer-services:
    @echo "SKIP: do not kubectl-apply platform LBs from Day-0; Flux owns them"

patch-routellm-vllm:
    @echo "SKIP: routellm is Flux stack-cylon-infra"

routellm-verify-vllm: context
    #!/usr/bin/env bash
    set -euo pipefail
    source config/cluster.env
    source config/loadbalancer-ips.env 2>/dev/null || true
    # Envoy TCP :4000 → routellm ClusterIP (or HTTPRoute routellm.dev)
    base="http://${ROUTELLM_LB_IP:-${ENVOY_GATEWAY_LB_IP:-10.177.76.234}}:4000"
    model="${VLLM_DEFAULT_MODEL:-Qwen/Qwen3.6-35B-A3B-FP8}"
    vllm="${VLLM_API_BASE:-http://192.168.1.104:8000/v1}"
    echo "Checking vLLM direct: ${vllm}/models"
    curl -sf "${vllm}/models" >/dev/null
    echo "Checking routellm health: ${base}/health"
    curl -sf "${base}/health" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('healthy_count',0)>0, d"
    echo "Checking routellm chat -> vLLM (${model})..."
    resp="$(curl -sf --max-time 120 "${base}/v1/chat/completions" \
        -H 'Content-Type: application/json' \
        -d "{\"model\":\"${model}\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with the word OK only.\"}],\"max_tokens\":32}")"
    printf '%s' "${resp}" | python3 -c 'import json,sys; d=json.load(sys.stdin); m=d["choices"][0]["message"]; t=m.get("content") or m.get("reasoning_content") or ""; assert str(t).strip(), d; print("OK: routellm -> vLLM completion:", str(t).strip()[:120])'

patch-local-storage-pvs:
    @echo "SKIP: democratic-csi / Flux owns storage"

apply-infra-secrets:
    @echo "SKIP: infra secrets via Flux profile-config / SOPS (just secrets-apply)"

platform-kustomize-build:
    kubectl kustomize gitops/clusters/dev >/dev/null && echo "OK: gitops/clusters/dev kustomize build"

# Create VMs, fetch kubeconfig, install MetalLB + registry seed, mount workspace.
# Namespaces / postgres / redis / observability → Flux (`just bootstrap-dev`).
cluster-create: vm-create-workers vm-mount-workspace cluster-bootstrap
    @echo ""
    @echo "Day 0 complete (VMs + k3s + MetalLB/registry seed)."
    @echo "Next (GitOps):"
    @echo "  just bootstrap-dev"
    @echo "  just cluster-edge-apply"

cluster-delete: vm-delete
    rm -f kubeconfig/shared-k8s.yaml

cluster-recreate:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "WARNING: Destructive — deletes Multipass VMs and cluster state."
    just --justfile day0.justfile cluster-delete
    just --justfile day0.justfile cluster-create

# Namespaces are Flux-owned (gitops/root/components/namespaces).
apply-platform-namespaces: context
    @echo "SKIP: platform namespaces are Flux-owned — just bootstrap-dev / sync stacks"

status: context
    @kubectl get nodes -o wide
    @kubectl get ns data observability pipeline scheduling gcp cylon registry 2>/dev/null || kubectl get ns
    @kubectl get svc -n registry

# Callable from sibling repos (hauliage, cylon, BRRTRouter, …).
check-ready: context
    #!/usr/bin/env bash
    set -euo pipefail
    export KUBECONFIG="$(pwd)/kubeconfig/shared-k8s.yaml"
    if [[ ! -f "${KUBECONFIG}" ]]; then
        echo "[FAIL] shared-k8s kubeconfig missing — run: just cluster-create" >&2
        exit 1
    fi
    if ! kubectl get nodes --no-headers 2>/dev/null | grep -q Ready; then
        echo "[FAIL] shared-k8s cluster not ready — run: just infra-up" >&2
        exit 1
    fi
    echo "[OK] shared-k8s ready (context $(kubectl config current-context))"

# -----------------------------------------------------------------------------
# LAN proxy — Mac / 192.168.1.x → MetalLB (replaces Kind hostPorts on ms02)
# -----------------------------------------------------------------------------

lan-proxy-render:
    python3 tools/configure_lan_proxy.py render

lan-proxy-urls:
    python3 tools/configure_lan_proxy.py urls

lan-proxy-install:
    python3 tools/configure_lan_proxy.py install

lan-proxy-up:
    python3 tools/configure_lan_proxy.py up

lan-proxy-down:
    python3 tools/configure_lan_proxy.py down

lan-proxy-status:
    python3 tools/configure_lan_proxy.py status

lan-proxy-verify:
    python3 tools/configure_lan_proxy.py verify

# -----------------------------------------------------------------------------
# Remote Tilt (Mac editor → ms02 build/deploy → monitor)
# Tilt binds 0.0.0.0 on ms02 (see deploy/APPS.md). Trigger from Mac; logs/wait via
# ssh when Mac tilt CLI version ≠ ms02 (tilt logs timestamp parse bug v0.37 vs v0.36).
# -----------------------------------------------------------------------------

# Default ms02 LAN IP (override: MS02_LAN_IP=… just tilt-remote-trigger …)
_ms02_lan_ip := "192.168.1.189"

# Usage: just tilt-remote-trigger hauliage bff
tilt-remote-trigger app resource:
    #!/usr/bin/env bash
    set -euo pipefail
    host="${MS02_LAN_IP:-{{_ms02_lan_ip}}}"
    case "{{app}}" in
      hauliage) port=10352 ;;
      sesame|sesame-idam) port=10351 ;;
      platform|shared-k8s) port=10349 ;;
      brrtrouter) port=10353 ;;
      *) echo "Unknown app {{app}} (hauliage|sesame|platform|brrtrouter)" >&2; exit 1 ;;
    esac
    tilt trigger "{{resource}}" --host "$host" --port "$port"

# Usage: just tilt-remote-wait hauliage bff
tilt-remote-wait app resource timeout="300s":
    #!/usr/bin/env bash
    set -euo pipefail
    case "{{app}}" in
      hauliage) port=10352 ;;
      sesame|sesame-idam) port=10351 ;;
      platform|shared-k8s) port=10349 ;;
      brrtrouter) port=10353 ;;
      *) echo "Unknown app {{app}}" >&2; exit 1 ;;
    esac
    ssh ms02 "tilt wait --port ${port} --for=condition=Ready uiresource/{{resource}} --timeout={{timeout}}"

# Usage: just tilt-remote-logs hauliage bff   (Ctrl-C to stop follow)
tilt-remote-logs app resource tail="50":
    #!/usr/bin/env bash
    set -euo pipefail
    case "{{app}}" in
      hauliage) port=10352 ;;
      sesame|sesame-idam) port=10351 ;;
      platform|shared-k8s) port=10349 ;;
      brrtrouter) port=10353 ;;
      *) echo "Unknown app {{app}}" >&2; exit 1 ;;
    esac
    ssh ms02 "tilt logs {{resource}} --port ${port} --tail {{tail}} -f"

# Trigger + wait (edit → rebuild → ready gate)
tilt-remote-cycle app resource:
    just tilt-remote-trigger {{app}} {{resource}}
    just tilt-remote-wait {{app}} {{resource}}

# cert-manager dev TLS (*.dev.microscaler.local) — synced to ms02 haproxy :443
cert-manager-install:
    #!/usr/bin/env bash
    set -euo pipefail
    source config/cluster.env
    export KUBECONFIG="$(pwd)/kubeconfig/shared-k8s.yaml"
    kubectl config use-context "${K8S_CONTEXT}"
    CM_VER="v1.16.2"
    CM_MANIFEST="/tmp/cert-manager-${CM_VER}.yaml"
    curl -sfL "https://github.com/cert-manager/cert-manager/releases/download/${CM_VER}/cert-manager.yaml" -o "${CM_MANIFEST}"
    kubectl apply --validate=false -f "${CM_MANIFEST}"
    kubectl rollout status deployment/cert-manager -n cert-manager --timeout=180s
    kubectl rollout status deployment/cert-manager-webhook -n cert-manager --timeout=180s
    kubectl rollout status deployment/cert-manager-cainjector -n cert-manager --timeout=180s
    kubectl apply -k k8s/platform/dev-tls
    echo "Waiting for dev wildcard cert..."
    for i in $(seq 1 60); do
      if kubectl get secret dev-microscaler-local-tls -n cert-manager >/dev/null 2>&1; then
        echo "OK: secret dev-microscaler-local-tls ready"
        exit 0
      fi
      sleep 3
    done
    kubectl describe certificate dev-microscaler-local-wildcard -n cert-manager >&2 || true
    exit 1

dev-tls-sync:
    python3 tools/sync_haproxy_tls.py sync

dev-tls-export-ca:
    python3 tools/sync_haproxy_tls.py export-ca

# -----------------------------------------------------------------------------
# Split-horizon dev DNS — ms02 dnsmasq + Mac /etc/resolver + ms02 systemd-resolved
# -----------------------------------------------------------------------------

dev-dns-render:
    python3 tools/configure_dev_dns.py render

dev-dns-urls:
    python3 tools/configure_dev_dns.py urls

dev-dns-mac-install:
    python3 tools/configure_dev_dns.py mac-install

dev-dns-mac-resolver:
    python3 tools/configure_dev_dns.py mac-resolver

dev-dns-ms02-install:
    python3 tools/configure_dev_dns.py ms02-install

dev-dns-ms02-resolver:
    python3 tools/configure_dev_dns.py ms02-resolver

dev-dns-install:
    python3 tools/configure_dev_dns.py install

dev-dns-up:
    python3 tools/configure_dev_dns.py up

dev-dns-down:
    python3 tools/configure_dev_dns.py down

dev-dns-status:
    python3 tools/configure_dev_dns.py status

dev-dns-verify:
    python3 tools/configure_dev_dns.py verify

# Restart a single app Tilt unit after install-systemd or config change.
restart-tilt-hauliage:
    systemctl --user restart tilt-hauliage.service

restart-tilt-fleetingdns:
    systemctl --user restart tilt-fleetingdns.service

restart-tilt-sesame-idam:
    systemctl --user restart tilt-sesame-idam.service

restart-tilt-brrtrouter:
    systemctl --user restart tilt-brrtrouter.service

restart-tilt-lifeguard:
    systemctl --user restart tilt-lifeguard.service

restart-tilt-apps: restart-tilt-hauliage restart-tilt-fleetingdns restart-tilt-sesame-idam restart-tilt-brrtrouter restart-tilt-lifeguard

cluster-verify-workspace-mount:
    #!/usr/bin/env bash
    set -euo pipefail
    source config/cluster.env
    multipass exec k8s-worker-1 -- test -f "${WORKSPACE_GUEST}/cylon/Cargo.toml"
    echo "OK: Cylon checkout visible on k8s-worker-1"

# -----------------------------------------------------------------------------
# Platform Tilt retired — Flux owns platform. App Tilts are systemd user units.
# -----------------------------------------------------------------------------

tilt-up:
    @echo "REMOVED: platform Tilt (port 10349) is retired. Flux owns platform stacks."
    @echo "  App Tilts: systemctl --user start tilt-hauliage tilt-sesame-idam …"
    @echo "  Units:     just tilt-units-apply"

tilt-down:
    @echo "REMOVED: nothing to tilt-down for platform (Flux-owned)"

dev-up: cluster-create
    @echo "Day 0 done. Finish with: just bootstrap-dev && just cluster-edge-apply"

dev-down:
    @echo "Use: just cluster-delete (destructive) or stop app Tilts via systemctl --user"

# -----------------------------------------------------------------------------
# systemd — App Tilt units (Ansible in this repo)
# -----------------------------------------------------------------------------

install-systemd:
    just --justfile justfile tilt-units-apply

infra-up:
    #!/usr/bin/env bash
    set -euo pipefail
    systemctl --user start microscaler-shared-k8s-infra.service
    export KUBECONFIG="$(pwd)/kubeconfig/shared-k8s.yaml"
    for i in $(seq 1 90); do
        if kubectl get nodes --no-headers 2>/dev/null | grep -q Ready; then
            echo "shared-k8s cluster is ready."
            exit 0
        fi
        sleep 2
    done
    echo "WARNING: shared-k8s cluster did not become ready within 3 minutes" >&2
    exit 1

infra-down:
    #!/usr/bin/env bash
    set -euo pipefail
    deploy/cluster-stop.sh
    systemctl --user stop microscaler-shared-k8s-infra.service 2>/dev/null || true

systemd-tilt-up:
    #!/usr/bin/env bash
    set -euo pipefail
    systemctl --user start tilt-shared-k8s.service
    for i in $(seq 1 60); do
        if curl -sf http://localhost:10349/api/v1/info >/dev/null 2>&1; then
            echo "Tilt ready at http://0.0.0.0:10349"
            exit 0
        fi
        sleep 2
    done
    echo "WARNING: tilt-shared-k8s did not become ready within 2 minutes" >&2
    exit 1

systemd-tilt-down:
    systemctl --user stop tilt-shared-k8s.service || true

dev-up-systemd: infra-up systemd-tilt-up
