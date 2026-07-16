"""Render per-cluster stacks.yaml for the platform-stacks GitOpsSet.

Merges:
  - gitops/inventory/platform-stacks.yaml (catalog: path, depends_on, profile)
  - gitops/clusters/<id>/inventory/stacks/<name>/ (enablement dirs)
  - deployment-configuration/profiles/<env>/<name>/ (optional profile KS)

Output: gitops/clusters/<id>/inventory/stacks.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "gitops" / "inventory" / "platform-stacks.yaml"
CLUSTERS = ROOT / "gitops" / "clusters"
PROFILES = ROOT / "deployment-configuration" / "profiles"


def _load_catalog() -> dict[str, dict]:
    data = yaml.safe_load(CATALOG.read_text(encoding="utf-8")) or {}
    out: dict[str, dict] = {}
    for row in data.get("stacks") or []:
        name = row.get("name")
        if not name:
            continue
        out[name] = row
    return out


def _enabled_stack_names(cluster_id: str) -> list[str]:
    stacks_dir = CLUSTERS / cluster_id / "inventory" / "stacks"
    if not stacks_dir.is_dir():
        return []
    names = sorted(p.name for p in stacks_dir.iterdir() if p.is_dir() and not p.name.startswith("."))
    return names


def render(cluster_id: str, profile_env: str) -> dict:
    catalog = _load_catalog()
    enabled = _enabled_stack_names(cluster_id)
    stacks: list[dict] = []
    unknown: list[str] = []

    for name in enabled:
        row = catalog.get(name)
        if not row:
            unknown.append(name)
            continue
        path = row["path"]
        depends: list[dict[str, str]] = []
        for dep in row.get("depends_on") or []:
            depends.append({"name": f"stack-{dep}"})

        profile = row.get("profile")
        if profile is None:
            # Default: if a profile dir exists for this stack name, depend on it
            if (PROFILES / profile_env / name).is_dir():
                profile = name
        if profile:
            depends.append({"name": f"profile-config-{profile}"})

        # Stable order: stack deps first, then profile
        stacks.append(
            {
                "name": name,
                "path": path,
                "description": row.get("description") or "",
                "depends": depends,
            }
        )

    if unknown:
        raise SystemExit(
            f"enabled stack dirs not in catalog ({cluster_id}): {', '.join(unknown)}"
        )

    return {
        "cluster_id": cluster_id,
        "profile_env": profile_env,
        "stacks": stacks,
    }


def write_stacks(cluster_id: str, profile_env: str, *, check: bool = False) -> Path:
    out_path = CLUSTERS / cluster_id / "inventory" / "stacks.yaml"
    payload = render(cluster_id, profile_env)
    body = (
        "# GENERATED — do not edit by hand.\n"
        f"# Source: gitops/inventory/platform-stacks.yaml + "
        f"clusters/{cluster_id}/inventory/stacks/<name>/\n"
        f"# Regenerate: just sync-stack-inventory {cluster_id}\n"
        + yaml.safe_dump(payload, sort_keys=False, default_flow_style=False)
    )
    if check:
        if not out_path.is_file():
            raise SystemExit(f"missing generated file: {out_path}")
        existing = out_path.read_text(encoding="utf-8")
        if existing != body:
            raise SystemExit(
                f"stacks.yaml drift for {cluster_id}: run "
                f"`just sync-stack-inventory {cluster_id}`"
            )
        print(f"OK {out_path.relative_to(ROOT)} matches catalog+enablement")
        return out_path

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")
    print(f"Wrote {out_path.relative_to(ROOT)} ({len(payload['stacks'])} stacks)")
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cluster_id", nargs="?", default="dev")
    parser.add_argument("--profile-env", default=None, help="defaults to cluster_id")
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if generated file would change",
    )
    args = parser.parse_args(argv)
    profile_env = args.profile_env or args.cluster_id
    write_stacks(args.cluster_id, profile_env, check=args.check)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
