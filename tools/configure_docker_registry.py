#!/usr/bin/env python3
"""Add shared-k8s in-cluster registry to Docker insecure-registries on the host."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    path = Path("/etc/docker/daemon.json")
    registries = {
        os.environ.get("REGISTRY_LB_IP", "10.177.76.220")
        + ":"
        + os.environ.get("REGISTRY_PORT", "5000"),
        os.environ.get("REGISTRY_HOST_ALIAS", "localhost:5001"),
    }
    data: dict = {}
    if path.exists():
        data = json.loads(path.read_text())
    existing = set(data.get("insecure-registries", []))
    merged = sorted(existing | registries)
    if merged == sorted(existing):
        print("Docker insecure-registries already configured.")
        return 0
    data["insecure-registries"] = merged
    path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Updated {path}:")
    print(path.read_text())
    print("Run: sudo systemctl restart docker")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
