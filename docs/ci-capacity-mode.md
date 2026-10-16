# ms02 CI capacity mode (16 Oct 2026)

ms02's CPU goes to GitHub Actions. Only these run: Flux, ARC (controller, listener, scale set `microscaler`,
`dind-registry-proxy`) and what they need — the zot registry (runner image, MetalLB `.220`), MetalLB,
democratic-csi (zot's and the proxy's volumes), cert-manager, kube-system, platform-dev-tls and the Flux UI.

| What | How it is parked | Bring it back |
|------|------------------|---------------|
| Platform stacks: ai, cylon-infra, envoy-gateway, imgproxy, messaging, minio, mosquitto, observability, pact, pipeline, platform-openbao, postgres, postgres-backup, redis, scheduling | `parked` file in `gitops/clusters/dev/inventory/stacks/<name>/` → `suspend: true` (`just sync-stack-inventory dev`) | delete the file, sync, push; Flux reconciles |
| Products: pricewhisperer-core, sesame-idam-idam(-services), rerp-crm-services (hauliage-core and rerp-accounting were already suspended) | `suspend: true` in `gitops/inventory/product-components.yaml` | `suspend: false`, push |
| Workers k8s-worker-2..4 | `K8S_WORKERS` in `config/cluster.env`; cordoned and `multipass stop`ped (VMs and disks kept) | move back to `K8S_WORKERS`, `multipass start`, `kubectl uncordon` |

Suspending keeps every object and volume (zfs-iscsi is Retain) and stops Flux reconciling it; it does not scale
running pods down. On the live cluster the parked workloads were scaled to zero once (and the observability
DaemonSets given an unmatched nodeSelector, its provisioner and the postgres-backup CronJobs suspended); a cluster
built from this repo never starts them. `~/ms02-scale-restore-20261016.txt` on ms02 holds the replica counts from
before, for `kubectl scale` after a resume (or let the next Helm upgrade restore them).

Removing a parked stack from the inventory instead would prune it: Flux deletes its PVCs and the Retain volumes are
left Released, needing a manual rebind. Do not do that for a stack with data.
