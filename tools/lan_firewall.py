"""Ensure ms02 UFW allows LAN clients to reach dev DNS + haproxy HTTP(S)."""

from __future__ import annotations

import subprocess
import sys


def ensure_lan_dev_firewall(lan_cidr: str = "192.168.1.0/24") -> None:
    """Idempotent UFW allows for split-horizon DNS and haproxy entry (Mac on LAN)."""
    rules = [
        ("53/udp", "Microscaler dev DNS (dnsmasq)"),
        ("53/tcp", "Microscaler dev DNS (dnsmasq TCP)"),
        ("80/tcp", "Microscaler dev haproxy HTTP"),
        ("443/tcp", "Microscaler dev haproxy HTTPS"),
    ]
    for port_proto, comment in rules:
        port, proto = port_proto.split("/")
        subprocess.run(
            [
                "sudo",
                "ufw",
                "allow",
                "from",
                lan_cidr,
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
    print(f"UFW: ensured LAN ({lan_cidr}) access to dev DNS :53 and haproxy :80/:443", file=sys.stderr)
