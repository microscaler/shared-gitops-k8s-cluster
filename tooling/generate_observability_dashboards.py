#!/usr/bin/env python3
"""Generate GitOps NDJSON dashboard bundles from dashboard_definitions."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "gitops/root/components/observability"
sys.path.insert(0, str(COMPONENT))

import dashboard_definitions as definitions  # noqa: E402


def main() -> int:
    out_dir = COMPONENT / "dashboards"
    out_dir.mkdir(parents=True, exist_ok=True)
    for bundle_name, objects in definitions.DASHBOARD_BUNDLES.items():
        lines = [
            json.dumps(
                definitions.export_line(object_type, object_id, payload),
                separators=(",", ":"),
            )
            for object_type, object_id, payload in objects
        ]
        path = out_dir / f"{bundle_name}.ndjson"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {path.name}: {len(lines)} objects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
