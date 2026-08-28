# Tooling consolidation — one CLI, one repo, disposable nodes

Status: ADOPTED 2026-08-28 · CLI: `msk8s` (tooling/, package `shared_gitops`)

## Why

Three symptoms, one disease (day-0 node state was mutable and hand-tended):

- ~1,100 lines of bash living inside `justfile` + `day0.justfile` bodies.
- Loose scripts in `tools/` duplicating/overlapping the `tooling/` package.
- Node config drift: k8s-worker-4 was created without the direct-mirror
  registries entry and every image pull on it failed
  ("HTTP response to HTTPS client", 2026-08-28). The bug was IN the
  cloud-init templates — every node was born broken and older ones had
  been hand-healed over SSH.

`shared-k8s-cluster` (the predecessor repo) is archived on GitHub; this
repo is the only home. Aether replaces the substrate when the blade
chassis lands — until then the interim goal is to make Multipass day-0
**boring and disposable**, which also rehearses the GitOps-driven VM
lifecycle Aether demands.

## Rules

1. **Logic lives in `tooling/src/shared_gitops/` (Python, testable).**
   just recipes are one-line shims calling `msk8s`. No new bash bodies.
2. **The cattle rule.** Never SSH-fix a node. `msk8s node replace NAME`
   is the fix for any drifted/broken node; Flux re-converges everything
   above day-0 automatically. `msk8s node doctor` detects drift.
3. **Strangler migration.** Each just recipe migrates when next touched:
   port its body into the package, leave a shim. `tools/*.py` become
   shims immediately when absorbed (see tools/render_cloud_init.py).
4. **Templates are the only birth certificate.** Node files (registries,
   firewall, mounts) change in `multipass/cloud-init-*.yaml` + a node
   replace — never on a live node.

## CLI surface (grows by strangling)

    msk8s node add|replace|delete NAME     # lifecycle (idempotent)
    msk8s node doctor                      # drift detection (read-only)
    msk8s cloud-init ROLE --output PATH    # template rendering
    msk8s inventory validate|metallb       # existing checks, one roof

## Migration backlog (order of touch)

- [x] cloud-init render (tools/render_cloud_init.py -> shared_gitops.cloud_init)
- [x] node add/replace/delete/doctor (day0 vm-create-workers/k3s-install-agent/vm-delete)
- [ ] cluster create/recreate/status/check-ready (day0)
- [ ] registry configure/verify/smoke (day0 + tools/configure_docker_registry.py)
- [ ] lan-proxy render/install/verify (justfile + tools/configure_lan_proxy.py + tools/sync_haproxy_tls.py)
- [ ] dev-dns render/install/verify (day0 + tools/configure_dev_dns.py)
- [ ] tilt systemd unit generation (project inventory -> units + haproxy vhosts + tilt-mcp entries)
- [ ] firewall (tools/lan_firewall.py)
- [ ] retire tools/ entirely (all shims deleted, package only)

## Config unification (second phase)

`config/*.env|yaml` (6 files) + `ansible/inventory` + `gitops/inventory`
collapse progressively into one `config/cluster-inventory.yaml` consumed
by msk8s generators. Each strangled recipe moves its knobs across.
