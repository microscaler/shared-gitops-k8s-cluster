# Agent memory — observability log signal

Updated: 2026-07-18

## Status
- Epoll (`may::io::sys::select` / body `*epoll select*`) is **dropped** by OTEL `filter/drop-epoll-io` before OpenSearch (was ~99% of volume).
- Remaining runtime_noise (memory, may config, BRRTRouter lifecycle) stays tagged/selectable.
- Signal Lucene = `log.attributes.event_class:application`.
- Do not put `opensearchDashboards.defaultRoute` in helm values (OSD 2.19 rejects).
- Unrelated dirty: `gitops/root/components/platform/openbao/bootstrap.sh` — leave unstaged.
