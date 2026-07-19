# envoy-gateway — cluster edge (HTTP + TCP/UDP)

See [`docs/edge-envoy-vs-metallb.md`](../../../../docs/edge-envoy-vs-metallb.md).

```
Mac → haproxy 192.168.1.189
        ├─ *.dev (Tilt → localhost; else → Envoy :80)     HTTPRoute
        └─ L4 ports → Envoy VIP :sameport                 TCPRoute / UDPRoute
```

**Tilt is the only traffic that does not enter Envoy** (`config/lan-http-vhosts.yaml`).

## GitOps annotations

| Annotation | Where | Meaning |
|---|---|---|
| `gitops.microscaler.io/edge: "*.dev.microscaler.local"` | Gateway / EnvoyProxy / HelmRelease | Shared edge identity |
| `gitops.microscaler.io/hostname: <host>` | HTTPRoute (+ optional Service) | Hostname this route owns |
| `gitops.microscaler.io/gateway: microscaler-dev` | HTTPRoute | Parent Gateway name |
| `metallb.universe.tf/loadBalancerIPs` | EnvoyProxy → Envoy Service | Fixed VIP `.234` |

Wiring is the **HTTPRoute** CR. Annotations are discoverability / ownership signals.

**Envoy Gateway does not attach `networking.k8s.io/Ingress` via annotations** (unlike
nginx-ingress `kubernetes.io/ingress.class`). Prefer HTTPRoute in the product repo
(example: `hauliage/k8s/frontend/httproute.yaml`). A bare Ingress without a
controller stays inert (ADDRESS empty, Host → Envoy 404).

## Add a host

1. Ensure the backend Service exists (ClusterIP or LB).
2. Add an `HTTPRoute` in the **owning app** (preferred) or under `httproutes/` with:
   - `annotations.gitops.microscaler.io/hostname`
   - `annotations.gitops.microscaler.io/gateway: microscaler-dev`
   - `parentRefs` → `envoy-gateway-system/microscaler-dev` (`http` + `https`)
   - `hostnames` + `backendRefs`
3. Optional: mirror the same annotations on the Service for discovery.
4. Commit; Flux/Tilt reconciles. No lan-proxy vhost edit.

## Known DNS extras without routes yet

`dev-dns.yaml` lists `sesame-idam` and `cylon` — those resolve to the LAN edge but
return **404** until a product HTTPRoute exists (no single UI Service today).

## Enable (dev)

```bash
mkdir -p gitops/clusters/dev/inventory/stacks/envoy-gateway
touch gitops/clusters/dev/inventory/stacks/envoy-gateway/.gitkeep
just sync-stack-inventory dev
# commit + push stacks.yaml + this component
```

Depends on `namespaces` + `platform-dev-tls` (wildcard Secret `cert-manager/dev-microscaler-local-tls`).
