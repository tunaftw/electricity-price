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

from elpris.config import parse_iso  # noqa: E402


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
