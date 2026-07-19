# Edge: MetalLB + haproxy + Envoy (slim)

## Target topology

```
Mac / LAN
  │
  ▼
haproxy 192.168.1.189
  ├─ *.dev.microscaler.local :80/:443
  │    ├─ tilt-*     → 127.0.0.1:<tilt-port>  ← ONLY outside Envoy
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
| **MetalLB** | Envoy VIP + remaining true-L4 Services | **Keep** |
| **haproxy** | LAN `*.dev` + L4 port bridge to Envoy VIP | **Keep thin** (Mac cannot reach `10.177.76.0/24` without a route) |
| **Envoy Gateway** | All HTTP UIs + L4 TCP/UDP into the cluster | GitOps manifests |

## What is GitOps

- `HTTPRoute` — browser UIs (`*.dev` except tilt)
- `TCPRoute` / `UDPRoute` — Postgres, Redis, MinIO S3, SMTP, OTel, registry, routellm API, resurrection hub, …
- `Gateway` listeners — HTTP/S + L4 ports

## What stays on haproxy (not Envoy)

| Host | Port | Why |
|---|---|---|
| `tilt-rerp.dev` | 10350 | Tilt is a **host** process on ms02 |
| `tilt-sesame.dev` | 10351 | same |
| `tilt-hauliage.dev` | 10352 | same |
| `tilt-brrtrouter.dev` | 10353 | same |
| `tilt-dcops.dev` | 10354 | same |
| `tilt-lifeguard.dev` | 10355 | same |
| `tilt-cylon.dev` | 10450 | same |
| `tilt-fleetingdns.dev` | 10654 | same |
| `tilt-aether.dev` | 10750 | same |
| `tilt-opengroupware.dev` | 10852 | same |

Source: `config/lan-http-vhosts.yaml` + `ansible/roles/tilt_user_units/defaults/main.yml`.

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

## Bridge / guest L4 (hit Envoy VIP directly)

| Port | Envoy listener | Backend | Replaces VIP |
|---|---|---|---|
| 4000 | tcp-routellm | `cylon/routellm:4000` | was `.221` |
| 14000 | tcp-resurrection | `cylon/resurrection-hub:14000` | was `.236` |

## Demoted UI MetalLBs (ClusterIP + HTTPRoute)

| Former VIP | Service | Hostname |
|---|---|---|
| `.227` | `opensearch-dashboards-lb` (removed) | `opensearch.dev` / `grafana.dev` |
| `.237` | `loadlinker/frontend` | `loadlinker.dev` / `hauliage.dev` |
| `.232` | `pact-broker` | `pact.dev` |
| `.221` | `routellm` | `routellm.dev` + Envoy TCP `:4000` |
| `.236` | `resurrection-hub` | `resurrection.dev` + Envoy TCP `:14000` |

If every Mac has `10.177.76.0/24 via 192.168.1.189`, DNS can point at Envoy VIP and haproxy L4 can shrink further.
