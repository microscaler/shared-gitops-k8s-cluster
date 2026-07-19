#!/usr/bin/env python3
"""Render and manage ms02 LAN → MetalLB proxy (haproxy, systemd-controlled).

TCP mode: per-port forwards (Postgres :5433, OpenSearch Dashboards :5601, …)
plus thin :80/:443 passthrough to Envoy Gateway (ENVOY_GATEWAY_LB_IP).

HTTP host routing for *.dev.microscaler.local is GitOps (Envoy Gateway HTTPRoute),
not haproxy vhosts. config/lan-http-vhosts.yaml is kept with an empty vhosts list
for tool compatibility; do not add manual vhosts there.

Observability UI is OpenSearch Dashboards only — no Grafana/Loki/Prometheus/Jaeger.
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


def load_http_vhosts(env: dict[str, str]) -> tuple[list[HttpVhost], dict]:
    if not VHOSTS_CONFIG.is_file():
        return [], {}
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
    return vhosts, raw


def _slug(name: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in name)


def _tls_pem_ready(raw_vhosts: dict) -> bool:
    tls = raw_vhosts.get("tls") or {}
    sync_dir = Path(str(tls.get("sync_dir") or TLS_SYNC_DIR))
    pem_file = str(tls.get("pem_file") or "dev.microscaler.local.pem")
    return (sync_dir / pem_file).is_file()


def _port_available(bind_ip: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((bind_ip, port))
        return True
    except OSError:
        return False


def render_haproxy(entries: list[ProxyEntry], vhosts: list[HttpVhost], raw_vhosts: dict) -> str:
    lines = [
        "# Generated by tools/configure_lan_proxy.py — do not edit.",
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
        # Always emit TCP frontends. Do not skip when the port is in use — that
        # strips binds during systemd ExecStartPre=render while the old process
        # still holds :80/:443 (Envoy edge passthrough would disappear).
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
                f"  server metallb {entry.target_ip}:{entry.target_port}",
                "",
            ]
        )

    if vhosts:
        http_port = int(raw_vhosts.get("http_port") or 80)
        https_port = int(raw_vhosts.get("https_port") or 443)
        bind_ip = vhosts[0].bind_ip
        if _port_available(bind_ip, http_port):
            lines.extend(
                [
                    "frontend http_dev_vhosts",
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
            lines.extend(["  default_backend http_unknown", ""])
        else:
            print(f"skip HTTP :{http_port}: port in use", file=sys.stderr)
        for vh in vhosts:
            be = _slug(vh.name)
            lines.extend(
                [
                    f"backend http_{be}",
                    "  mode http",
                    f"  server metallb {vh.target_ip}:{vh.target_port}",
                    "",
                ]
            )
        lines.extend(
            [
                "backend http_unknown",
                "  mode http",
                "  # Bare IP (192.168.1.189) or unknown Host → primary dev app.",
                "  http-request redirect code 302 location http://hauliage.dev.microscaler.local%[path] if ! { hdr(host) -m end -i .dev.microscaler.local }",
                "  http-request deny deny_status 404",
                "",
            ]
        )
        if _tls_pem_ready(raw_vhosts) and _port_available(bind_ip, https_port):
            tls = raw_vhosts.get("tls") or {}
            sync_dir = str(tls.get("sync_dir") or TLS_SYNC_DIR)
            lines.extend(
                [
                    "frontend https_dev_vhosts",
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
            lines.extend(["  default_backend http_unknown", ""])
        elif _tls_pem_ready(raw_vhosts):
            print(f"skip HTTPS :{https_port}: port in use", file=sys.stderr)

    if skipped_udp:
        lines.insert(1, f"# Skipped {skipped_udp} UDP proxies (UDP unsupported in this haproxy path).")
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
    vhosts, raw_vhosts = load_http_vhosts(env)
    _write_haproxy_cfg(render_haproxy(entries, vhosts, raw_vhosts))
    print(
        f"Wrote {HAPROXY_CFG} ({len(entries)} TCP proxies, {len(vhosts)} HTTP vhosts, "
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
    vhosts, _ = load_http_vhosts(env)
    lan_ip = entries[0].bind_ip if entries else env.get("MS02_LAN_IP", "192.168.1.189")
    failures = 0
    for entry in entries:
        if entry.protocol != "tcp":
            continue
        url_host = f"{lan_ip}:{entry.lan_port}"
        if entry.name in ("grafana", "prometheus", "jaeger-ui", "minio-console", "mailpit-web", "mailhog-web"):
            cmd = ["curl", "-sf", "--max-time", "5", f"http://{url_host}/"]
        elif entry.name == "routellm":
            cmd = ["curl", "-sf", "--max-time", "5", f"http://{url_host}/health"]
        elif entry.name == "registry":
            cmd = ["curl", "-sf", "--max-time", "5", f"http://{url_host}/v2/"]
        elif entry.name == "postgres":
            cmd = ["bash", "-lc", f"timeout 3 bash -c '</dev/tcp/{lan_ip}/{entry.lan_port}'"]
        else:
            cmd = ["bash", "-lc", f"timeout 3 bash -c '</dev/tcp/{lan_ip}/{entry.lan_port}'"]
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            print(f"[OK] {entry.name} {lan_ip}:{entry.lan_port} -> {entry.target_ip}:{entry.target_port}")
        else:
            print(
                f"[FAIL] {entry.name} {lan_ip}:{entry.lan_port} -> {entry.target_ip}:{entry.target_port}",
                file=sys.stderr,
            )
            failures += 1
    for vh in vhosts:
        cmd = ["curl", "-sf", "--max-time", "5", "-H", f"Host: {vh.host}", f"http://{lan_ip}/"]
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            print(f"[OK] {vh.host} http://{lan_ip}/ -> {vh.target_ip}:{vh.target_port}")
        else:
            print(f"[FAIL] {vh.host} http://{lan_ip}/", file=sys.stderr)
            failures += 1
    if failures:
        print(f"{failures} probe(s) failed", file=sys.stderr)
        return 1
    tcp_count = sum(1 for e in entries if e.protocol == "tcp")
    print(f"All probes OK ({tcp_count} TCP + {len(vhosts)} HTTP vhosts)")
    return 0


def cmd_urls(_: argparse.Namespace) -> int:
    env = load_env()
    entries = load_proxies(env)
    vhosts, _raw_vhosts = load_http_vhosts(env)
    lan_ip = entries[0].bind_ip if entries else env.get("MS02_LAN_IP", "192.168.1.189")
    print(f"# Reach from Mac via ms02 LAN ({lan_ip})")
    print("# HTTP hosts: Envoy Gateway HTTPRoutes (gitops/root/components/envoy-gateway/)")
    print("  https://hauliage.dev.microscaler.local/")
    print("  https://opensearch.dev.microscaler.local/")
    print("  https://grafana.dev.microscaler.local/   # alias → OpenSearch Dashboards")
    print("  https://tilt-sesame.dev.microscaler.local/")
    print("  https://tilt-hauliage.dev.microscaler.local/")
    if vhosts:
        print("# Legacy haproxy vhosts (should be empty)")
        for vh in vhosts:
            print(f"{vh.name:22} http://{vh.host}/")
    print("# TCP ports (non-HTTP services + Envoy edge passthrough)")
    for entry in entries:
        if entry.name in ("envoy-http", "envoy-https"):
            print(f"{entry.name:22} {lan_ip}:{entry.lan_port} -> Envoy {entry.target_ip}:{entry.target_port}")
            continue
        scheme = "http" if entry.protocol == "tcp" and entry.lan_port not in (5433, 6390, 5001) else entry.protocol
        if scheme == "http":
            print(f"{entry.name:22} http://{lan_ip}:{entry.lan_port}/")
        else:
            print(f"{entry.name:22} {lan_ip}:{entry.lan_port} ({entry.protocol})")
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
