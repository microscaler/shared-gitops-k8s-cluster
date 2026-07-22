# shared-gitops-k8s-cluster — Flux/kubectl on ms02; thin Ansible from Mac (or any controller)
set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

repo_root := justfile_directory()
day0_kubeconfig := repo_root + "/kubeconfig/shared-k8s.yaml"
ansible_dir := repo_root + "/ansible"

default:
	@just --list

# ── Day-0 host edge (thin Ansible — run ON ms02) ───────────────────────────
# Docs: docs/day0-host-edge-ansible.md
# From Mac: ssh ms02 'cd ~/Workspace/microscaler/shared-gitops-k8s-cluster && just cluster-edge-apply'
#
# Usage: just cluster-edge-apply
#         just cluster-edge-apply multipass_bridge
#         just cluster-edge-apply lan_proxy,k8s_api_lan
#         just cluster-edge-apply tilt_units

cluster-edge-apply *tags:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{ansible_dir}}"
	if [[ -n "{{tags}}" ]]; then
	  ansible-playbook playbooks/ms02_cluster_edge.yml --tags "{{tags}}"
	else
	  ansible-playbook playbooks/ms02_cluster_edge.yml
	fi

cluster-edge-check *tags:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{ansible_dir}}"
	if [[ -n "{{tags}}" ]]; then
	  ansible-playbook playbooks/ms02_cluster_edge.yml --check --diff --tags "{{tags}}"
	else
	  ansible-playbook playbooks/ms02_cluster_edge.yml --check --diff
	fi

# Install/refresh ~/.config/systemd/user/tilt-*.service
tilt-units-apply:
	just cluster-edge-apply tilt_units

# ── Day-0 Multipass/k3s (day0.justfile) ────────────────────────────────────
# VMs + kubeconfig + MetalLB/registry seed. Platform after that is Flux.

cluster-create:
	just --justfile day0.justfile --working-directory "{{repo_root}}" cluster-create

cluster-delete:
	just --justfile day0.justfile --working-directory "{{repo_root}}" cluster-delete

cluster-recreate:
	just --justfile day0.justfile --working-directory "{{repo_root}}" cluster-recreate

cluster-fetch-kubeconfig:
	just --justfile day0.justfile --working-directory "{{repo_root}}" cluster-fetch-kubeconfig

check-ready:
	just --justfile day0.justfile --working-directory "{{repo_root}}" check-ready

infra-up:
	just --justfile day0.justfile --working-directory "{{repo_root}}" infra-up

status:
	just --justfile day0.justfile --working-directory "{{repo_root}}" status

lan-proxy-up:
	just --justfile day0.justfile --working-directory "{{repo_root}}" lan-proxy-up

lan-proxy-down:
	just --justfile day0.justfile --working-directory "{{repo_root}}" lan-proxy-down

lan-proxy-status:
	just --justfile day0.justfile --working-directory "{{repo_root}}" lan-proxy-status

tilt-remote-trigger app resource:
	just --justfile day0.justfile --working-directory "{{repo_root}}" tilt-remote-trigger {{app}} {{resource}}

tilt-remote-wait app resource timeout="300s":
	just --justfile day0.justfile --working-directory "{{repo_root}}" tilt-remote-wait {{app}} {{resource}} {{timeout}}

tilt-remote-logs app resource tail="50":
	just --justfile day0.justfile --working-directory "{{repo_root}}" tilt-remote-logs {{app}} {{resource}} {{tail}}

tilt-remote-cycle app resource:
	just --justfile day0.justfile --working-directory "{{repo_root}}" tilt-remote-cycle {{app}} {{resource}}

restart-tilt-apps:
	just --justfile day0.justfile --working-directory "{{repo_root}}" restart-tilt-apps

# Dedicated Multipass nodes for ARC (labeled + tainted). See docs/gha-arc.md
vm-create-runners:
	just --justfile day0.justfile --working-directory "{{repo_root}}" vm-create-runners

# Build + push ARC runner image (gcc/pip/mold toolchain) to in-cluster registry.
arc_runner_version := "2.336.0"
# Bump -ciN when toolchain changes so IfNotPresent nodes pull the new digest.
arc_runner_tag := arc_runner_version + "-ci2"
arc_runner_image := "10.177.76.220:5000/microscaler/actions-runner:" + arc_runner_tag

arc-runner-image-build:
	#!/usr/bin/env bash
	set -euo pipefail
	source "{{repo_root}}/config/cluster.env"
	cd "{{repo_root}}/gitops/root/components/arc/runner-image"
	docker build \
	  --build-arg "RUNNER_VERSION={{arc_runner_version}}" \
	  -t "{{arc_runner_image}}" \
	  .
	# Prefer registry; if full, import into each ARC node’s containerd instead.
	if docker push "{{arc_runner_image}}"; then
	  echo "Pushed {{arc_runner_image}}"
	else
	  echo "WARN: registry push failed — importing into K8S_RUNNERS containerd"
	  mkdir -p "{{repo_root}}/.multipass"
	  TAR="{{repo_root}}/.multipass/actions-runner-ci.tar"
	  docker save -o "${TAR}" "{{arc_runner_image}}"
	  for runner in ${K8S_RUNNERS//,/ }; do
	    [[ -z "${runner}" ]] && continue
	    multipass transfer "${TAR}" "${runner}:/home/ubuntu/actions-runner-ci.tar"
	    multipass exec "${runner}" -- sudo k3s ctr -n k8s.io images import /home/ubuntu/actions-runner-ci.tar
	    multipass exec "${runner}" -- rm -f /home/ubuntu/actions-runner-ci.tar
	    echo "Imported on ${runner}"
	  done
	  rm -f "${TAR}"
	fi
	echo "Roll runners: just arc-runner-rollout"

# Recreate AutoscalingRunnerSet so pods pick up the image in runner-scale-set.yaml
arc-runner-rollout:
	#!/usr/bin/env bash
	set -euo pipefail
	export KUBECONFIG="${KUBECONFIG:-{{day0_kubeconfig}}}"
	kubectl -n arc-systems get autoscalinglistener -o name 2>/dev/null \
	  | while read -r n; do kubectl -n arc-systems patch "$n" -p '{"metadata":{"finalizers":[]}}' --type=merge; done
	kubectl -n arc-runners get autoscalingrunnerset,ephemeralrunnerset,ephemeralrunner -o name 2>/dev/null \
	  | while read -r n; do kubectl -n arc-runners patch "$n" -p '{"metadata":{"finalizers":[]}}' --type=merge 2>/dev/null || true; done
	kubectl -n arc-systems delete autoscalinglistener --all --wait=false --ignore-not-found
	kubectl -n arc-runners delete ephemeralrunner,ephemeralrunnerset,autoscalingrunnerset --all --wait=false --ignore-not-found
	sleep 3
	kubectl apply -f "{{repo_root}}/gitops/root/components/arc/runner-scale-set.yaml"
	echo "Waiting for a runner pod..."
	for i in $(seq 1 60); do
	  if kubectl -n arc-runners get pods --no-headers 2>/dev/null | grep -q Running; then
	    kubectl -n arc-runners get pods -o wide
	    exit 0
	  fi
	  sleep 5
	done
	kubectl -n arc-runners get pods -o wide || true
	exit 1

# Schema-check inventory YAML (+ generated stacks.yaml drift)
validate-inventory:
	cd {{repo_root}} && (test -x .venv/bin/python || python3 -m venv .venv)
	{{repo_root}}/.venv/bin/pip -q install pyyaml
	PYTHONPATH={{repo_root}}/tooling/src {{repo_root}}/.venv/bin/python {{repo_root}}/tooling/src/shared_gitops/validate_inventory.py

# Render gitops/clusters/<id>/inventory/stacks.yaml from catalog + enablement dirs
sync-stack-inventory cluster="dev":
	cd {{repo_root}} && (test -x .venv/bin/python || python3 -m venv .venv)
	{{repo_root}}/.venv/bin/pip -q install pyyaml
	PYTHONPATH={{repo_root}}/tooling/src {{repo_root}}/.venv/bin/python \
	  {{repo_root}}/tooling/src/shared_gitops/render_cluster_stacks.py {{cluster}}

# MetalLB inventory vs component annotation drift
check-metallb-inventory:
	cd {{repo_root}} && (test -x .venv/bin/python || python3 -m venv .venv)
	{{repo_root}}/.venv/bin/pip -q install pyyaml
	PYTHONPATH={{repo_root}}/tooling/src {{repo_root}}/.venv/bin/python \
	  {{repo_root}}/tooling/src/shared_gitops/check_metallb_inventory.py

# Validate product inventory and the GitOpsSet against the installed CRD.
validate-product-components:
	#!/usr/bin/env bash
	set -euo pipefail
	export KUBECONFIG="${KUBECONFIG:-{{day0_kubeconfig}}}"
	just validate-inventory
	kubectl config current-context | grep -q shared-k8s
	kubectl apply --dry-run=server \
	  -f {{repo_root}}/gitops/root/gitopssets/product-components.yaml

# Build cluster entrypoint (no cluster required)
build-dev:
	kubectl kustomize {{repo_root}}/gitops/clusters/dev

build-dev-control:
	kubectl kustomize {{repo_root}}/gitops/clusters/dev/control

build-namespaces:
	kubectl kustomize {{repo_root}}/gitops/root/components/namespaces

# Apply Flux bootstrap to Multipass shared-k8s (Day 0 must already exist)
bootstrap-dev:
	#!/usr/bin/env bash
	set -euo pipefail
	export KUBECONFIG="${KUBECONFIG:-{{day0_kubeconfig}}}"
	kubectl config current-context | grep -q shared-k8s || {
	  echo "ERROR: expected context shared-k8s (KUBECONFIG=$KUBECONFIG)" >&2
	  exit 1
	}
	just validate-inventory
	# Flux CRDs and CRs cannot land in one shot — apply twice with a CRD wait.
	kubectl apply -k {{repo_root}}/gitops/clusters/dev || true
	kubectl wait --for=condition=Established crd/gitrepositories.source.toolkit.fluxcd.io --timeout=120s
	kubectl wait --for=condition=Established crd/kustomizations.kustomize.toolkit.fluxcd.io --timeout=120s
	kubectl apply -k {{repo_root}}/gitops/clusters/dev
	echo "Bootstrap applied. Ensure secret flux-system/gitops-auth exists + GitHub deploy key, then: flux get all -A"

# Re-export Flux install (pins a new version directory manually)
flux-export version="2.9.2":
	#!/usr/bin/env bash
	set -euo pipefail
	outdir={{repo_root}}/gitops/root/flux/v{{version}}
	mkdir -p "$outdir"
	flux install --components-extra="image-reflector-controller,image-automation-controller" --export \
	  | python3 -c "
	import sys, re
	raw = sys.stdin.read()
	docs = re.split(r'(?m)^---\s*$', raw)
	kept = []
	for d in docs:
	    d = d.strip()
	    if not d: continue
	    if re.search(r'(?m)^kind:\s*Namespace\s*$', d) and re.search(r'(?m)^  name:\s*flux-system\s*$', d):
	        continue
	    kept.append(d)
	print('---')
	print('\n---\n'.join(kept))
	" > "$outdir/flux-install.yaml"
	printf '%s\n' 'apiVersion: kustomize.config.k8s.io/v1beta1' 'kind: Kustomization' 'resources:' '  - flux-install.yaml' > "$outdir/kustomization.yaml"
	echo "Wrote $outdir/flux-install.yaml"

# Create git credentials secret (interactive / CI). Example SSH:
#   just create-git-secret keyfile=~/.ssh/flux_deploy_key
create-git-secret keyfile:
	#!/usr/bin/env bash
	set -euo pipefail
	export KUBECONFIG="${KUBECONFIG:-{{day0_kubeconfig}}}"
	kubectl -n flux-system create secret generic gitops-auth \
	  --from-file=identity={{keyfile}} \
	  --from-file=identity.pub={{keyfile}}.pub \
	  --from-literal=known_hosts="$(ssh-keyscan -t ed25519,rsa github.com 2>/dev/null)" \
	--dry-run=client -o yaml | kubectl apply -f -

# Build gitopssets-controller from local checkout and push to ms02 registry.
# Source: ~/Workspace/weaveworks/gitopssets-controller
push-gitopssets-images registry="10.177.76.220:5000" version="v0.17.2":
	#!/usr/bin/env bash
	set -euo pipefail
	REG="{{registry}}"
	VERSION="{{version}}"
	SRC="${GITOPSSETS_SRC:-$HOME/Workspace/weaveworks/gitopssets-controller}"
	IMG="$REG/weaveworks/gitopssets-controller:$VERSION"
	PROXY_SRC=registry.k8s.io/kubebuilder/kube-rbac-proxy:v0.16.0
	PROXY_DST="$REG/kubebuilder/kube-rbac-proxy:v0.16.0"
	cd "$SRC"
	make docker-build IMG="$IMG" VERSION="$VERSION"
	make docker-push IMG="$IMG"
	DESC=$(git describe --tags --always)
	docker tag "$IMG" "$REG/weaveworks/gitopssets-controller:$DESC"
	docker push "$REG/weaveworks/gitopssets-controller:$DESC"
	docker pull "$PROXY_SRC"
	docker tag "$PROXY_SRC" "$PROXY_DST"
	docker push "$PROXY_DST"
	echo "Pushed $IMG (+ $DESC) and $PROXY_DST"

# Trigger an immediate postgres → MinIO dump (from CronJob template)
postgres-backup-now:
	#!/usr/bin/env bash
	set -euo pipefail
	export KUBECONFIG="${KUBECONFIG:-{{day0_kubeconfig}}}"
	NAME="postgres-backup-manual-$(date -u +%Y%m%d%H%M%S)"
	kubectl -n data create job "$NAME" --from=cronjob/postgres-backup
	kubectl -n data wait --for=condition=complete "job/$NAME" --timeout=600s
	kubectl -n data logs "job/$NAME" -c dump
	kubectl -n data logs "job/$NAME" -c upload

# Download the latest backup and restore it into a disposable local Postgres.
# This never connects the restore stream to the live cluster database.
postgres-backup-restore-drill database="rerp":
	#!/usr/bin/env bash
	set -euo pipefail
	export KUBECONFIG="${KUBECONFIG:-{{day0_kubeconfig}}}"
	PYTHONPATH={{repo_root}}/tooling/src python3 \
	  {{repo_root}}/tooling/src/shared_gitops/postgres_restore_drill.py \
	  --kubeconfig "$KUBECONFIG" --database "{{database}}"

# Reconcile OpenSearch retention, dashboard assets, and alert monitors now.
observability-provision-now:
	#!/usr/bin/env bash
	set -euo pipefail
	export KUBECONFIG="${KUBECONFIG:-{{day0_kubeconfig}}}"
	NAME="observability-provisioner-manual-$(date -u +%Y%m%d%H%M%S)"
	kubectl -n observability create job "$NAME" --from=cronjob/observability-provisioner
	kubectl -n observability wait --for=condition=complete "job/$NAME" --timeout=300s
	kubectl -n observability logs "job/$NAME"

# Heal stuck Terminating MinIO PVC/PV (Retain hostPath kept on disk), then apply Flux component
heal-minio-pvc:
	#!/usr/bin/env bash
	set -euo pipefail
	export KUBECONFIG="${KUBECONFIG:-{{day0_kubeconfig}}}"
	kubectl -n data scale deploy/minio deploy/imgproxy --replicas=0 || true
	kubectl -n data wait --for=delete pod -l app=minio --timeout=120s || true
	kubectl -n data wait --for=delete pod -l app=imgproxy --timeout=120s || true
	kubectl -n data patch pvc minio-storage -p '{"metadata":{"finalizers":null}}' --type=merge || true
	kubectl patch pv minio-pv -p '{"metadata":{"finalizers":null}}' --type=merge || true
	sleep 2
	kubectl apply -k {{repo_root}}/gitops/root/components/minio
	kubectl -n data rollout status deploy/minio --timeout=180s
	kubectl -n data scale deploy/imgproxy --replicas=1 || true
	echo "MinIO healed. HostPath /var/lib/data/minio on k8s-worker-1 retained."

# --- SOPS deployment-configuration (canonical secrets; SMC-aligned) ---
# Age key on ms02: ~/.config/sops/age/flux-shared-gitops
# Docs: deployment-configuration/README.md
# Path: deployment-configuration/profiles/<env>/<component>/

sops_age_key := env_var_or_default("SOPS_AGE_KEY_FILE", home_directory() + "/.config/sops/age/flux-shared-gitops")
profiles_root := repo_root + "/deployment-configuration/profiles"

# Ensure flux-system/sops-age exists from the ms02 age private key
secrets-ensure-age-key:
	#!/usr/bin/env bash
	set -euo pipefail
	export KUBECONFIG="${KUBECONFIG:-{{day0_kubeconfig}}}"
	KEY="{{sops_age_key}}"
	test -f "$KEY" || { echo "missing age key: $KEY (run age-keygen -o $KEY)" >&2; exit 1; }
	kubectl -n flux-system create secret generic sops-age \
	  --from-file=age.agekey="$KEY" \
	  --dry-run=client -o yaml | kubectl apply -f -
	kubectl -n flux-system get secret sops-age

# Encrypt plaintext dotenv → deployment-configuration/profiles/<env>/<component>/application.secrets.env
# Write to the final path first so .sops.yaml path_regex matches (stdout encrypt uses /tmp path).
secrets-encrypt env component plain:
	#!/usr/bin/env bash
	set -euo pipefail
	export SOPS_AGE_KEY_FILE="{{sops_age_key}}"
	DEST="{{profiles_root}}/{{env}}/{{component}}"
	mkdir -p "$DEST"
	test -f "{{plain}}" || { echo "missing plaintext: {{plain}}" >&2; exit 1; }
	cp "{{plain}}" "$DEST/application.secrets.env"
	sops --encrypt --in-place --input-type dotenv --output-type dotenv \
	  "$DEST/application.secrets.env"
	echo "Wrote $DEST/application.secrets.env"
	echo "Next: just secrets-apply {{env}} {{component}}  # or wait for Flux profile-secrets"

# Decrypt canonical profile dotenv to stdout (keys+values — use carefully)
secrets-decrypt env component:
	#!/usr/bin/env bash
	set -euo pipefail
	export SOPS_AGE_KEY_FILE="{{sops_age_key}}"
	sops -d "{{profiles_root}}/{{env}}/{{component}}/application.secrets.env"

# Verify canonical profile path (no gitops mirrors — Flux path is deployment-configuration/)
secrets-sync env component:
	#!/usr/bin/env bash
	set -euo pipefail
	SRC_DIR="{{profiles_root}}/{{env}}/{{component}}"
	test -d "$SRC_DIR" || { echo "missing $SRC_DIR" >&2; exit 1; }
	test -f "$SRC_DIR/kustomization.yaml" || { echo "missing $SRC_DIR/kustomization.yaml" >&2; exit 1; }
	echo "OK canonical profile: $SRC_DIR"
	echo "Flux applies via profile-config-{{component}} (path ./deployment-configuration/profiles/{{env}}/{{component}})"

# Apply profile kustomization (bootstrap ConfigMaps + Secrets before Flux)
secrets-apply env component:
	#!/usr/bin/env bash
	set -euo pipefail
	export KUBECONFIG="${KUBECONFIG:-{{day0_kubeconfig}}}"
	export SOPS_AGE_KEY_FILE="{{sops_age_key}}"
	PROFILE="{{profiles_root}}/{{env}}/{{component}}"
	test -f "$PROFILE/kustomization.yaml" || { echo "missing $PROFILE/kustomization.yaml" >&2; exit 1; }
	# kustomize cannot read ENC[] — decrypt secrets into a temp overlay
	TMP=$(mktemp -d)
	trap 'rm -rf "$TMP"' EXIT
	cp "$PROFILE/kustomization.yaml" "$TMP/"
	if [ -f "$PROFILE/application.properties" ]; then
	  cp "$PROFILE/application.properties" "$TMP/"
	fi
	shopt -s nullglob
	# Non-secret overlays referenced by configMapGenerator (helm-values*.yaml, etc.)
	for f in "$PROFILE"/*.yaml "$PROFILE"/*.yml "$PROFILE"/*.properties; do
	  base="$(basename "$f")"
	  case "$base" in
	    kustomization.yaml|*.secret.yaml) continue ;;
	  esac
	  cp "$f" "$TMP/"
	done
	for f in "$PROFILE"/*.secrets.env; do
	  sops -d "$f" > "$TMP/$(basename "$f")"
	done
	for f in "$PROFILE"/*.secret.yaml; do
	  sops -d "$f" > "$TMP/$(basename "$f")"
	done
	kubectl apply -k "$TMP"
	echo "Applied profile profiles/{{env}}/{{component}}"

# Heal Terminating Retain hostPath PVC/PV for mailpit or pact-postgres
heal-hostpath-pvc name:
	#!/usr/bin/env bash
	set -euo pipefail
	export KUBECONFIG="${KUBECONFIG:-{{day0_kubeconfig}}}"
	case "{{name}}" in
	  mailpit)
	    DEPLOY=mailpit; PVC=mailpit-storage-pv-claim; PV=mailpit-pv; COMP=messaging ;;
	  pact)
	    DEPLOY=pact-postgres; PVC=pact-postgres-data; PV=pact-postgres-pv; COMP=pact ;;
	  *) echo "usage: just heal-hostpath-pvc mailpit|pact" >&2; exit 1 ;;
	esac
	kubectl -n data scale "deploy/$DEPLOY" --replicas=0 || true
	kubectl -n data wait --for=delete pod -l "app=$DEPLOY" --timeout=120s || true
	kubectl -n data patch "pvc/$PVC" -p '{"metadata":{"finalizers":null}}' --type=merge || true
	kubectl patch "pv/$PV" -p '{"metadata":{"finalizers":null}}' --type=merge || true
	sleep 2
	kubectl apply -k "{{repo_root}}/gitops/root/components/$COMP"
	kubectl -n data scale "deploy/$DEPLOY" --replicas=1 || true
	kubectl -n data rollout status "deploy/$DEPLOY" --timeout=180s
	echo "Healed {{name}} (Retain hostPath)."
