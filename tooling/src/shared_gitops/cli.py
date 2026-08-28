"""msk8s — the ONE entrypoint for shared-gitops-k8s-cluster operations.

Strangler pattern (docs/tooling-consolidation.md): logic migrates from
day0.justfile/justfile bash bodies and loose tools/*.py into this package;
just recipes become one-line shims. New capability lands here first.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import cloud_init, nodes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="msk8s", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    node = sub.add_parser("node", help="node lifecycle (cattle rule)")
    node_sub = node.add_subparsers(dest="node_cmd", required=True)
    for verb, fn_help in (
        ("add", "create VM from template + join k3s (idempotent)"),
        ("replace", "drain + delete + recreate a drifted/broken node"),
        ("delete", "drain + remove a node"),
    ):
        p = node_sub.add_parser(verb, help=fn_help)
        p.add_argument("name")
    node_sub.add_parser("doctor", help="detect node-config drift (read-only)")

    ci = sub.add_parser("cloud-init", help="render a cloud-init template")
    ci.add_argument("role", choices=cloud_init.ROLES)
    ci.add_argument("--output", type=Path, required=True)
    ci.add_argument("--k3s-token", default="")
    ci.add_argument("--worker-ip", default="")

    inv = sub.add_parser("inventory", help="inventory checks")
    inv_sub = inv.add_subparsers(dest="inv_cmd", required=True)
    inv_sub.add_parser("validate", help="schema-check the stack inventory")
    inv_sub.add_parser("metallb", help="check MetalLB IP inventory")

    args = parser.parse_args(argv)

    if args.cmd == "node":
        if args.node_cmd == "add":
            nodes.node_add(args.name)
        elif args.node_cmd == "replace":
            nodes.node_replace(args.name)
        elif args.node_cmd == "delete":
            nodes.node_delete(args.name)
        elif args.node_cmd == "doctor":
            return nodes.node_doctor()
        return 0

    if args.cmd == "cloud-init":
        nodes.load_cluster_env()
        out = cloud_init.render(args.role, args.output,
                                k3s_token=args.k3s_token,
                                worker_ip=args.worker_ip)
        print(out)
        return 0

    if args.cmd == "inventory":
        if args.inv_cmd == "validate":
            from . import validate_inventory
            return validate_inventory.main() or 0
        if args.inv_cmd == "metallb":
            from . import check_metallb_inventory
            return check_metallb_inventory.main() or 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
