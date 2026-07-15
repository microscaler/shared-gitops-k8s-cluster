# Progress — shared-gitops-k8s-cluster

## 2026-07-15

- [x] Scaffold + push to github.com/microscaler/shared-gitops-k8s-cluster
- [x] Flux controllers running on Multipass `shared-k8s` (dev)
- [x] `gitops-auth` secret created (ed25519 deploy key on ms02)
- [ ] **BLOCKED:** add deploy key to GitHub repo (read-only)
- [ ] cluster-control Ready → gitopssets → stack-namespaces
- [ ] Migrate remaining platform stacks

### Deploy key (public) — add at
https://github.com/microscaler/shared-gitops-k8s-cluster/settings/keys

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILAkivXyOXteK2SUBC96N1cF5GccisMm/+DSvy27Abdm flux@shared-gitops-k8s-cluster
```

Title: `flux@shared-gitops-k8s-cluster` — **Allow write** unchecked (read-only).
