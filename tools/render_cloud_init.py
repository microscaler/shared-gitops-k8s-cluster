#!/usr/bin/env python3
"""SHIM — logic moved to tooling/src/shared_gitops/cloud_init.py (msk8s).

Kept so existing day0.justfile recipes keep working until they are migrated
to `msk8s cloud-init render` shims. Do not add logic here.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tooling" / "src"))

from shared_gitops.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["cloud-init", *sys.argv[1:]]))
