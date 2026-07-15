# Progress — shared-gitops-k8s-cluster

## 2026-07-15

- [x] Flux on Multipass `dev` + deploy key
- [x] Built gitopssets-controller from `~/Workspace/weaveworks/gitopssets-controller`
- [x] Pushed to `10.177.76.220:5000/weaveworks/gitopssets-controller:v0.17.2`
- [x] Mirrored kube-rbac-proxy to `10.177.76.220:5000/kubebuilder/kube-rbac-proxy:v0.16.0`
- [x] HelmRelease Ready; pod 2/2 Running
- [x] GitOpsSet `platform-stacks` Ready → generated `stack-namespaces` Ready

Refresh images: `just push-gitopssets-images` (builds from local weaveworks checkout).
