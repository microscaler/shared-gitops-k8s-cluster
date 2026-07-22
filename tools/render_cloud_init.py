#!/usr/bin/env python3
"""Render Multipass cloud-init templates with cluster variables."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def render(template: Path, output: Path, replacements: dict[str, str]) -> None:
    text = template.read_text()
    for key, value in replacements.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text)
    output.chmod(0o644)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=("server", "agent"))
    parser.add_argument(
        "--template-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "multipass",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent / ".multipass" / "cloud-init.yaml",
    )
    parser.add_argument("--k3s-token", default=os.environ.get("K3S_TOKEN", ""))
    parser.add_argument("--worker-ip", default=os.environ.get("WORKER_IP", ""))
    args = parser.parse_args()

    if args.role == "agent" and not args.k3s_token.strip():
        print("K3S_TOKEN required for agent cloud-init", file=sys.stderr)
        return 1

    env = os.environ
    replacements = {
        "K8S_CP_IP": env.get("K8S_CP_IP", "10.177.76.210"),
        "K8S_WORKER_1_IP": env.get("K8S_WORKER_1_IP", "10.177.76.211"),
        "K8S_WORKER_2_IP": env.get("K8S_WORKER_2_IP", "10.177.76.212"),
        "K8S_WORKER_3_IP": env.get("K8S_WORKER_3_IP", "10.177.76.213"),
        "REGISTRY_LB_IP": env.get("REGISTRY_LB_IP", "10.177.76.220"),
        "REGISTRY_HOST_ALIAS": env.get("REGISTRY_HOST_ALIAS", "localhost:5001"),
        "WORKSPACE_GUEST": env.get(
            "WORKSPACE_GUEST", "/home/casibbald/Workspace/microscaler"
        ),
        "K3S_TOKEN": args.k3s_token,
        "WORKER_IP": args.worker_ip,
    }

    template = args.template_dir / f"cloud-init-k3s-{args.role}.yaml"
    if not template.is_file():
        print(f"Missing template: {template}", file=sys.stderr)
        return 1

    render(template, args.output, replacements)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
