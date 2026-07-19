#!/usr/bin/env python3
"""One-shot: rewrite operational paths from shared-k8s-cluster → shared-gitops-k8s-cluster."""

from __future__ import annotations

from pathlib import Path

REPOS = [
    "hauliage",
    "lifeguard",
    "BRRTRouter",
    "sesame-idam",
    "seasame-idam",
    "cylon",
    "DCops",
    "rerp",
    "fleetingdns",
    "opengroupware",
    "shared-gitops-k8s-cluster",
    "cylon-local-infra",
]

GLOBS = [
    "Justfile",
    "justfile",
    "Tiltfile",
    "AGENTS.md",
    ".cursor/rules/*.mdc",
    "scripts/dev_up.py",
    "scripts/dev_down.py",
    "scripts/setup_data_port_forwards.py",
    "scripts/deploy-shared-k8s.sh",
    "deployment-configuration/systemd/*.service",
    "deployment-configuration/k8s/daemon/Tiltfile",
    "deployment-configuration/k8s/daemon/justfile",
    "docs/remote-tilt-workflow.md",
    "docs/day0-host-edge-ansible.md",
    "docs/design.md",
    "docs/observability-opensearch.md",
    "docs/llmwiki/README.md",
    "docs/llmwiki/topics/cluster-topology.md",
    "deploy/microscaler-lan-proxy.service",
    "gitops/inventory/*.yaml",
    "README.md",
]

REPLACEMENTS = [
    (
        "/home/casibbald/Workspace/microscaler/shared-k8s-cluster",
        "/home/casibbald/Workspace/microscaler/shared-gitops-k8s-cluster",
    ),
    (
        "~/Workspace/microscaler/shared-k8s-cluster",
        "~/Workspace/microscaler/shared-gitops-k8s-cluster",
    ),
    (
        "Workspace/remote/microscaler/shared-k8s-cluster",
        "Workspace/remote/microscaler/shared-gitops-k8s-cluster",
    ),
    ("../shared-k8s-cluster", "../shared-gitops-k8s-cluster"),
    ("microscaler/shared-k8s-cluster", "microscaler/shared-gitops-k8s-cluster"),
]


def main() -> None:
    root = Path.home() / "Workspace/microscaler"
    changed: list[str] = []
    for repo in REPOS:
        base = root / repo
        if not base.is_dir():
            continue
        files: set[Path] = set()
        for pat in GLOBS:
            files.update(base.glob(pat))
        for path in sorted(files):
            if not path.is_file() or ".git" in path.parts:
                continue
            try:
                raw = path.read_bytes()
            except OSError:
                continue
            if b"\x00" in raw[:1024]:
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            if "shared-k8s-cluster" not in text:
                continue
            new = text
            for old, repl in REPLACEMENTS:
                new = new.replace(old, repl)
            # leftover prose / comments after path rewrite
            new = new.replace("shared-k8s-cluster", "shared-gitops-k8s-cluster")
            if new != text:
                path.write_text(new, encoding="utf-8")
                changed.append(str(path))
    print(f"updated {len(changed)} files")
    for c in changed:
        print(f"  {c}")


if __name__ == "__main__":
    main()
