#!/usr/bin/env python3
"""Är gårdagen komplett i alla källor? Skriver JSON och ger exitkod 0 (ja) eller 1 (nej).

    python scripts/datastatus_klar.py
    python scripts/datastatus_klar.py --idag 2026-10-02

Används av scripts/windows/elpris_sync.ps1. Reglerna finns i elpris/datastatus.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from elpris.config import SWEDEN_TZ  # noqa: E402
from elpris.datastatus import kontrollera, standardkallor  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--idag", type=date.fromisoformat, default=None,
                        help="Dagens datum (standard: idag i svensk tid)")
    args = parser.parse_args()
    idag = args.idag or datetime.now(SWEDEN_TZ).date()
    hamtare, temperatur = standardkallor()
    resultat = kontrollera(idag, hamtare, temperatur)
    print(json.dumps(resultat, ensure_ascii=False))
    return 0 if resultat["komplett"] else 1


if __name__ == "__main__":
    sys.exit(main())
