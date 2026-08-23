#!/usr/bin/env python3
"""Generera investerarrapporten — en kurerad ensidesrapport per månad.

Rapporten är fristående HTML utan externa beroenden (ingen CDN, ingen
JS), så den kan mejlas och skrivas ut offline.

    python3 generate_investor_report.py                    # senaste stängda månad
    python3 generate_investor_report.py --month 2026-07
    python3 generate_investor_report.py --save-data /tmp/inv.json
    python3 generate_investor_report.py --from-data /tmp/inv.json --month 2026-06

``--save-data``/``--from-data`` cachar parköversikten (den tunga delen,
~10 min) så renderaren kan itereras på sekunder. Cachen är
månadsoberoende — samma fil kan användas för flera rapportmånader så
länge månaden ryms i historiken.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from elpris.config import REPORTS_DIR
from elpris.insikt.investerare import build_investor_data, render_investor_html


def parse_month(value: str) -> tuple:
    """'YYYY-MM' → (year, month)."""
    try:
        year_s, month_s = value.split("-")
        year, month = int(year_s), int(month_s)
        if not 1 <= month <= 12:
            raise ValueError
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Ogiltig månad: {value!r} — förväntar YYYY-MM"
        )
    return year, month


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generera investerarrapport (fristående HTML)."
    )
    parser.add_argument(
        "--month", type=parse_month, default=None,
        help="Rapportmånad YYYY-MM (default: senaste stängda månad)",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Utfil (default: Resultat/rapporter/investerare_YYYY-MM.html)",
    )
    parser.add_argument(
        "--save-data", type=Path, default=None,
        help="Spara parköversiktens JSON för snabb iteration",
    )
    parser.add_argument(
        "--from-data", type=Path, default=None,
        help="Läs parköversikten från cachad JSON istället för att bygga om",
    )
    args = parser.parse_args()

    year, month = args.month if args.month else (None, None)

    parkoversikt = None
    if args.from_data:
        parkoversikt = json.loads(args.from_data.read_text(encoding="utf-8"))
    elif args.save_data:
        from elpris.insikt.parkoversikt import build_parkoversikt_data
        parkoversikt = build_parkoversikt_data()
        args.save_data.write_text(
            json.dumps(parkoversikt), encoding="utf-8"
        )
        print(f"Parköversikt cachad: {args.save_data}", file=sys.stderr)

    data = build_investor_data(year, month, parkoversikt=parkoversikt)
    html = render_investor_html(data)

    out = args.output
    if out is None:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out = REPORTS_DIR / f"investerare_{data['period']['month_key']}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")

    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
