# shared-gitops-k8s-cluster — run on ms02
set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

repo_root := justfile_directory()
day0_kubeconfig := repo_root + "/../shared-k8s-cluster/kubeconfig/shared-k8s.yaml"

default:
	@just --list

# Schema-check inventory YAML
validate-inventory:
	cd {{repo_root}} && (test -x .venv/bin/python || python3 -m venv .venv)
	{{repo_root}}/.venv/bin/pip -q install pyyaml
	{{repo_root}}/.venv/bin/python {{repo_root}}/tooling/src/shared_gitops/validate_inventory.py

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
