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
	kubectl apply -k {{repo_root}}/gitops/clusters/dev
	echo "Bootstrap applied. Ensure secret flux-system/gitops-auth exists, then: flux get all -A"

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
