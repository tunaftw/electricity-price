#!/usr/bin/env python3
"""Generera månadsvis prestandarapport (HTML) för Svea Solars solparker."""

import argparse
import io
import sys
from datetime import date
from pathlib import Path

# Säkerställ UTF-8-utskrift på Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from elpris.park_config import list_parks, get_park_metadata
from elpris.performance_report_data import generate_report
from elpris.performance_report_html import render_html
from elpris.config import RESULTAT_DIR

OUTPUT_DIR = RESULTAT_DIR / "rapporter"


def main():
    parser = argparse.ArgumentParser(
        description="Generera månadsvis prestandarapport för solparker"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--park", help="Parknyckel (t.ex. horby, hova)")
    group.add_argument("--all", action="store_true", help="Generera för alla parker")
    parser.add_argument(
        "--month",
        help="Månad i formatet YYYY-MM (t.ex. 2026-03). Default: senaste fullständiga månad."
    )
    args = parser.parse_args()

    # Bestäm månad
    if args.month:
        year, month = map(int, args.month.split("-"))
    else:
        today = date.today()
        # Senaste fullständiga månad
        if today.month == 1:
            year, month = today.year - 1, 12
        else:
            year, month = today.year, today.month - 1

    # Bestäm parker
    if args.all:
        parks = list_parks()
    else:
        parks = [args.park]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for park_key in parks:
        meta = get_park_metadata(park_key)
        if meta is None:
            print(f"⚠ Okänd park: {park_key}, hoppar över")
            continue

        zone = meta["zone"]
        display_name = meta["display_name"]
        print(f"Genererar rapport för {display_name} ({zone}), {year}-{month:02d}...")

        try:
            report = generate_report(park_key, year, month)
            html = render_html(report)

            filename = f"performance_{park_key}_{zone}_{year}-{month:02d}.html"
            filepath = OUTPUT_DIR / filename
            filepath.write_text(html, encoding="utf-8")

            print(f"  ✓ {filepath}")
            print(f"    Energi: {report.actual_energy_mwh:.1f} MWh | "
                  f"Budget: {report.budget_energy_mwh:.1f} MWh | "
                  f"Yield: {report.yield_kwh_kwp:.1f} kWh/kWp")
        except Exception as e:
            print(f"  ✗ Fel: {e}", file=sys.stderr)

    print("\nKlart!")


if __name__ == "__main__":
    main()
