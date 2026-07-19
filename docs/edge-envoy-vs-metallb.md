# Edge: MetalLB + haproxy + Envoy (slim)

## Target topology

```
Mac / LAN
  │
  ▼
haproxy 192.168.1.189
  ├─ *.dev.microscaler.local :80/:443
  │    ├─ tilt-*     → 127.0.0.1:10351/10352   ← ONLY outside Envoy
  │    └─ everything → Envoy :80               ← HTTPRoute GitOps
  └─ L4 ports (:5433, :6390, …)
       └─ Envoy VIP :sameport                  ← TCPRoute/UDPRoute GitOps
              │
              ▼
         MetalLB 10.177.76.234 (Envoy)
              │
              ▼
         cluster Services
```

| Piece | Owns | Removable? |
|---|---|---|
| **MetalLB** | Envoy VIP (and optional leftover per-app LBs) | **Keep** for Envoy VIP |
| **haproxy** | LAN `*.dev` + L4 port bridge to Envoy VIP | **Keep thin** (Mac cannot reach `10.177.76.0/24` without a route) |
| **Envoy Gateway** | All HTTP UIs + all L4 TCP/UDP into the cluster | GitOps manifests |

## What is GitOps

- `HTTPRoute` — browser UIs (`*.dev` except tilt)
- `TCPRoute` / `UDPRoute` — Postgres, Redis, MinIO S3, SMTP, OTel, registry, …
- `Gateway` listeners — HTTP/S + L4 ports

## What stays on haproxy (not Envoy)

| Host / port | Why |
|---|---|
| `tilt-sesame.dev` / `tilt-hauliage.dev` | Tilt is a **host** process on ms02; Multipass pods cannot reach it without bridge firewall hacks. Keep local. |

## L4 port map (Mac → haproxy → Envoy → Service)

| LAN port | Envoy listener | Backend |
|---|---|---|
| 6443 | tcp-k8s-api | CP `10.177.76.137:6443` |
| 5433 | tcp-postgres | `data/postgres:5432` |
| 6390 | tcp-redis | `data/redis:6379` |
| 9000 | tcp-minio | `data/minio:9000` |
| 1025 | tcp-mailpit-smtp | `data/mailpit:1025` |
| 7419 | tcp-faktory | `scheduling/faktory-server:7419` |
| 4317 / 4318 | tcp-otel-* | `observability/otel-collector` |
| 5001 | tcp-registry | `registry/registry:5000` |
| 3128 | tcp-squid | `cylon/squid-proxy:3128` |
| 9003 | tcp-fluvio-sc | `pipeline/fluvio-sc-public:9003` |
| 1812 / 1813 UDP | udp-radius-* | Envoy VIP directly (mpqemubr0 route) |

## Later cleanup (optional)

UI MetalLBs still allocated but unused for browser entry (hostname = Envoy). Demote to ClusterIP when no script hits the VIP:

| VIP | Service | Prefer |
|---|---|---|
| `.227` | `opensearch-dashboards-lb` | `opensearch.dev` |
| `.237` | `loadlinker/frontend` | `loadlinker.dev` |
| `.232` | `pact-broker` | `pact.dev` |
| `.221` | `routellm` | `routellm.dev` (check `day0.justfile` first) |
| `.236` | `resurrection-hub` | `resurrection.dev` |

Also: sibling disk tree `shared-k8s-cluster/` if empty of unique state; hauliage `k8s/frontend/ingress.yaml` (inert on Multipass).

If every Mac has `10.177.76.0/24 via 192.168.1.189`, DNS can point at Envoy VIP and haproxy L4 can shrink further.
