# Active Context

**Last updated:** 2026-07-16 — GitOpsSets audit migration complete on dev.

## GitOpsSets (live)

| Set | Role | Status |
|-----|------|--------|
| `platform-stacks` | Catalog + cluster enablement → `stack-*` KS with `dependsOn` | Ready (18) |
| `profile-config` | Matrix cluster×profile → `profile-config-*` (+ SOPS) | Ready (9) |
| `product-components` | ImageRepository/ImagePolicy from inventory | Ready (9) |

Catalog: `gitops/inventory/platform-stacks.yaml`  
Generated: `just sync-stack-inventory <id>` → `clusters/<id>/inventory/stacks.yaml`  
Profiles: `deployment-configuration/profiles/<env>/<component>/`

## Staging / prod

Do **not** enable GitOpsSets until static `stack-namespaces-ks.yaml` is removed from that cluster’s `control/` (name collision). See `gitops/deferred/gitopssets/README.md`.

## Next (backlog)

1. Helm `valuesFrom` for observability / postgres-ha / minio / redis knobs.
2. FreeRADIUS / Squid passwords → SOPS.
3. MetalLB annotation patches / LAN proxy sync (inventory check OK).
4. Add Matrix rows when staging/prod go live.
