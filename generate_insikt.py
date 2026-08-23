#!/usr/bin/env python3
"""Generera Insikt — slutsats först, grafen under är beviset.

Tre sektioner: Parkerna, Marknad & intäkt, Batteri & investering.

Användning:
    python3 generate_insikt.py
    python3 generate_insikt.py --output /tmp/insikt.html

Skriver Resultat/rapporter/insikt_YYYYMMDD.html och skriver sökvägen
till stdout. Design och regelverk: docs/plans/2026-08-22-insikt-produkt-spec.md.

Datainsamlingen körs EN gång: parkdatan från parköversikten delas med
marknadssektionen (PPA/intäkt) och stacking-DP:n körs en gång och delas
mellan stacking-tabellen och investeringskalkylen.

För renderar-iteration (samma mönster som generate_rework_dashboard):
    python3 generate_insikt.py --save-data /tmp/insikt_data.json
    python3 generate_insikt.py --from-data /tmp/insikt_data.json  # sekunder
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

from elpris.config import REPORTS_DIR
from elpris.insikt.bess_sektion import build_bess_sektion_data
from elpris.insikt.marknad import build_marknad_data
from elpris.insikt.parkoversikt import build_parkoversikt_data
from elpris.insikt.render import render_insikt


def _step(label: str, fn):
    t0 = time.time()
    out = fn()
    print(f"  {label}: {time.time() - t0:.1f} s", file=sys.stderr)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generera Insikt (alla sektioner) som fristående HTML."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Utfil (default: Resultat/rapporter/insikt_YYYYMMDD.html)",
    )
    parser.add_argument(
        "--save-data",
        type=Path,
        default=None,
        help="Cacha den insamlade datan som JSON (renderar-iteration)",
    )
    parser.add_argument(
        "--from-data",
        type=Path,
        default=None,
        help="Rendera från cachad JSON i stället för att samla in data",
    )
    args = parser.parse_args()

    t_total = time.time()
    if args.from_data is not None:
        data = json.loads(args.from_data.read_text(encoding="utf-8"))
        print(f"  data från cache: {args.from_data}", file=sys.stderr)
    else:
        # Memoisera de tunga loaderna: utan detta läser varje
        # generate_report-anrop om ALLA parkers 15-min-data (15+ min).
        from elpris.insikt.cache import install_insikt_cache
        install_insikt_cache()
        data = _step("parköversikt", build_parkoversikt_data)
        data["marknad"] = _step(
            "marknad & intäkt", lambda: build_marknad_data(data["parks"])
        )
        data["bess"] = _step(
            "batteri & investering", build_bess_sektion_data
        )
    if args.save_data is not None:
        args.save_data.parent.mkdir(parents=True, exist_ok=True)
        args.save_data.write_text(
            json.dumps(data, default=str, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  data sparad: {args.save_data}", file=sys.stderr)
    html = _step("rendering", lambda: render_insikt(data))
    print(f"  totalt: {time.time() - t_total:.1f} s", file=sys.stderr)

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
