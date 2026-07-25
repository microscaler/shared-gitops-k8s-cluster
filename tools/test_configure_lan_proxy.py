#!/usr/bin/env python3
"""Tests for configure_lan_proxy."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from configure_lan_proxy import (  # noqa: E402
    _tls_pem_files,
    _tls_pem_ready,
    load_env,
    load_http_vhosts,
    load_proxies,
    render_haproxy,
)


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


class TlsPemReadyTest(unittest.TestCase):
    """`tls.certificates` is a list — one pem per LAN DNS zone, selected by SNI."""

    def test_config_lists_every_zone_pem(self) -> None:
        _vhosts, raw, _default = load_http_vhosts(load_env())
        pems = _tls_pem_files(raw.get("tls") or {})
        self.assertIn("dev.microscaler.local.pem", pems)
        self.assertIn("sesameidentity.dev.local.pem", pems)

    def test_ready_when_any_single_pem_exists(self) -> None:
        # haproxy binds the whole dir, so one synced zone is enough to emit https_dev;
        # a zone still waiting on cert-manager must not hold the others on plaintext.
        with tempfile.TemporaryDirectory() as tmp:
            raw = {
                "tls": {
                    "sync_dir": tmp,
                    "certificates": [
                        {"secret_name": "a-tls", "pem_file": "a.pem"},
                        {"secret_name": "b-tls", "pem_file": "b.pem"},
                    ],
                }
            }
            self.assertFalse(_tls_pem_ready(raw))
            (Path(tmp) / "b.pem").write_text("")
            self.assertTrue(_tls_pem_ready(raw))

    def test_not_ready_without_configured_certificates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(_tls_pem_ready({"tls": {"sync_dir": tmp, "certificates": []}}))


if __name__ == "__main__":
    unittest.main()
