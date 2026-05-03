"""Tester för elpris.storage — CSV-läs/skriv för spotpriser."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris import storage  # noqa: E402


# ---------------------------------------------------------------------------
# Test fixtures: build a fake RAW_DIR via monkeypatch
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_raw(tmp_path, monkeypatch):
    """Replace storage.RAW_DIR with an empty tmp dir for isolation."""
    monkeypatch.setattr(storage, "RAW_DIR", tmp_path)
    return tmp_path


def _write_zone_year(base: Path, zone: str, year: int, rows: list[dict]) -> Path:
    zone_dir = base / zone
    zone_dir.mkdir(parents=True, exist_ok=True)
    csv_path = zone_dir / f"{year}.csv"
    fields = list(rows[0].keys()) if rows else ["time_start"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return csv_path


# ---------------------------------------------------------------------------
# get_latest_timestamp
# ---------------------------------------------------------------------------

def test_latest_timestamp_returns_none_when_no_data(fake_raw):
    assert storage.get_latest_timestamp("SE3") is None


def test_latest_timestamp_returns_last_row(fake_raw):
    _write_zone_year(fake_raw, "SE3", 2025, [
        {"time_start": "2025-01-01T00:00:00+01:00"},
        {"time_start": "2025-01-01T01:00:00+01:00"},
        {"time_start": "2025-01-01T02:00:00+01:00"},
    ])
    ts = storage.get_latest_timestamp("SE3")
    assert ts.isoformat() == "2025-01-01T02:00:00+01:00"


def test_latest_timestamp_falls_back_to_previous_year_when_latest_empty(fake_raw):
    """B5 fix: empty year file should not mask older data.

    Without the fix, an empty 2025.csv (header only) caused the function
    to return None and trigger a full re-download of all of 2024.
    """
    _write_zone_year(fake_raw, "SE3", 2024, [
        {"time_start": "2024-12-31T22:00:00+01:00"},
        {"time_start": "2024-12-31T23:00:00+01:00"},
    ])
    # 2025: header only, no rows
    _write_zone_year(fake_raw, "SE3", 2025, [])

    ts = storage.get_latest_timestamp("SE3")
    assert ts is not None
    assert ts.isoformat() == "2024-12-31T23:00:00+01:00"


def test_latest_timestamp_picks_newest_year_when_both_have_data(fake_raw):
    _write_zone_year(fake_raw, "SE3", 2024, [
        {"time_start": "2024-12-31T23:00:00+01:00"},
    ])
    _write_zone_year(fake_raw, "SE3", 2025, [
        {"time_start": "2025-01-01T00:00:00+01:00"},
    ])

    ts = storage.get_latest_timestamp("SE3")
    assert ts.isoformat() == "2025-01-01T00:00:00+01:00"


# ---------------------------------------------------------------------------
# find_data_gaps
# ---------------------------------------------------------------------------

def test_find_data_gaps_empty_zone_returns_empty_list(fake_raw):
    assert storage.find_data_gaps("SE3") == []


def test_find_data_gaps_no_gaps_in_contiguous_data(fake_raw):
    _write_zone_year(fake_raw, "SE3", 2025, [
        {"time_start": "2025-01-01T00:00:00+01:00"},
        {"time_start": "2025-01-01T01:00:00+01:00"},
        {"time_start": "2025-01-01T02:00:00+01:00"},
    ])
    assert storage.find_data_gaps("SE3", max_gap_hours=2) == []


def test_find_data_gaps_detects_multi_day_gap(fake_raw):
    _write_zone_year(fake_raw, "SE3", 2024, [
        {"time_start": "2024-12-14T22:00:00+01:00"},
        {"time_start": "2024-12-14T23:00:00+01:00"},
        # 16 days missing here
        {"time_start": "2024-12-31T00:00:00+01:00"},
    ])
    gaps = storage.find_data_gaps("SE3", max_gap_hours=2)
    assert len(gaps) == 1
    gap_start, gap_end = gaps[0]
    assert gap_start.isoformat() == "2024-12-14T23:00:00+01:00"
    assert gap_end.isoformat() == "2024-12-31T00:00:00+01:00"


def test_find_data_gaps_tolerates_dst_spring_jump(fake_raw):
    """Spring DST = 1h forward jump. Should NOT be flagged as a gap
    when threshold is 2h."""
    _write_zone_year(fake_raw, "SE3", 2025, [
        # Last hour before DST jump
        {"time_start": "2025-03-30T01:00:00+01:00"},
        # First hour after — local 03:00 = +02:00 offset, but UTC progresses 1h
        {"time_start": "2025-03-30T03:00:00+02:00"},
    ])
    assert storage.find_data_gaps("SE3", max_gap_hours=2) == []


def test_find_data_gaps_spans_year_boundary(fake_raw):
    _write_zone_year(fake_raw, "SE3", 2024, [
        {"time_start": "2024-12-31T22:00:00+01:00"},
        {"time_start": "2024-12-31T23:00:00+01:00"},
    ])
    _write_zone_year(fake_raw, "SE3", 2025, [
        # 5 day gap straddling new year
        {"time_start": "2025-01-05T00:00:00+01:00"},
    ])
    gaps = storage.find_data_gaps("SE3", max_gap_hours=2)
    assert len(gaps) == 1
    assert gaps[0][0].date().isoformat() == "2024-12-31"
    assert gaps[0][1].date().isoformat() == "2025-01-05"


# ---------------------------------------------------------------------------
# append_day_data round-trip
# ---------------------------------------------------------------------------

def test_append_day_data_writes_header_first_time(fake_raw, monkeypatch):
    from datetime import date
    from elpris.config import CSV_FIELDS

    rec = {
        "time_start": "2025-06-01T00:00:00+02:00",
        "time_end": "2025-06-01T01:00:00+02:00",
        "SEK_per_kWh": "0.5",
        "EUR_per_kWh": "0.045",
        "EXR": "11.1",
    }
    storage.append_day_data("SE3", date(2025, 6, 1), [rec])
    csv_path = fake_raw / "SE3" / "2025.csv"
    assert csv_path.exists()
    with open(csv_path, encoding="utf-8") as f:
        lines = f.readlines()
    # Header + one data row
    assert len(lines) == 2
    assert lines[0].strip().split(",") == CSV_FIELDS
