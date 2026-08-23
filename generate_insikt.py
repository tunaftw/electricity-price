#!/usr/bin/env python3
"""Generera Insikt — parköversikten (slutsats först, grafen är beviset).

Användning:
    python3 generate_insikt.py
    python3 generate_insikt.py --output /tmp/insikt.html

Skriver Resultat/rapporter/insikt_YYYYMMDD.html och skriver sökvägen
till stdout. Design och regelverk: docs/plans/2026-08-22-insikt-produkt-spec.md.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from elpris.config import REPORTS_DIR
from elpris.insikt.parkoversikt import build_parkoversikt_data
from elpris.insikt.render import render_insikt


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generera Insikt (parköversikten) som fristående HTML."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Utfil (default: Resultat/rapporter/insikt_YYYYMMDD.html)",
    )
    args = parser.parse_args()

    data = build_parkoversikt_data()
    html = render_insikt(data)

    out = args.output
    if out is None:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out = REPORTS_DIR / f"insikt_{date.today():%Y%m%d}.html"
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
