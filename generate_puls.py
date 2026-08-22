#!/usr/bin/env python3
"""Daglig puls — avvikelsedetektion över gårdagens data.

Kör sex detektorer (inverter-underprestation, fastnad nattsignal, saknad
data, yield-avvikelse, alarmspik, släpande datakällor) och skriver dels en
terminal-sammanfattning, dels en liten HTML-sida.

    python3 generate_puls.py                     # igår
    python3 generate_puls.py --date 2026-07-27   # valfritt dygn
    python3 generate_puls.py --no-html           # bara terminal

Exit-kod är alltid 0: en avvikelse är ett fynd, inte ett processfel. Bara
oväntade undantag ger annan kod.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from elpris.insikt.puls import run_puls, write_puls_html

SEVERITY_MARK = {"warn": "!", "info": "-"}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Daglig puls: avvikelsedetektion + digest"
    )
    parser.add_argument(
        "--date",
        help="Dygn att analysera (YYYY-MM-DD). Default: igår.",
    )
    parser.add_argument(
        "--no-html",
        action="store_true",
        help="Skriv ingen HTML-fil, bara terminal-sammanfattning.",
    )
    args = parser.parse_args()

    if args.date:
        try:
            datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            print(f"Ogiltigt datum: {args.date} (vantat YYYY-MM-DD)")
            return 2

    result = run_puls(args.date)

    print(f"DAGLIG PULS {result['date']}")
    print("-" * 60)
    print(result["summary"])

    if result["findings"]:
        print()
        for finding in result["findings"]:
            mark = SEVERITY_MARK.get(finding["severity"], " ")
            print(f"  [{mark}] {finding['rubrik']}: {finding['text']}")

    if not args.no_html:
        path = write_puls_html(result)
        print()
        print(f"HTML: {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
