#!/usr/bin/env python3
"""Render and manage ms02 LAN edge (haproxy, systemd-controlled).

Architecture (slim):
  - MetalLB → Envoy VIP only (for the edge path)
  - haproxy owns *.dev.microscaler.local:
      Tilt hosts → 127.0.0.1 (only traffic outside Envoy)
      everything else → Envoy :80 (HTTPRoute GitOps)
  - L4 ports → Envoy VIP (TCPRoute/UDPRoute GitOps)

See docs/edge-envoy-vs-metallb.md.
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "lan-exposure.yaml"
VHOSTS_CONFIG = ROOT / "config" / "lan-http-vhosts.yaml"
GENERATED_DIR = ROOT / "deploy" / "generated"
HAPROXY_CFG = GENERATED_DIR / "haproxy.cfg"
SYSTEM_UNIT = ROOT / "deploy" / "microscaler-lan-proxy.service"
SYSTEM_UNIT_DEST = Path("/etc/systemd/system/microscaler-lan-proxy.service")
TLS_SYNC_DIR = Path("/etc/microscaler/haproxy/certs")


@dataclass(frozen=True)
class ProxyEntry:
    name: str
    lan_port: int
    target_ip: str
    target_port: int
    protocol: str
    bind_ip: str


@dataclass(frozen=True)
class HttpVhost:
    host: str
    name: str
    target_ip: str
    target_port: int
    bind_ip: str


@dataclass(frozen=True)
class DefaultHttpBackend:
    name: str
    target_ip: str
    target_port: int


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for rel in ("config/cluster.env", "config/loadbalancer-ips.env"):
        path = ROOT / rel
        if not path.is_file():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            env.setdefault(key.strip(), val.strip())
    return env


def _bind_ip(env: dict[str, str], raw: dict | None = None) -> str:
    if raw and raw.get("ms02_lan_ip"):
        return str(raw["ms02_lan_ip"])
    if CONFIG_PATH.is_file():
        exposure = yaml.safe_load(CONFIG_PATH.read_text()) or {}
        if exposure.get("ms02_lan_ip"):
            return str(exposure["ms02_lan_ip"])
    return str(env.get("MS02_LAN_IP") or "192.168.1.189")


def load_proxies(env: dict[str, str]) -> list[ProxyEntry]:
    if not CONFIG_PATH.is_file():
        raise FileNotFoundError(f"Missing {CONFIG_PATH}")
    raw = yaml.safe_load(CONFIG_PATH.read_text())
    bind_ip = _bind_ip(env, raw)
    entries: list[ProxyEntry] = []
    for item in raw.get("proxies") or []:
        ip_env = item.get("lb_ip_env")
        if not ip_env:
            raise ValueError(f"proxy {item.get('name')} missing lb_ip_env")
        target_ip = env.get(str(ip_env))
        if not target_ip:
            raise ValueError(f"env {ip_env} not set for proxy {item.get('name')}")
        entries.append(
            ProxyEntry(
                name=str(item["name"]),
                lan_port=int(item["lan_port"]),
                target_ip=target_ip,
                target_port=int(item["target_port"]),
                protocol=str(item.get("protocol") or "tcp").lower(),
                bind_ip=bind_ip,
            )
        )
    return entries


def load_http_vhosts(env: dict[str, str]) -> tuple[list[HttpVhost], dict, DefaultHttpBackend | None]:
    if not VHOSTS_CONFIG.is_file():
        return [], {}, None
    raw = yaml.safe_load(VHOSTS_CONFIG.read_text()) or {}
    bind_ip = _bind_ip(env, None)
    vhosts: list[HttpVhost] = []
    for item in raw.get("vhosts") or []:
        ip_env = item.get("lb_ip_env")
        target_host = item.get("target_host")
        if target_host:
            target_ip = str(target_host)
        elif ip_env:
            target_ip = env.get(str(ip_env))
            if not target_ip:
                raise ValueError(f"env {ip_env} not set for vhost {item.get('host')}")
        else:
            raise ValueError(
                f"vhost {item.get('host')} requires lb_ip_env or target_host"
            )
        vhosts.append(
            HttpVhost(
                host=str(item["host"]),
                name=str(item.get("name") or item["host"]),
                target_ip=target_ip,
                target_port=int(item["target_port"]),
                bind_ip=bind_ip,
            )
        )
    default: DefaultHttpBackend | None = None
    raw_default = raw.get("default_backend") or {}
    if raw_default:
        ip_env = raw_default.get("lb_ip_env")
        if not ip_env:
            raise ValueError("default_backend requires lb_ip_env")
        tip = env.get(str(ip_env))
        if not tip:
            raise ValueError(f"env {ip_env} not set for default_backend")
        default = DefaultHttpBackend(
            name=str(raw_default.get("name") or "envoy"),
            target_ip=tip,
            target_port=int(raw_default.get("target_port") or 80),
        )
    return vhosts, raw, default


def _slug(name: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in name)


def _tls_pem_ready(raw_vhosts: dict) -> bool:
    tls = raw_vhosts.get("tls") or {}
    sync_dir = Path(str(tls.get("sync_dir") or TLS_SYNC_DIR))
    pem_file = str(tls.get("pem_file") or "dev.microscaler.local.pem")
    return (sync_dir / pem_file).is_file()


def render_haproxy(
    entries: list[ProxyEntry],
    vhosts: list[HttpVhost],
    raw_vhosts: dict,
    default_backend: DefaultHttpBackend | None = None,
) -> str:
    lines = [
        "# Generated by tools/configure_lan_proxy.py — do not edit.",
        "# *.dev → haproxy (Tilt local / else Envoy); L4 → Envoy VIP.",
        "global",
        "  log /dev/log local0",
        "  maxconn 4096",
        "",
        "defaults",
        "  log global",
        "  option dontlognull",
        "  timeout connect 5s",
        "  timeout client  1h",
        "  timeout server  1h",
        "",
    ]
    skipped_udp = 0
    for entry in entries:
        if entry.protocol != "tcp":
            skipped_udp += 1
            continue
        fe = _slug(entry.name)
        lines.extend(
            [
                f"frontend lan_{fe}",
                f"  bind {entry.bind_ip}:{entry.lan_port}",
                "  mode tcp",
                f"  default_backend be_{fe}",
                "",
                f"backend be_{fe}",
                "  mode tcp",
                f"  server envoy {entry.target_ip}:{entry.target_port}",
                "",
            ]
        )

    bind_ip = vhosts[0].bind_ip if vhosts else _bind_ip({}, None)
    http_port = int(raw_vhosts.get("http_port") or 80)
    https_port = int(raw_vhosts.get("https_port") or 443)
    default_name = f"http_{_slug(default_backend.name)}" if default_backend else "http_deny"

    if vhosts or default_backend:
        lines.extend(
            [
                "frontend http_dev",
                f"  bind {bind_ip}:{http_port}",
                "  mode http",
                "  option forwardfor",
                "  http-request set-header X-Forwarded-Proto http if !{ ssl_fc }",
            ]
        )
        for vh in vhosts:
            acl = _slug(vh.host)
            lines.append(f"  acl host_{acl} hdr(host) -i {vh.host}")
            lines.append(f"  use_backend http_{_slug(vh.name)} if host_{acl}")
        lines.extend([f"  default_backend {default_name}", ""])

        for vh in vhosts:
            be = _slug(vh.name)
            lines.extend(
                [
                    f"backend http_{be}",
                    "  mode http",
                    f"  server tilt {vh.target_ip}:{vh.target_port}",
                    "",
                ]
            )
        if default_backend:
            lines.extend(
                [
                    f"backend {default_name}",
                    "  mode http",
                    f"  server envoy {default_backend.target_ip}:{default_backend.target_port}",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "backend http_deny",
                    "  mode http",
                    "  http-request deny deny_status 404",
                    "",
                ]
            )

        if _tls_pem_ready(raw_vhosts):
            tls = raw_vhosts.get("tls") or {}
            sync_dir = str(tls.get("sync_dir") or TLS_SYNC_DIR)
            lines.extend(
                [
                    "frontend https_dev",
                    f"  bind {bind_ip}:{https_port} ssl crt {sync_dir}/",
                    "  mode http",
                    "  option forwardfor",
                    "  http-request set-header X-Forwarded-Proto https",
                ]
            )
            for vh in vhosts:
                acl = _slug(vh.host)
                lines.append(f"  acl host_{acl} hdr(host) -i {vh.host}")
                lines.append(f"  use_backend http_{_slug(vh.name)} if host_{acl}")
            lines.extend([f"  default_backend {default_name}", ""])

    if skipped_udp:
        lines.insert(2, f"# Skipped {skipped_udp} UDP proxies (use Envoy VIP + mpqemubr0 route).")
    return "\n".join(lines)


def _write_haproxy_cfg(text: str) -> None:
    """Write generated cfg; use sudo when the path is root-owned (prior lan-proxy runs)."""
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    try:
        HAPROXY_CFG.write_text(text)
        return
    except PermissionError:
        pass
    tmp = GENERATED_DIR / "haproxy.cfg.tmp"
    tmp.write_text(text)
    subprocess.run(
        ["sudo", "install", "-m", "0644", "-o", os.getenv("USER", "root"), str(tmp), str(HAPROXY_CFG)],
        check=True,
    )
    tmp.unlink(missing_ok=True)


def cmd_render(_: argparse.Namespace) -> int:
    env = load_env()
    entries = load_proxies(env)
    vhosts, raw_vhosts, default_be = load_http_vhosts(env)
    _write_haproxy_cfg(render_haproxy(entries, vhosts, raw_vhosts, default_be))
    print(
        f"Wrote {HAPROXY_CFG} ({len(entries)} L4→Envoy, {len(vhosts)} tilt vhosts, "
        f"default={'envoy' if default_be else 'none'}, "
        f"TLS={'yes' if _tls_pem_ready(raw_vhosts) else 'pending'})"
    )
    return 0


def _require_haproxy() -> None:
    if not shutil.which("haproxy"):
        print("haproxy is not installed (sudo apt install haproxy)", file=sys.stderr)
        sys.exit(1)


def _disable_distro_haproxy() -> None:
    """Ubuntu `haproxy.service` binds /etc/haproxy — disable when using our unit."""
    subprocess.run(["sudo", "systemctl", "disable", "--now", "haproxy.service"], check=False)


def _ensure_lan_firewall(env: dict[str, str]) -> None:
    from lan_firewall import ensure_lan_dev_firewall

    lan_ip = env.get("MS02_LAN_IP") or "192.168.1.189"
    prefix = ".".join(lan_ip.split(".")[:3]) + ".0/24"
    ensure_lan_dev_firewall(prefix)


def _ensure_tls_dir() -> None:
    subprocess.run(["sudo", "mkdir", "-p", str(TLS_SYNC_DIR)], check=False)
    subprocess.run(["sudo", "chown", f"{os.getenv('USER', 'root')}:{os.getenv('USER', 'root')}", str(TLS_SYNC_DIR)], check=False)


def _sync_tls_best_effort() -> None:
    sync = ROOT / "tools" / "sync_haproxy_tls.py"
    if not sync.is_file():
        return
    result = subprocess.run(["python3", str(sync), "sync"], check=False)
    if result.returncode != 0:
        print("TLS sync skipped (cert-manager secret not ready yet); HTTP :80 still works", file=sys.stderr)


def cmd_install(_: argparse.Namespace) -> int:
    env = load_env()
    cmd_render(_)
    _require_haproxy()
    _ensure_lan_firewall(env)
    _ensure_tls_dir()
    if not SYSTEM_UNIT.is_file():
        print(f"Missing {SYSTEM_UNIT}", file=sys.stderr)
        return 1
    _disable_distro_haproxy()
    subprocess.run(["sudo", "install", "-m", "0644", str(SYSTEM_UNIT), str(SYSTEM_UNIT_DEST)], check=True)
    subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
    print(f"Installed {SYSTEM_UNIT_DEST}")
    print("Start with: just lan-proxy-up")
    return 0


def cmd_up(_: argparse.Namespace) -> int:
    env = load_env()
    _ensure_tls_dir()
    _sync_tls_best_effort()
    _ensure_lan_firewall(env)
    # Stop before render so bind-probe sees ports free (avoid skip :80/:443 on restart).
    subprocess.run(["sudo", "systemctl", "stop", "microscaler-lan-proxy.service"], check=False)
    subprocess.run(["sudo", "systemctl", "stop", "haproxy.service"], check=False)
    # Brief settle — stale LISTEN after stop races the port probe.
    time.sleep(0.5)
    cmd_render(_)
    _require_haproxy()
    _disable_distro_haproxy()
    subprocess.run(["sudo", "systemctl", "enable", "--now", "microscaler-lan-proxy.service"], check=True)
    return 0


def cmd_down(_: argparse.Namespace) -> int:
    subprocess.run(["sudo", "systemctl", "stop", "microscaler-lan-proxy.service"], check=False)
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    subprocess.run(["sudo", "systemctl", "status", "microscaler-lan-proxy.service", "--no-pager"], check=False)
    return 0


def cmd_verify(_: argparse.Namespace) -> int:
    env = load_env()
    entries = load_proxies(env)
    vhosts, _, _default = load_http_vhosts(env)
    lan_ip = entries[0].bind_ip if entries else env.get("MS02_LAN_IP", "192.168.1.189")
    failures = 0
    for entry in entries:
        if entry.protocol != "tcp":
            continue
        if entry.name == "registry":
            cmd = ["curl", "-sf", "--max-time", "5", f"http://{lan_ip}:{entry.lan_port}/v2/"]
        else:
            cmd = ["bash", "-lc", f"timeout 3 bash -c '</dev/tcp/{lan_ip}/{entry.lan_port}'"]
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            print(f"[OK] {entry.name} {lan_ip}:{entry.lan_port} -> Envoy {entry.target_ip}:{entry.target_port}")
        else:
            print(
                f"[FAIL] {entry.name} {lan_ip}:{entry.lan_port} -> Envoy {entry.target_ip}:{entry.target_port}",
                file=sys.stderr,
            )
            failures += 1
    for vh in vhosts:
        cmd = ["curl", "-sf", "--max-time", "5", "-H", f"Host: {vh.host}", f"http://{lan_ip}/"]
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            print(f"[OK] tilt {vh.host} -> {vh.target_ip}:{vh.target_port}")
        else:
            print(f"[FAIL] tilt {vh.host}", file=sys.stderr)
            failures += 1
    # Smoke one Envoy HTTP host via haproxy default backend
    cmd = [
        "curl",
        "-skf",
        "--max-time",
        "5",
        "--resolve",
        f"opensearch.dev.microscaler.local:443:{lan_ip}",
        "https://opensearch.dev.microscaler.local/",
    ]
    if subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        print(f"[OK] *.dev default → Envoy (opensearch)")
    else:
        print("[FAIL] *.dev default → Envoy (opensearch)", file=sys.stderr)
        failures += 1
    if failures:
        print(f"{failures} probe(s) failed", file=sys.stderr)
        return 1
    print(f"All probes OK ({sum(1 for e in entries if e.protocol == 'tcp')} L4 + {len(vhosts)} tilt)")
    return 0


def cmd_urls(_: argparse.Namespace) -> int:
    env = load_env()
    entries = load_proxies(env)
    vhosts, _raw, default_be = load_http_vhosts(env)
    lan_ip = entries[0].bind_ip if entries else env.get("MS02_LAN_IP", "192.168.1.189")
    print(f"# Reach from Mac via ms02 LAN ({lan_ip})")
    print("# haproxy owns *.dev — Tilt local; else Envoy HTTPRoute")
    for vh in vhosts:
        print(f"  https://{vh.host}/  (tilt → {vh.target_ip}:{vh.target_port})")
    if default_be:
        print(f"  https://*.dev.microscaler.local/  (default → Envoy {default_be.target_ip}:{default_be.target_port})")
    print("# L4 → Envoy TCPRoute (same ports on VIP)")
    for entry in entries:
        print(f"{entry.name:22} {lan_ip}:{entry.lan_port} -> Envoy :{entry.target_port}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, func in (
        ("render", cmd_render),
        ("install", cmd_install),
        ("up", cmd_up),
        ("down", cmd_down),
        ("status", cmd_status),
        ("verify", cmd_verify),
        ("urls", cmd_urls),
    ):
        sub.add_parser(name, help=func.__doc__ or name).set_defaults(func=func)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
