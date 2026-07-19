#!/usr/bin/env python3
"""Tests for configure_lan_proxy."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from configure_lan_proxy import ProxyEntry, load_env, load_http_vhosts, load_proxies, render_haproxy  # noqa: E402


class LanProxyRenderTest(unittest.TestCase):
    def test_render_contains_opensearch_dashboards(self) -> None:
        env = load_env()
        entries = load_proxies(env)
        osd = next(e for e in entries if e.name == "opensearch-dashboards")
        cfg = render_haproxy(entries, [], {})
        self.assertIn(f"bind {osd.bind_ip}:5601", cfg)
        self.assertIn(f"server metallb {osd.target_ip}:5601", cfg)

    def test_render_contains_kubernetes_api(self) -> None:
        env = load_env()
        entries = load_proxies(env)
        api = next(e for e in entries if e.name == "k8s-api")
        self.assertEqual(api.lan_port, 6443)
        self.assertEqual(api.target_port, 6443)

    def test_render_envoy_edge_passthrough(self) -> None:
        env = load_env()
        entries = load_proxies(env)
        http = next(e for e in entries if e.name == "envoy-http")
        https = next(e for e in entries if e.name == "envoy-https")
        self.assertEqual(http.lan_port, 80)
        self.assertEqual(https.lan_port, 443)
        self.assertEqual(http.target_ip, env["ENVOY_GATEWAY_LB_IP"])
        cfg = render_haproxy(entries, [], {})
        self.assertIn(f"bind {http.bind_ip}:80", cfg)
        self.assertIn(f"server metallb {http.target_ip}:80", cfg)
        self.assertIn(f"server metallb {https.target_ip}:443", cfg)

    def test_http_vhosts_retired_empty(self) -> None:
        env = load_env()
        vhosts, raw = load_http_vhosts(env)
        self.assertEqual(vhosts, [])
        self.assertEqual(raw.get("vhosts"), [])

    def test_postgres_lan_port_matches_kind(self) -> None:
        env = load_env()
        entries = load_proxies(env)
        postgres = next(e for e in entries if e.name == "postgres")
        self.assertEqual(postgres.lan_port, 5433)
        self.assertEqual(postgres.target_port, 5432)


if __name__ == "__main__":
    unittest.main()
