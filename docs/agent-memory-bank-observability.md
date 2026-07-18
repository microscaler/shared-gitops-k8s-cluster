# Agent memory — observability log signal

Updated: 2026-07-18

## Status
- OTEL  drops may epoll select AND BRRTRouter Memory statistics before OpenSearch.
- Verified: last 2m after epoll-only drop had 0 epoll; remaining was memory+JWKS. Memory drop added next.
- Signal: .
- Unrelated dirty: openbao/bootstrap.sh — leave unstaged.
