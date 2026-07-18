#!/usr/bin/env python3
"""Convert NodePort Services to MetalLB LoadBalancer in migrated k8s manifests."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
K8S = ROOT / "k8s"

# namespace/name → MetalLB IP (from config/loadbalancer-ips.env + cluster.env)
LB_BY_SERVICE: dict[tuple[str, str], str] = {}


def load_env() -> None:
    for rel in ("config/cluster.env", "config/loadbalancer-ips.env"):
        path = ROOT / rel
        if not path.is_file():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

    mapping = {
        ("cylon", "routellm"): "ROUTELLM_LB_IP",
        ("cylon", "squid-proxy"): "SQUID_LB_IP",
        ("cylon", "freeradius"): "FREERADIUS_LB_IP",
        ("data", "postgres"): "POSTGRES_LB_IP",
        ("data", "redis"): "REDIS_LB_IP",
        ("data", "minio"): "MINIO_LB_IP",
        ("data", "pact-broker"): "PACT_BROKER_LB_IP",
        ("data", "mailpit"): "MAILPIT_LB_IP",
        ("data", "mailhog"): "MAILPIT_LB_IP",
        ("observability", "grafana"): "GRAFANA_LB_IP",
        ("observability", "prometheus"): "PROMETHEUS_LB_IP",
        ("observability", "loki"): "LOKI_LB_IP",
        ("observability", "jaeger"): "JAEGER_LB_IP",
        ("observability", "otel-collector"): "OTEL_LB_IP",
        ("scheduling", "faktory"): "FAKTORY_LB_IP",
    }
    for key, env_name in mapping.items():
        ip = os.environ.get(env_name)
        if ip:
            LB_BY_SERVICE[key] = ip


def infer_namespace(path: Path, meta: dict) -> str:
    if meta.get("namespace"):
        return meta["namespace"]
    parts = path.parts
    if "observability" in parts:
        return "observability"
    if "cylon-infra" in parts:
        return "cylon"
    if "scheduling" in parts:
        return "scheduling"
    if "platform-data" in parts:
        return "data"
    if "gcp" in parts:
        return "gcp"
    if "ai" in parts:
        return "ai"
    return ""


def patch_service(doc: dict, path: Path) -> bool:
    if doc.get("kind") != "Service":
        return False
    spec = doc.get("spec") or {}
    if spec.get("type") != "NodePort":
        return False
    meta = doc.get("metadata") or {}
    ns = infer_namespace(path, meta)
    name = meta.get("name") or ""
    ip = LB_BY_SERVICE.get((ns, name))
    if not ip:
        print(f"  skip (no LB IP): {ns}/{name}", file=sys.stderr)
        return False
    spec["type"] = "LoadBalancer"
    meta.setdefault("annotations", {})["metallb.universe.tf/loadBalancerIPs"] = ip
    for port in spec.get("ports", []):
        port.pop("nodePort", None)
    print(f"  patched {ns}/{name} -> {ip}")
    return True


def patch_file(path: Path) -> int:
    if path.name.startswith("._"):
        return 0
    try:
        text = path.read_text()
    except UnicodeDecodeError:
        print(f"  skip (binary): {path}", file=sys.stderr)
        return 0
    docs = list(yaml.safe_load_all(text))
    changed = 0
    for doc in docs:
        if doc and patch_service(doc, path):
            changed += 1
    if changed:
        out = []
        for doc in docs:
            if doc is None:
                continue
            out.append(yaml.dump(doc, default_flow_style=False, sort_keys=False))
        path.write_text("---\n".join(out))
    return changed


def main() -> int:
    load_env()
    if not LB_BY_SERVICE:
        print("No LoadBalancer IPs configured", file=sys.stderr)
        return 1
    total = 0
    for path in sorted(K8S.rglob("*.yaml")):
        if "cluster/" in str(path):
            continue
        n = patch_file(path)
        if n:
            print(f"{path.relative_to(ROOT)}: {n} service(s)")
            total += n
    print(f"Patched {total} service(s) total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
