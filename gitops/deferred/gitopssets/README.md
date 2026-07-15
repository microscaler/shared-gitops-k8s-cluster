# Deferred / optional GitOpsSets artifacts
#
# Active path (with ms02 registry mirrors):
#   gitops/root/controllers/gitopssets/
#   gitops/root/gitopssets/
#   gitops/clusters/dev/control/{gitopssets-controller,platform-gitopssets}-ks.yaml
#
# Refresh images:
#   just push-gitopssets-images
#
# Plain-Flux fallback (no GitOpsSets): point clusters/*/control at stack-namespaces-ks.yaml
