#!/usr/bin/env python3
"""Render and manage split-horizon dev DNS on ms02 (dnsmasq).

LAN zones (config/dev-dns.yaml `lan_zones`): Mac / 192.168.1.x clients → MS02_LAN_IP
(LAN proxy). Any number of zones; each is served in full by dnsmasq on ms02.
MetalLB zone (*.metallb.dev): ms02 / Multipass bridge → LoadBalancer IPs from loadbalancer-ips.env.

Mac split DNS needs one resolver file per zone — macOS matches /etc/resolver/<name>
by domain suffix and has no wildcard, so N zones means N files:
  /etc/resolver/dev.microscaler.local
  /etc/resolver/sesameidentity.dev.local
each with one nameserver line pointing at ms02 (see deploy/mac-resolver/).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LAN_EXPOSURE = ROOT / "config" / "lan-exposure.yaml"
DEV_DNS = ROOT / "config" / "dev-dns.yaml"
GENERATED_DIR = ROOT / "deploy" / "generated"
DNSMASQ_CFG = GENERATED_DIR / "dnsmasq-dev.conf"
MAC_RESOLVER_DIR = ROOT / "deploy" / "mac-resolver"
SYSTEM_UNIT = ROOT / "deploy" / "microscaler-dev-dns.service"
SYSTEM_UNIT_DEST = Path("/etc/systemd/system/microscaler-dev-dns.service")
INSTALLED_CFG = Path("/etc/microscaler/dnsmasq-dev.conf")


@dataclass(frozen=True)
class DnsRecord:
    fqdn: str
    address: str


@dataclass(frozen=True)
class LanZone:
    """One LAN DNS zone owned by the ms02 edge."""

    name: str
    hostnames: tuple[str, ...]

    def records(self, lan_ip: str) -> list[DnsRecord]:
        # Apex first: the wildcard `address=/<zone>/` covers the whole subtree, so the
        # explicit names below exist only for docs and non-wildcard resolvers.
        records = [DnsRecord(fqdn=self.name, address=lan_ip)]
        for host in self.hostnames:
            records.append(DnsRecord(fqdn=f"{host}.{self.name}", address=lan_ip))
        return records


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


def load_dev_dns_config() -> dict:
    if not DEV_DNS.is_file():
        raise FileNotFoundError(f"Missing {DEV_DNS}")
    return yaml.safe_load(DEV_DNS.read_text()) or {}


def load_proxy_names() -> list[str]:
    if not LAN_EXPOSURE.is_file():
        raise FileNotFoundError(f"Missing {LAN_EXPOSURE}")
    raw = yaml.safe_load(LAN_EXPOSURE.read_text()) or {}
    names: list[str] = []
    for item in raw.get("proxies") or []:
        name = str(item.get("name") or "").strip()
        if name:
            names.append(name)
    return names


def _proxy_metallb_records(env: dict[str, str], metallb_zone: str) -> list[DnsRecord]:
    raw = yaml.safe_load(LAN_EXPOSURE.read_text()) or {}
    records: list[DnsRecord] = []
    for item in raw.get("proxies") or []:
        name = str(item.get("name") or "").strip()
        ip_env = item.get("lb_ip_env")
        if not name or not ip_env:
            continue
        target_ip = env.get(str(ip_env))
        if not target_ip:
            continue
        records.append(DnsRecord(fqdn=f"{name}.{metallb_zone}", address=target_ip))
    return records


def load_lan_zones(cfg: dict | None = None) -> list[LanZone]:
    """Parse `lan_zones` from config/dev-dns.yaml into LanZone objects."""
    cfg = load_dev_dns_config() if cfg is None else cfg
    raw_zones = cfg.get("lan_zones")
    if not raw_zones:
        # The single-zone shape was replaced outright, not deprecated — a stale config
        # would silently render half the DNS, so fail loudly with the exact migration.
        raise ValueError(
            f"{DEV_DNS} has no `lan_zones:` list.\n"
            "The single `lan_zone:`/`extra_lan_hostnames:` shape is gone. Replace:\n"
            "  lan_zone: dev.microscaler.local\n"
            "  extra_lan_hostnames:\n"
            "    - grafana\n"
            "with:\n"
            "  lan_zones:\n"
            "    - name: dev.microscaler.local\n"
            "      proxy_hostnames: true\n"
            "      hostnames:\n"
            "        - grafana"
        )
    zones: list[LanZone] = []
    proxy_names = load_proxy_names()
    for item in raw_zones:
        name = str((item or {}).get("name") or "").strip()
        if not name:
            raise ValueError(f"{DEV_DNS}: every entry in lan_zones needs a `name`")
        hostnames = {str(h).strip() for h in (item.get("hostnames") or []) if str(h).strip()}
        # Only the zone that opts in absorbs the shared proxy names from
        # lan-exposure.yaml; other zones would otherwise mirror the whole estate.
        if item.get("proxy_hostnames"):
            hostnames |= set(proxy_names)
        zones.append(LanZone(name=name, hostnames=tuple(sorted(hostnames))))
    return zones


def build_records(
    env: dict[str, str],
) -> tuple[list[LanZone], str, dict[str, list[DnsRecord]], list[DnsRecord]]:
    cfg = load_dev_dns_config()
    lan_zones = load_lan_zones(cfg)
    metallb_zone = str(cfg.get("metallb_zone") or "metallb.dev")
    lan_ip = str(
        yaml.safe_load(LAN_EXPOSURE.read_text()).get("ms02_lan_ip")
        or env.get("MS02_LAN_IP")
        or "192.168.1.189"
    )

    # Keyed by zone so callers (urls, resolver install) can stay per-zone.
    lan_records = {zone.name: zone.records(lan_ip) for zone in lan_zones}

    metallb_records = _proxy_metallb_records(env, metallb_zone)
    metallb_records.append(DnsRecord(fqdn=metallb_zone, address=lan_ip))

    return lan_zones, metallb_zone, lan_records, metallb_records


def render_dnsmasq(
    env: dict[str, str],
    *,
    listen_addresses: list[str] | None = None,
) -> str:
    lan_zones, metallb_zone, lan_records, metallb_records = build_records(env)
    if listen_addresses is None:
        listen_addresses = [
            env.get("MS02_LAN_IP") or "192.168.1.189",
            "127.0.0.1",
        ]

    lines = [
        "# Generated by tools/configure_dev_dns.py — do not edit.",
        "no-hosts",
        "no-poll",
        "bind-interfaces",
    ]
    # One `local=` per zone: keeps each zone authoritative here (never forwarded upstream).
    for zone in lan_zones:
        lines.append(f"local=/{zone.name}/")
    lines.append(f"local=/{metallb_zone}/")
    lines.append("")
    for addr in listen_addresses:
        lines.append(f"listen-address={addr}")
    lines.append("")

    for zone in lan_zones:
        for record in lan_records[zone.name]:
            lines.append(f"address=/{record.fqdn}/{record.address}")
        lines.append("")
    for record in metallb_records:
        lines.append(f"address=/{record.fqdn}/{record.address}")
    lines.append("")
    return "\n".join(lines)


def render_mac_resolver(env: dict[str, str]) -> str:
    lan_ip = env.get("MS02_LAN_IP") or "192.168.1.189"
    return f"nameserver {lan_ip}\n"


def cmd_render(_: argparse.Namespace) -> int:
    env = load_env()
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    DNSMASQ_CFG.write_text(render_dnsmasq(env))
    lan_zones, metallb_zone, lan_records, metallb_records = build_records(env)
    # One resolver stub per zone — macOS matches /etc/resolver files by exact suffix.
    MAC_RESOLVER_DIR.mkdir(parents=True, exist_ok=True)
    body = render_mac_resolver(env)
    for zone in lan_zones:
        (MAC_RESOLVER_DIR / zone.name).write_text(body)
    total_lan = sum(len(v) for v in lan_records.values())
    print(f"Wrote {DNSMASQ_CFG} ({total_lan} LAN + {len(metallb_records)} MetalLB records)")
    print(f"Wrote {MAC_RESOLVER_DIR}/ ({len(lan_zones)} resolver stubs)")
    print(f"Zones: {', '.join(z.name for z in lan_zones)}, {metallb_zone}")
    return 0


def _require_dnsmasq() -> None:
    if not shutil.which("dnsmasq"):
        print("dnsmasq is not installed (sudo apt install dnsmasq)", file=sys.stderr)
        sys.exit(1)


def _ensure_lan_firewall(env: dict[str, str]) -> None:
    from lan_firewall import ensure_lan_dev_firewall

    lan_ip = env.get("MS02_LAN_IP") or "192.168.1.189"
    prefix = ".".join(lan_ip.split(".")[:3]) + ".0/24"
    ensure_lan_dev_firewall(prefix)


def cmd_install(_: argparse.Namespace) -> int:
    env = load_env()
    cmd_render(_)
    _require_dnsmasq()
    _ensure_lan_firewall(env)
    if not SYSTEM_UNIT.is_file():
        print(f"Missing {SYSTEM_UNIT}", file=sys.stderr)
        return 1
    subprocess.run(["sudo", "mkdir", "-p", "/etc/microscaler"], check=True)
    subprocess.run(["sudo", "install", "-m", "0644", str(DNSMASQ_CFG), str(INSTALLED_CFG)], check=True)
    subprocess.run(["sudo", "install", "-m", "0644", str(SYSTEM_UNIT), str(SYSTEM_UNIT_DEST)], check=True)
    subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
    print(f"Installed {INSTALLED_CFG}")
    print(f"Installed {SYSTEM_UNIT_DEST}")
    print("Start with: just dev-dns-up")
    return 0


def _install_config() -> None:
    subprocess.run(["sudo", "mkdir", "-p", "/etc/microscaler"], check=True)
    subprocess.run(["sudo", "install", "-m", "0644", str(DNSMASQ_CFG), str(INSTALLED_CFG)], check=True)


def cmd_up(_: argparse.Namespace) -> int:
    env = load_env()
    cmd_render(_)
    _require_dnsmasq()
    _ensure_lan_firewall(env)
    _install_config()
    subprocess.run(["sudo", "systemctl", "enable", "--now", "microscaler-dev-dns.service"], check=True)
    return 0


def cmd_down(_: argparse.Namespace) -> int:
    subprocess.run(["sudo", "systemctl", "stop", "microscaler-dev-dns.service"], check=False)
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    subprocess.run(["sudo", "systemctl", "status", "microscaler-dev-dns.service", "--no-pager"], check=False)
    return 0


def cmd_verify(_: argparse.Namespace) -> int:
    env = load_env()
    lan_zones, metallb_zone, _lan_records, metallb_records = build_records(env)
    lan_ip = env.get("MS02_LAN_IP") or "192.168.1.189"
    failures = 0

    def dig(host: str, server: str) -> str | None:
        result = subprocess.run(
            ["dig", "+short", f"@{server}", host, "A"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None
        answer = result.stdout.strip().splitlines()
        return answer[0] if answer else None

    # Probe one name per zone so a zone missing from dnsmasq shows up on its own line
    # instead of hiding behind a neighbour that happens to resolve.
    for zone in lan_zones:
        probe = _resolver_probe_host(zone)
        got = dig(probe, lan_ip)
        if got == lan_ip:
            print(f"[OK] {probe} → {got} (via {lan_ip})")
        else:
            print(f"[FAIL] {probe} expected {lan_ip}, got {got!r}", file=sys.stderr)
            failures += 1

    sample = next((r for r in metallb_records if r.fqdn.startswith("grafana.")), None)
    if sample:
        got_mb = dig(sample.fqdn, "127.0.0.1")
        if got_mb == sample.address:
            print(f"[OK] {sample.fqdn} → {got_mb} (via 127.0.0.1)")
        else:
            print(
                f"[FAIL] {sample.fqdn} expected {sample.address}, got {got_mb!r}",
                file=sys.stderr,
            )
            failures += 1

    if failures:
        return 1
    zone_list = ", ".join(z.name for z in lan_zones)
    print(f"Split-horizon DNS OK ({zone_list}, {metallb_zone})")
    return 0


def cmd_urls(_: argparse.Namespace) -> int:
    env = load_env()
    lan_zones, metallb_zone, lan_records, _ = build_records(env)
    lan_ip = env.get("MS02_LAN_IP") or "192.168.1.189"
    ports = load_proxies_ports()
    for zone in lan_zones:
        print(f"# LAN zone ({zone.name}) — use with Mac resolver + LAN proxy ports")
        for record in lan_records[zone.name]:
            if record.fqdn == zone.name:
                print(f"{record.fqdn:40} → {record.address}")
                continue
            short = record.fqdn.removesuffix(f".{zone.name}")
            proxy = next((e for e in ports if e[0] == short), None)
            if proxy and proxy[2] == "tcp" and proxy[1] not in (5433, 6390, 5001):
                print(f"{record.fqdn:40} → http://{record.address}:{proxy[1]}/")
            else:
                print(f"{record.fqdn:40} → {record.address}:{proxy[1] if proxy else '?'}")
        print("")
    print(f"# MetalLB zone ({metallb_zone}) — ms02 / Multipass only (direct LB IPs)")
    print(f"grafana.{metallb_zone:24} → dig @{lan_ip} grafana.{metallb_zone}")
    return 0


def load_proxies_ports() -> list[tuple[str, int, str]]:
    raw = yaml.safe_load(LAN_EXPOSURE.read_text()) or {}
    out: list[tuple[str, int, str]] = []
    for item in raw.get("proxies") or []:
        out.append(
            (
                str(item["name"]),
                int(item["lan_port"]),
                str(item.get("protocol") or "tcp"),
            )
        )
    return out


def _resolver_probe_host(zone: LanZone) -> str:
    """A subdomain of the zone to verify against — exercises the wildcard the way
    clients use it. Falls back to the apex for a zone with no explicit hostnames."""
    return f"{zone.hostnames[0]}.{zone.name}" if zone.hostnames else zone.name


def cmd_mac_resolver(_: argparse.Namespace) -> int:
    env = load_env()
    zones = load_lan_zones()
    body = render_mac_resolver(env)
    print(f"sudo mkdir -p /etc/resolver")
    # One block per zone — macOS has no wildcard resolver, each zone needs its own file.
    for zone in zones:
        print("")
        print(f"# Covers all *.{zone.name}:")
        print(f"sudo tee /etc/resolver/{zone.name} <<'EOF'")
        print(body, end="")
        print("EOF")
    print("")
    print("# Verify (any HTTP code proves DNS + edge; 404 just means no route yet):")
    for zone in zones:
        probe = _resolver_probe_host(zone)
        print(f"dscacheutil -q host -a name {probe}")
        print(f"curl -s -o /dev/null -w '%{{http_code}}\\n' http://{probe}/")
    return 0


def cmd_mac_install(_: argparse.Namespace) -> int:
    """Install /etc/resolver files on this Mac, one per LAN zone (requires sudo)."""
    import platform

    if platform.system() != "Darwin":
        print("mac-install is for macOS only; use mac-resolver for instructions", file=sys.stderr)
        return 1
    env = load_env()
    zones = load_lan_zones()
    body = render_mac_resolver(env)
    subprocess.run(["sudo", "mkdir", "-p", "/etc/resolver"], check=True)
    for zone in zones:
        dest = Path(f"/etc/resolver/{zone.name}")
        proc = subprocess.run(
            ["sudo", "tee", str(dest)],
            input=body.encode(),
            stdout=subprocess.DEVNULL,
            check=True,
        )
        if proc.returncode != 0:
            return proc.returncode
        print(f"Installed {dest}")
    for zone in zones:
        print(f"Test: dscacheutil -q host -a name {_resolver_probe_host(zone)}")
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
        ("mac-resolver", cmd_mac_resolver),
        ("mac-install", cmd_mac_install),
    ):
        sub.add_parser(name, help=func.__doc__ or name).set_defaults(func=func)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
