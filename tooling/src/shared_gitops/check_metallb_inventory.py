"""Check MetalLB inventory vs annotations in gitops/root/components.

Does not mutate the cluster. Exit 1 on drift between inventory lb_ip and
committed Service/HelmRelease annotations.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
INVENTORY = ROOT / "gitops" / "inventory" / "metallb-services.yaml"
COMPONENTS = ROOT / "gitops" / "root" / "components"
ANNOTATION = "metallb.universe.tf/loadBalancerIPs"
IP_RE = re.compile(
    r'metallb\.universe\.tf/loadBalancerIPs:\s*["\']?([0-9.]+)'
)


def main() -> int:
    data = yaml.safe_load(INVENTORY.read_text(encoding="utf-8")) or {}
    services = data.get("services") or []
    by_ip = {s["lb_ip"]: s for s in services if s.get("lb_ip")}
    by_name = {s["name"]: s for s in services if s.get("name")}

    found: list[tuple[str, str, Path]] = []
    for path in COMPONENTS.rglob("*.yaml"):
        text = path.read_text(encoding="utf-8")
        for match in IP_RE.finditer(text):
            found.append((match.group(1), path.relative_to(ROOT).as_posix(), path))

    errors: list[str] = []
    seen_ips: set[str] = set()
    for ip, rel, _ in found:
        seen_ips.add(ip)
        if ip not in by_ip:
            errors.append(f"{rel}: annotation IP {ip} not in metallb-services.yaml")

    # Inventory entries that claim a service should appear in components (unless skipped)
    for svc in services:
        if svc.get("status") == "unused":
            continue
        ip = svc.get("lb_ip")
        if ip and ip not in seen_ips:
            errors.append(
                f"inventory {svc.get('name')}: lb_ip {ip} not found under components/"
            )

    # Name sanity: dashboards IP must be opensearch-dashboards-lb era
    dash = by_name.get("opensearch-dashboards-lb") or by_name.get("opensearch-dashboards")
    if not dash:
        errors.append(
            "inventory missing opensearch-dashboards(-lb) entry for .227 Dashboards UI"
        )

    if errors:
        print("metallb inventory check FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"metallb inventory OK ({len(found)} annotations, {len(services)} inventory rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
