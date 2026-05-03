"""Tester för elpris.processing — tim → quarterly-konvertering."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris.processing import expand_hourly_to_quarterly, is_quarterly_data  # noqa: E402


# ---------------------------------------------------------------------------
# is_quarterly_data
# ---------------------------------------------------------------------------

def test_hourly_record_detected_as_not_quarterly():
    assert is_quarterly_data(
        "2025-06-01T00:00:00+02:00", "2025-06-01T01:00:00+02:00"
    ) is False


def test_quarterly_record_detected():
    assert is_quarterly_data(
        "2025-10-01T00:00:00+02:00", "2025-10-01T00:15:00+02:00"
    ) is True


# ---------------------------------------------------------------------------
# expand_hourly_to_quarterly
# ---------------------------------------------------------------------------

def _hourly(start: str, end: str, sek="0.5", eur="0.045", exr="11.1") -> dict:
    return {
        "time_start": start, "time_end": end,
        "SEK_per_kWh": sek, "EUR_per_kWh": eur, "EXR": exr,
    }


def test_hourly_expands_to_four_quarterly_records():
    rec = _hourly("2025-06-01T00:00:00+02:00", "2025-06-01T01:00:00+02:00")
    out = expand_hourly_to_quarterly(rec)

    assert len(out) == 4
    starts = [r["time_start"] for r in out]
    assert starts == [
        "2025-06-01T00:00:00+02:00",
        "2025-06-01T00:15:00+02:00",
        "2025-06-01T00:30:00+02:00",
        "2025-06-01T00:45:00+02:00",
    ]
    # All four hold the same prices
    for r in out:
        assert r["SEK_per_kWh"] == "0.5"
        assert r["EUR_per_kWh"] == "0.045"
        assert r["EXR"] == "11.1"


def test_quarterly_input_returns_unchanged_singleton():
    rec = _hourly("2025-10-01T00:00:00+02:00", "2025-10-01T00:15:00+02:00")
    out = expand_hourly_to_quarterly(rec)
    assert out == [rec]


def test_dst_spring_hour_expands_normally():
    """Spring DST: clocks go 02:00 → 03:00 in Stockholm. The 02:00 hour
    doesn't exist locally. Spotpris-CSV represents this with the local
    offset on the timestamp (no row at +01:00 02:00). Expansion math
    operates on tz-aware datetimes and shouldn't crash."""
    rec = _hourly("2025-03-30T03:00:00+02:00", "2025-03-30T04:00:00+02:00")
    out = expand_hourly_to_quarterly(rec)
    assert len(out) == 4
    assert out[0]["time_start"] == "2025-03-30T03:00:00+02:00"
    assert out[3]["time_start"] == "2025-03-30T03:45:00+02:00"


def test_dst_autumn_hour_expands_normally():
    """Autumn DST: clocks go 03:00 → 02:00 in Stockholm. Two distinct
    02:00 hours exist (one +02:00, one +01:00). Each gets its own
    expansion. Verify the second one expands cleanly."""
    rec = _hourly("2025-10-26T02:00:00+01:00", "2025-10-26T03:00:00+01:00")
    out = expand_hourly_to_quarterly(rec)
    assert len(out) == 4
    # All four sub-quarters retain the +01:00 offset (post-DST hour)
    for r in out:
        assert r["time_start"].endswith("+01:00")
