"""Render Multipass cloud-init templates with cluster variables.

Single source of truth for cloud-init rendering (absorbed from
tools/render_cloud_init.py, which is now a shim). Variables come from the
process environment (config/cluster.env is sourced by the just shims) with
the same defaults the old script used.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

ROLES = ("server", "agent", "runner")


def replacements(k3s_token: str = "", worker_ip: str = "") -> dict[str, str]:
    env = os.environ
    return {
        "K8S_CP_IP": env.get("K8S_CP_IP", "10.177.76.210"),
        "K8S_WORKER_1_IP": env.get("K8S_WORKER_1_IP", "10.177.76.211"),
        "K8S_WORKER_2_IP": env.get("K8S_WORKER_2_IP", "10.177.76.212"),
        "K8S_WORKER_3_IP": env.get("K8S_WORKER_3_IP", "10.177.76.213"),
        "K8S_WORKER_4_IP": env.get("K8S_WORKER_4_IP", "10.177.76.214"),
        "REGISTRY_LB_IP": env.get("REGISTRY_LB_IP", "10.177.76.220"),
        "REGISTRY_HOST_ALIAS": env.get("REGISTRY_HOST_ALIAS", "localhost:5001"),
        "WORKSPACE_GUEST": env.get(
            "WORKSPACE_GUEST", "/home/casibbald/Workspace/microscaler"
        ),
        "K3S_TOKEN": k3s_token,
        "WORKER_IP": worker_ip,
    }


def render_text(role: str, k3s_token: str = "", worker_ip: str = "",
                template_dir: Path | None = None) -> str:
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r} (want one of {ROLES})")
    template_dir = template_dir or REPO_ROOT / "multipass"
    template = template_dir / f"cloud-init-k3s-{role}.yaml"
    if not template.is_file():
        raise FileNotFoundError(f"missing template: {template}")
    text = template.read_text()
    for key, value in replacements(k3s_token, worker_ip).items():
        text = text.replace(f"{{{{{key}}}}}", value)
    return text


def render(role: str, output: Path, k3s_token: str = "", worker_ip: str = "",
           template_dir: Path | None = None) -> Path:
    if role in ("agent", "runner") and not k3s_token.strip():
        raise ValueError("K3S_TOKEN required for agent/runner cloud-init")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_text(role, k3s_token, worker_ip, template_dir))
    output.chmod(0o644)
    return output


def canonical_registries_yaml() -> str:
    """The registries.yaml block every node must carry (rendered, no token
    needed) — used by `msk8s node doctor` to detect drift like the
    2026-08-28 k8s-worker-4 incident."""
    text = render_text("agent", k3s_token="doctor", worker_ip="0.0.0.0")
    lines = text.splitlines()
    block: list[str] = []
    capture = False
    for i, line in enumerate(lines):
        if "/etc/rancher/k3s/registries.yaml" in line:
            capture = True
            continue
        if capture:
            if line.strip().startswith(("permissions:", "content:")):
                continue
            if line.startswith("      ") or not line.strip():
                if line.strip():
                    block.append(line[6:])
                continue
            break
    return "\n".join(block).rstrip() + "\n"
