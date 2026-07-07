#!/usr/bin/env python3
"""Generate the Unified Dashboard (Track C — Nordic Editorial).

Utvecklingsflöde: ``--save-data data.json`` vid första körningen,
sedan ``--from-data data.json`` för att iterera på renderaren utan
att bygga om datat (sekunder i stället för minuter).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris.unified_dashboard_v3_html import render_track_c

OUT_DIR = PROJECT_ROOT / "Resultat" / "rapporter"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generera Unified Dashboard (Track C — Nordic Editorial)."
    )
    parser.add_argument(
        "--out", type=Path, default=None,
        help="Egen utfil (default: Resultat/rapporter/dashboard_unified_v3_YYYYMMDD.html)",
    )
    parser.add_argument(
        "--save-data", type=Path, default=None, metavar="JSON",
        help="Spara den byggda datastrukturen som JSON (för --from-data)",
    )
    parser.add_argument(
        "--from-data", type=Path, default=None, metavar="JSON",
        help="Rendera från sparad JSON i stället för att bygga om datat",
    )
    args = parser.parse_args()

    if args.from_data is not None:
        print(f"Läser data från {args.from_data}...", file=sys.stderr)
        data = json.loads(args.from_data.read_text(encoding="utf-8"))
    else:
        from elpris.unified_dashboard_data import build_unified_data
        print("Building unified data...", file=sys.stderr)
        data = build_unified_data()

    if args.save_data is not None:
        args.save_data.write_text(
            json.dumps(data, default=str, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  Data sparad: {args.save_data}")

    out = args.out
    if out is None:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y%m%d")
        out = OUT_DIR / f"dashboard_unified_v3_{today}.html"

    html = render_track_c(data)
    out.write_text(html, encoding="utf-8")
    size_mb = out.stat().st_size / 1024 / 1024
    print(f"  Track C: {out} ({size_mb:.1f} MB)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
