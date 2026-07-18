# Agent memory — observability log signal

Updated: 2026-07-18

## Status
- OTEL `filter/drop-epoll-io` drops may epoll select AND BRRTRouter Memory statistics before OpenSearch.
- Verified last 60s: only JWKS (auth); epoll=0, memory=0.
- Signal query: `log.attributes.event_class:application`.
- Unrelated dirty: `gitops/root/components/platform/openbao/bootstrap.sh` — leave unstaged.
