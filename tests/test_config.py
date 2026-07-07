"""Tester för elpris.config — delad ISO-parser (parse_iso).

datetime.fromisoformat('...Z') kastar ValueError på Python 3.9 (men inte 3.11).
parse_iso normaliserar 'Z' -> '+00:00' så Z-suffixad data (t.ex. eSett) parsas
konsekvent istället för att krascha eller tyst droppas.
"""

from __future__ import annotations

import sys
from datetime import timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris.config import SWEDEN_TZ, local_year_month, parse_iso  # noqa: E402


def test_parse_iso_handles_z_suffix():
    ts = parse_iso("2024-01-01T00:00:00Z")
    assert ts.year == 2024 and ts.hour == 0
    assert ts.utcoffset() == timezone.utc.utcoffset(None)


def test_parse_iso_handles_explicit_offset():
    ts = parse_iso("2024-06-01T10:00:00+02:00")
    assert ts.hour == 10
    assert ts.utcoffset().total_seconds() == 2 * 3600


def test_parse_iso_handles_naive():
    ts = parse_iso("2024-01-01T00:00:00")
    assert ts.tzinfo is None
    assert ts.year == 2024


# ---------------------------------------------------------------------------
# local_year_month — bucketa månader på svensk lokaltid, inte UTC
# ---------------------------------------------------------------------------

def test_local_year_month_summer_boundary_rolls_to_next_month():
    """2026-03-31 22:30 UTC = 2026-04-01 00:30 CEST (UTC+2) -> april, inte mars."""
    ts = parse_iso("2026-03-31T22:30:00Z")
    assert local_year_month(ts) == (2026, 4)


def test_local_year_month_winter_boundary_rolls_to_next_month():
    """2026-01-31 23:30 UTC = 2026-02-01 00:30 CET (UTC+1) -> februari."""
    ts = parse_iso("2026-01-31T23:30:00Z")
    assert local_year_month(ts) == (2026, 2)


def test_local_year_month_midday_unchanged():
    ts = parse_iso("2026-06-15T10:00:00Z")
    assert local_year_month(ts) == (2026, 6)
