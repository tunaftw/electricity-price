#!/usr/bin/env python3
"""Generera Översikt — solportföljen och elmarknaden på en sida.

Fem delar: Portföljen, Elmarknaden, Terminer, Batteri och Datastatus.
Design: docs/plans/2026-09-22-oversikt-design.md.

Användning:
    python3 generate_oversikt.py
    python3 generate_oversikt.py --output /tmp/oversikt.html

    # Som Claude-artifact (utan dokumentskal):
    python3 generate_oversikt.py --artifact --output /tmp/oversikt_artifact.html

    # Iterera på renderaren utan att räkna om datan (sekunder):
    python3 generate_oversikt.py --save-data /tmp/oversikt.json
    python3 generate_oversikt.py --from-data /tmp/oversikt.json

Skriver Resultat/rapporter/oversikt_YYYYMMDD.html och sökvägen till stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

from elpris.config import REPORTS_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description="Generera Översikt som fristående HTML.")
    parser.add_argument("--output", type=Path, default=None,
                        help="Utfil (default: Resultat/rapporter/oversikt_YYYYMMDD.html)")
    parser.add_argument("--save-data", type=Path, default=None,
                        help="Spara den insamlade datan som JSON")
    parser.add_argument("--from-data", type=Path, default=None,
                        help="Rendera från sparad JSON i stället för att räkna om")
    parser.add_argument("--artifact", action="store_true",
                        help="Skriv sidan utan dokumentskal, för publicering som Claude-artifact")
    args = parser.parse_args()

    t0 = time.time()
    if args.from_data:
        data = json.loads(args.from_data.read_text(encoding="utf-8"))
    else:
        from elpris.oversikt.build import build_oversikt_data
        print("Samlar data…", file=sys.stderr)
        data = build_oversikt_data()
        if args.save_data:
            args.save_data.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
            print(f"  data sparad: {args.save_data}", file=sys.stderr)

    from elpris.oversikt.render import render_oversikt, render_oversikt_fragment
    html = render_oversikt_fragment(data) if args.artifact else render_oversikt(data)
    out = args.output or REPORTS_DIR / f"oversikt_{date.today():%Y%m%d}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"  klart på {time.time() - t0:.1f} s, {len(html) / 1024:.0f} kB", file=sys.stderr)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
