#!/usr/bin/env python3
"""Kör datakvalitetskontroll på spotprisdata.

Kör ad-hoc från kommandoraden:
    python3 quality_check.py

Exit-kod:
    0: inga fel (varningar tillåtna)
    1: minst ett fel
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris.quality import check_all_spot_prices, format_report


def main() -> int:
    print("Kör datakvalitets-kontroll...\n")
    reports = check_all_spot_prices()
    print(format_report(reports))

    any_errors = any(r.n_errors > 0 for r in reports.values())
    return 1 if any_errors else 0


if __name__ == "__main__":
    sys.exit(main())
