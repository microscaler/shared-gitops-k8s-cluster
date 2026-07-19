"""Ensure ms02 UFW allows LAN / Multipass bridge access for the Dev edge."""

from __future__ import annotations

import subprocess
import sys

# Multipass bridge — in-cluster Envoy reaches host Tilt UIs via this CIDR.
MPQEMU_BRIDGE_CIDR = "10.177.76.0/24"


def _ufw_allow(cidr: str, port: str, proto: str, comment: str) -> None:
    subprocess.run(
        [
            "sudo",
            "ufw",
            "allow",
            "from",
            cidr,
            "to",
            "any",
            "port",
            port,
            "proto",
            proto,
            "comment",
            comment,
        ],
        check=False,
    )


def ensure_lan_dev_firewall(lan_cidr: str = "192.168.1.0/24") -> None:
    """Idempotent UFW allows for DNS, haproxy edge, and host Tilt (Envoy backends)."""
    for port, proto, comment in (
        ("53", "udp", "Microscaler dev DNS (dnsmasq)"),
        ("53", "tcp", "Microscaler dev DNS (dnsmasq TCP)"),
        ("80", "tcp", "Microscaler edge haproxy→Envoy HTTP"),
        ("443", "tcp", "Microscaler edge haproxy→Envoy HTTPS"),
    ):
        _ufw_allow(lan_cidr, port, proto, comment)

    # Tilt UIs bind on the Multipass host; Envoy pods reach them via mpqemubr0.
    for port, comment in (
        ("10351", "tilt-sesame from k8s bridge (Envoy)"),
        ("10352", "tilt-hauliage from k8s bridge (Envoy)"),
    ):
        _ufw_allow(MPQEMU_BRIDGE_CIDR, port, "tcp", comment)

    print(
        f"UFW: ensured LAN ({lan_cidr}) :53/:80/:443 and bridge "
        f"({MPQEMU_BRIDGE_CIDR}) Tilt :10351/:10352",
        file=sys.stderr,
    )
