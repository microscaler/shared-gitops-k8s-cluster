# Agent memory — observability log signal

Updated: 2026-07-18

## Status
- Epoll + memory dropped at collector; health-probe Request logs dropped.
- Request completed/received kept (DEBUG exception) with method/path/duration; tagged `event_category:http`.
- `time_unix_nano` repaired from observed time (no more 1970 in detail).
- `log.attributes.message` copied from body for clearer detail labeling.
- BRRTRouter `d0b931a` promotes Request completed to INFO + status (needs service rebuild/rollout to take effect in images).
- Discover Signal columns include method/path/status/duration_ms.

## Detail view tip
Expand row → Table/JSON. Look for `body` / `log.attributes.message` plus `log.attributes.method|path|status|duration_ms`.
