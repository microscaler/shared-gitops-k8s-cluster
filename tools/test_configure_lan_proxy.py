#!/usr/bin/env python3
"""Tests for configure_lan_proxy."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "tools"))

from configure_lan_proxy import ProxyEntry, load_env, load_proxies, render_haproxy  # noqa: E402


class LanProxyRenderTest(unittest.TestCase):
    def test_render_contains_grafana_frontend(self) -> None:
        env = load_env()
        entries = load_proxies(env)
        grafana = next(e for e in entries if e.name == "grafana")
        cfg = render_haproxy(entries, [], {})
        self.assertIn(f"bind {grafana.bind_ip}:3000", cfg)
        self.assertIn(f"server metallb {grafana.target_ip}:3000", cfg)

    def test_render_http_vhost_hauliage(self) -> None:
        from configure_lan_proxy import HttpVhost, load_http_vhosts

        env = load_env()
        vhosts, raw = load_http_vhosts(env)
        hauliage = next(v for v in vhosts if v.host == "hauliage.dev.microscaler.local")
        cfg = render_haproxy([], vhosts, raw)
        self.assertIn("frontend http_dev_vhosts", cfg)
        self.assertIn(f"bind {hauliage.bind_ip}:80", cfg)
        self.assertIn("hdr(host) -i hauliage.dev.microscaler.local", cfg)
        self.assertIn(f"server metallb {hauliage.target_ip}:8080", cfg)

    def test_postgres_lan_port_matches_kind(self) -> None:
        env = load_env()
        entries = load_proxies(env)
        postgres = next(e for e in entries if e.name == "postgres")
        self.assertEqual(postgres.lan_port, 5433)
        self.assertEqual(postgres.target_port, 5432)


if __name__ == "__main__":
    unittest.main()
