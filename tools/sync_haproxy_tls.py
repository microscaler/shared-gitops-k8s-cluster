#!/usr/bin/env python3
"""Sync cert-manager TLS secrets from the cluster to ms02 haproxy cert directory."""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
VHOSTS_CONFIG = ROOT / "config" / "lan-http-vhosts.yaml"


def load_vhosts_config() -> dict:
    if not VHOSTS_CONFIG.is_file():
        raise FileNotFoundError(f"Missing {VHOSTS_CONFIG}")
    return yaml.safe_load(VHOSTS_CONFIG.read_text()) or {}


def kubeconfig_env() -> dict[str, str]:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    kc = ROOT / "kubeconfig" / "shared-k8s.yaml"
    if kc.is_file():
        env.setdefault("KUBECONFIG", str(kc))
    return env


def fetch_secret(namespace: str, name: str) -> dict[str, str]:
    proc = subprocess.run(
        [
            "kubectl",
            "get",
            "secret",
            name,
            "-n",
            namespace,
            "-o",
            "json",
        ],
        capture_output=True,
        text=True,
        env=kubeconfig_env(),
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"secret {namespace}/{name} not found")
    data = json.loads(proc.stdout).get("data") or {}
    return {k: base64.b64decode(v).decode("utf-8") for k, v in data.items()}


def write_combined_pem(sync_dir: Path, pem_file: str, cert_pem: str, key_pem: str) -> Path:
    sync_dir.mkdir(parents=True, exist_ok=True)
    out = sync_dir / pem_file
    content = cert_pem.rstrip() + "\n" + key_pem.rstrip() + "\n"
    if not os.access(sync_dir, os.W_OK):
        import tempfile

        tmp = Path(tempfile.mkdtemp()) / pem_file
        tmp.write_text(content)
        tmp.chmod(0o600)
        subprocess.run(["sudo", "install", "-m", "0600", str(tmp), str(out)], check=True)
    else:
        out.write_text(content)
        out.chmod(0o600)
    return out


def cmd_sync(_: argparse.Namespace) -> int:
    cfg = load_vhosts_config()
    tls = cfg.get("tls") or {}
    namespace = str(tls.get("namespace") or "cert-manager")
    secret_name = str(tls.get("secret_name") or "dev-microscaler-local-tls")
    sync_dir = Path(str(tls.get("sync_dir") or "/etc/microscaler/haproxy/certs"))
    pem_file = str(tls.get("pem_file") or "dev.microscaler.local.pem")

    secret = fetch_secret(namespace, secret_name)
    cert_pem = secret.get("tls.crt")
    key_pem = secret.get("tls.key")
    if not cert_pem or not key_pem:
        print(f"secret {namespace}/{secret_name} missing tls.crt or tls.key", file=sys.stderr)
        return 1

    out = write_combined_pem(sync_dir, pem_file, cert_pem, key_pem)
    print(f"Wrote {out}")
    return 0


def cmd_export_ca(_: argparse.Namespace) -> int:
    """Export dev CA cert for trusting on Mac (install to Keychain / mkcert-style trust)."""
    cfg = load_vhosts_config()
    tls = cfg.get("tls") or {}
    namespace = str(tls.get("namespace") or "cert-manager")
    secret = fetch_secret(namespace, "dev-microscaler-ca")
    ca_pem = secret.get("tls.crt")
    if not ca_pem:
        print("dev-microscaler-ca secret missing tls.crt", file=sys.stderr)
        return 1
    out = ROOT / "deploy" / "generated" / "dev-microscaler-ca.crt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(ca_pem.rstrip() + "\n")
    print(f"Wrote {out}")
    print("Mac trust: sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain deploy/generated/dev-microscaler-ca.crt")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("sync", help="Sync wildcard TLS secret to haproxy cert dir").set_defaults(
        func=cmd_sync
    )
    sub.add_parser("export-ca", help="Export dev CA cert for Mac trust").set_defaults(
        func=cmd_export_ca
    )
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
