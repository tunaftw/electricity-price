#!/usr/bin/env python3
"""Generate the Unified Dashboard (Track A and/or Track C)."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris.unified_dashboard_data import build_unified_data
from elpris.unified_dashboard_html import render_track_a

OUT_DIR = PROJECT_ROOT / "Resultat" / "rapporter"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--track", choices=["A", "C", "both"], default="both")
    args = p.parse_args()

    print("Building unified data...", file=sys.stderr)
    data = build_unified_data()
    today = datetime.now().strftime("%Y%m%d")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.track in ("A", "both"):
        html = render_track_a(data)
        out = OUT_DIR / f"dashboard_unified_{today}.html"
        out.write_text(html, encoding="utf-8")
        size_mb = out.stat().st_size / 1024 / 1024
        print(f"  Track A: {out} ({size_mb:.1f} MB)")

    if args.track in ("C", "both"):
        try:
            from elpris.unified_dashboard_v3_html import render_track_c  # noqa: F401
            html = render_track_c(data)
            out = OUT_DIR / f"dashboard_unified_v3_{today}.html"
            out.write_text(html, encoding="utf-8")
            size_mb = out.stat().st_size / 1024 / 1024
            print(f"  Track C: {out} ({size_mb:.1f} MB)")
        except ImportError:
            print("  Track C: not yet implemented, skipped", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
