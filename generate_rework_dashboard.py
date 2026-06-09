#!/usr/bin/env python3
"""Generera rework-dashboarden (Nordic Clarity — portfölj & marknad).

Bygger parallellt med unified-dashboarden (Track C) och ersätter den
inte. Output: Resultat/rapporter/dashboard_rework_YYYYMMDD.html

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

from elpris.rework_dashboard_html import render_rework

OUT_DIR = PROJECT_ROOT / "Resultat" / "rapporter"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generera rework-dashboarden (portfölj & marknad)."
    )
    parser.add_argument(
        "--out", type=Path, default=None,
        help="Egen utfil (default: Resultat/rapporter/dashboard_rework_YYYYMMDD.html)",
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
        # Insikterna är rena funktioner av sektionerna — räkna alltid om
        # dem så att texterna speglar aktuell insiktslogik vid iteration.
        from elpris.rework_portfolio import build_insights
        data["insights"] = build_insights(
            portfolio=data.get("portfolio", {}),
            market_analysis=data.get("market_analysis", {}),
            cannibalization=data.get("cannibalization", {}),
            orientation=data.get("orientation", {}),
            imbalance=data.get("imbalance", {}),
            ppa_view=data.get("ppa", {}),
        )
    else:
        from elpris.rework_dashboard_data import build_rework_data
        print("Bygger rework-data...", file=sys.stderr)
        data = build_rework_data()

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
        out = OUT_DIR / f"dashboard_rework_{today}.html"

    html = render_rework(data)
    out.write_text(html, encoding="utf-8")
    size_mb = out.stat().st_size / 1024 / 1024
    print(f"  Rework: {out} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
