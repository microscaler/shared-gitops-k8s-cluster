"""Node lifecycle for the Multipass/k3s dev cluster (EPIC: tooling
consolidation — logic lives here, day0.justfile shims call `msk8s node ...`).

The cattle rule: nodes are never SSH-fixed in place. A wrong node is
replaced (`msk8s node replace NAME`); `msk8s node doctor` detects drift.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import cloud_init

REPO_ROOT = Path(__file__).resolve().parents[3]


def _run(cmd: list[str], check: bool = True, capture: bool = False,
         quiet: bool = False) -> subprocess.CompletedProcess:
    if not quiet:
        print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, text=True,
                          capture_output=capture)


def load_cluster_env() -> dict[str, str]:
    """Parse config/cluster.env into the process env (KEY=VALUE lines)."""
    env_file = REPO_ROOT / "config" / "cluster.env"
    values: dict[str, str] = {}
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    os.environ.update(values)
    return values


def vm_state(name: str) -> str | None:
    proc = _run(["multipass", "info", name, "--format", "json"], check=False,
                capture=True, quiet=True)
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)["info"][name]["state"]
    except (KeyError, json.JSONDecodeError):
        return None


def vm_exists(name: str) -> bool:
    return vm_state(name) is not None


def vm_ipv4(name: str, attempts: int = 60) -> str:
    for _ in range(attempts):
        proc = _run(["multipass", "info", name, "--format", "json"],
                    check=False, capture=True, quiet=True)
        if proc.returncode == 0:
            info = json.loads(proc.stdout)["info"].get(name, {})
            for ip in info.get("ipv4", []):
                if ip and ip != "--":
                    return ip
        time.sleep(3)
    raise RuntimeError(f"no IPv4 for {name}")


def cp_token(cp: str) -> str:
    proc = _run(["multipass", "exec", cp, "--", "sudo", "cat",
                 "/var/lib/rancher/k3s/server/node-token"], capture=True,
                quiet=True)
    return proc.stdout.strip()


def role_for(name: str, env: dict[str, str]) -> str:
    if name in env.get("K8S_RUNNERS", "").split(","):
        return "runner"
    return "agent"


def node_add(name: str) -> None:
    env = load_cluster_env()
    cp = env["K8S_CP"]
    role = role_for(name, env)
    prefix = "K8S_RUNNER" if role == "runner" else "K8S_WORKER"
    cpus = env.get(f"{prefix}_CPUS", "2")
    mem = env.get(f"{prefix}_MEM", "12G")
    disk = env.get(f"{prefix}_DISK", "40G")

    token = cp_token(cp)
    cp_ip = vm_ipv4(cp)

    if vm_exists(name):
        print(f"{name} already exists — joining k3s only.")
    else:
        rendered = cloud_init.render(
            role, REPO_ROOT / ".multipass" / f"{name}-cloud-init.yaml",
            k3s_token=token, worker_ip="0.0.0.0")
        _run(["multipass", "launch", "24.04", "--name", name,
              "--cpus", cpus, "--memory", mem, "--disk", disk,
              "--cloud-init", str(rendered)])

    ip = vm_ipv4(name)
    # Idempotent agent install (ported from day0 k3s-install-agent).
    active = _run(["multipass", "exec", name, "--", "systemctl", "is-active",
                   "--quiet", "k3s-agent"], check=False, quiet=True)
    if active.returncode == 0:
        print(f"k3s agent already running on {name}.")
    else:
        install = (
            f"curl -sfL https://get.k3s.io | K3S_URL=https://{cp_ip}:6443 "
            f"K3S_TOKEN='{token}' INSTALL_K3S_EXEC='agent --node-ip {ip}' sh -"
        )
        _run(["multipass", "exec", name, "--", "sudo", "bash", "-c", install])
        for _ in range(60):
            if _run(["multipass", "exec", name, "--", "systemctl",
                     "is-active", "--quiet", "k3s-agent"], check=False,
                    quiet=True).returncode == 0:
                break
            time.sleep(5)
        else:
            raise RuntimeError(f"k3s agent did not start on {name}")
    print(f"node {name} ({ip}) joined as {role}.")


def node_delete(name: str, drain: bool = True) -> None:
    load_cluster_env()
    if drain:
        _run(["kubectl", "drain", name, "--ignore-daemonsets",
              "--delete-emptydir-data", "--timeout=120s"], check=False)
        _run(["kubectl", "delete", "node", name], check=False)
    _run(["multipass", "stop", name], check=False)
    _run(["multipass", "delete", name, "--purge"], check=False)
    print(f"node {name} deleted.")


def node_replace(name: str) -> None:
    node_delete(name)
    node_add(name)


def node_doctor() -> int:
    """Compare every node's on-disk registries.yaml with the canonical
    template render. Exit 1 on drift. Read-only."""
    env = load_cluster_env()
    canonical = cloud_init.canonical_registries_yaml()
    names = [env["K8S_CP"]]
    names += [n for n in env.get("K8S_WORKERS", "").split(",") if n]
    names += [n for n in env.get("K8S_RUNNERS", "").split(",") if n]
    drift = 0
    for name in names:
        if vm_state(name) != "Running":
            print(f"  {name}: not running — skipped")
            continue
        proc = _run(["multipass", "exec", name, "--", "cat",
                     "/etc/rancher/k3s/registries.yaml"], check=False,
                    capture=True, quiet=True)
        if proc.returncode != 0:
            print(f"✗ {name}: registries.yaml MISSING")
            drift += 1
            continue
        actual = proc.stdout.strip()
        if actual == canonical.strip():
            print(f"✓ {name}: registries.yaml canonical")
        else:
            print(f"✗ {name}: registries.yaml DRIFTED from template")
            drift += 1
    if drift:
        print(f"\n{drift} node(s) drifted. Fix: msk8s node replace <name>")
    return 1 if drift else 0
