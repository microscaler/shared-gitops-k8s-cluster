# Agent memory — observability log signal

Updated: 2026-07-18

## Status
- Commits:  (noise categories),  (remove OSD defaultRoute CrashLoop), / (docs), Signal Lucene simplified to .
- OTEL tags live: epoll_io, runtime_metrics, runtime_config, framework_lifecycle → event_class:runtime_noise.
- Discover: Open **Logs / Signal** (no epoll); **Logs / Runtime noise** to select trash.
- Do not put  in helm values (OSD 2.19 rejects).
- Unrelated dirty: >> Waiting for OpenBao pod to be Running...
pod/openbao-0 condition met
>> Initialising (1 key share, threshold 1 — dev only)... — leave unstaged.

## UI verify
- Signal simple query shows JWKS / application hits; epoll excluded.
