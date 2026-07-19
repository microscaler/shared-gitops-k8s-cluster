# envoy-gateway — `*.dev.microscaler.local` edge

Host routing for Mac/LAN traffic is **GitOps HTTPRoute**, not `config/lan-http-vhosts.yaml`.

```
Mac → 192.168.1.189:80/443 (haproxy TCP) → MetalLB 10.177.76.234 (Envoy) → Service
```

## GitOps annotations

| Annotation | Where | Meaning |
|---|---|---|
| `gitops.microscaler.io/edge: "*.dev.microscaler.local"` | Gateway / EnvoyProxy / HelmRelease | Shared edge identity |
| `gitops.microscaler.io/hostname: <host>` | HTTPRoute (+ optional Service) | Hostname this route owns |
| `gitops.microscaler.io/gateway: microscaler-dev` | HTTPRoute | Parent Gateway name |
| `metallb.universe.tf/loadBalancerIPs` | EnvoyProxy → Envoy Service | Fixed VIP `.234` |

Wiring is the **HTTPRoute** CR. Annotations are discoverability / ownership signals — Envoy Gateway does not route from Service annotations alone.

## Add a host

1. Ensure the backend Service exists (ClusterIP or LB).
2. Add an `HTTPRoute` under `httproutes/` (or in the owning app stack) with:
   - `annotations.gitops.microscaler.io/hostname`
   - `parentRefs` → `envoy-gateway-system/microscaler-dev`
   - `hostnames` + `backendRefs`
3. Commit; Flux reconciles. No lan-proxy vhost edit.

## Enable (dev)

```bash
mkdir -p gitops/clusters/dev/inventory/stacks/envoy-gateway
touch gitops/clusters/dev/inventory/stacks/envoy-gateway/.gitkeep
just sync-stack-inventory dev
# commit + push stacks.yaml + this component
```

Depends on `namespaces` + `platform-dev-tls` (wildcard Secret `cert-manager/dev-microscaler-local-tls`).
