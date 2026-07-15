"""Validate shared-gitops inventory YAML files."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
INVENTORY = ROOT / "gitops" / "inventory"


def _load(name: str) -> dict | list:
    path = INVENTORY / name
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def validate_clusters() -> list[str]:
    errors: list[str] = []
    data = _load("clusters.yaml")
    clusters = data.get("clusters") or []
    ids: set[str] = set()
    for c in clusters:
        cid = c.get("id")
        if not cid:
            errors.append("cluster missing id")
            continue
        if cid in ids:
            errors.append(f"duplicate cluster id: {cid}")
        ids.add(cid)
        if "git" not in c or "url" not in c["git"]:
            errors.append(f"cluster {cid}: missing git.url")
        status = c.get("status")
        if status not in {"active", "stub", "disabled"}:
            errors.append(f"cluster {cid}: invalid status {status!r}")
    for required in ("dev", "staging", "prod"):
        if required not in ids:
            errors.append(f"missing required cluster id: {required}")
    return errors


def validate_stacks() -> list[str]:
    errors: list[str] = []
    data = _load("platform-stacks.yaml")
    stacks = data.get("stacks") or []
    names: set[str] = set()
    for s in stacks:
        name = s.get("name")
        path = s.get("path")
        if not name or not path:
            errors.append(f"stack missing name/path: {s!r}")
            continue
        if name in names:
            errors.append(f"duplicate stack name: {name}")
        names.add(name)
        rel = ROOT / path.lstrip("./")
        if not (rel / "kustomization.yaml").exists() and not (rel / "kustomization.yml").exists():
            errors.append(f"stack {name}: no kustomization.yaml under {path}")
        for dep in s.get("depends_on") or []:
            if dep not in names and dep not in {x.get("name") for x in stacks}:
                # allow forward refs; check after loop
                pass
    all_names = {s.get("name") for s in stacks}
    for s in stacks:
        for dep in s.get("depends_on") or []:
            if dep not in all_names:
                errors.append(f"stack {s.get('name')}: unknown depends_on {dep}")
    return errors


def validate_metallb() -> list[str]:
    errors: list[str] = []
    data = _load("metallb-services.yaml")
    services = data.get("services") or []
    ips: set[str] = set()
    lan_ports: set[int] = set()
    for svc in services:
        name = svc.get("name")
        lb_ip = svc.get("lb_ip")
        if not name or not lb_ip:
            errors.append(f"metallb service missing name/lb_ip: {svc!r}")
            continue
        if lb_ip in ips:
            errors.append(f"duplicate lb_ip: {lb_ip} ({name})")
        ips.add(lb_ip)
        claimed: set[int] = set()
        lan = svc.get("lan_port")
        if lan is not None:
            claimed.add(lan)
        for extra in svc.get("lan_ports") or []:
            ep = extra.get("lan_port")
            if ep is not None:
                claimed.add(ep)
        for port in claimed:
            if port in lan_ports:
                errors.append(f"duplicate lan_port: {port} ({name})")
            lan_ports.add(port)
        if not svc.get("namespace"):
            errors.append(f"service {name}: missing namespace")
        if not svc.get("ports"):
            errors.append(f"service {name}: missing ports")
    return errors


def validate_apps() -> list[str]:
    errors: list[str] = []
    data = _load("apps.yaml")
    apps = data.get("apps") or []
    ports: set[int] = set()
    ids: set[str] = set()
    for app in apps:
        aid = app.get("id")
        port = app.get("port")
        if not aid or port is None:
            errors.append(f"app missing id/port: {app!r}")
            continue
        if aid in ids:
            errors.append(f"duplicate app id: {aid}")
        ids.add(aid)
        if port in ports:
            errors.append(f"duplicate app port: {port} ({aid})")
        ports.add(port)
    return errors


def main() -> int:
    errors = (
        validate_clusters()
        + validate_stacks()
        + validate_metallb()
        + validate_apps()
    )
    if errors:
        print("inventory validation FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("inventory validation OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
