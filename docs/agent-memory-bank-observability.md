# Agent memory — observability log signal

Updated: 2026-07-18

## Status
- HEAD includes noise categories, OSD CrashLoop fix (no defaultRoute), Signal Lucene = `log.attributes.event_class:application`.
- OTEL tags live: `epoll_io`, `runtime_metrics`, `runtime_config`, `framework_lifecycle` under `event_class:runtime_noise`.
- Discover: Open **Logs / Signal** (no epoll); **Logs / Runtime noise** to select trash.
- Do not put `opensearchDashboards.defaultRoute` in helm values (OSD 2.19 rejects).
- Unrelated dirty: `gitops/root/components/platform/openbao/bootstrap.sh` — leave unstaged.

## UI verify
- Signal shows JWKS / application hits; epoll excluded.
