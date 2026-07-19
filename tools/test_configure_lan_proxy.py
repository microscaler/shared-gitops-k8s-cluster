#!/usr/bin/env python3
"""Tests for configure_lan_proxy."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from configure_lan_proxy import load_env, load_http_vhosts, load_proxies, render_haproxy  # noqa: E402


class LanProxyRenderTest(unittest.TestCase):
    def test_l4_targets_envoy_vip(self) -> None:
        env = load_env()
        entries = load_proxies(env)
        self.assertTrue(entries)
        for e in entries:
            self.assertEqual(e.target_ip, env["ENVOY_GATEWAY_LB_IP"], e.name)

    def test_tilt_vhosts_and_envoy_default(self) -> None:
        env = load_env()
        vhosts, raw, default = load_http_vhosts(env)
        hosts = {v.host for v in vhosts}
        self.assertGreaterEqual(len(vhosts), 10)
        self.assertIn("tilt-sesame.dev.microscaler.local", hosts)
        self.assertIn("tilt-hauliage.dev.microscaler.local", hosts)
        self.assertIn("tilt-cylon.dev.microscaler.local", hosts)
        self.assertIn("tilt-opengroupware.dev.microscaler.local", hosts)
        self.assertIsNotNone(default)
        assert default is not None
        self.assertEqual(default.target_ip, env["ENVOY_GATEWAY_LB_IP"])
        cfg = render_haproxy(load_proxies(env), vhosts, raw, default)
        self.assertIn("default_backend http_envoy", cfg)
        self.assertIn(f"server envoy {env['ENVOY_GATEWAY_LB_IP']}:80", cfg)
        self.assertIn("server tilt 127.0.0.1:10351", cfg)

    def test_postgres_lan_port(self) -> None:
        env = load_env()
        postgres = next(e for e in load_proxies(env) if e.name == "postgres")
        self.assertEqual(postgres.lan_port, 5433)
        self.assertEqual(postgres.target_port, 5433)


if __name__ == "__main__":
    unittest.main()
