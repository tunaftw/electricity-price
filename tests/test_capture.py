"""Tester för elpris.capture — capture price-formel."""

from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris import capture, solar_profile  # noqa: E402


@pytest.fixture
def fake_quarterly(tmp_path, monkeypatch):
    """Inject a fake QUARTERLY_DIR with controllable CSV content."""
    monkeypatch.setattr(capture, "QUARTERLY_DIR", tmp_path)
    return tmp_path


def _write_quarterly(base: Path, zone: str, year: int, rows: list[dict]) -> None:
    zone_dir = base / zone
    zone_dir.mkdir(parents=True, exist_ok=True)
    csv_path = zone_dir / f"{year}.csv"
    fields = list(rows[0].keys())
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _row(ts: str, sek: float) -> dict:
    return {
        "time_start": ts, "time_end": ts,  # time_end unused by capture
        "SEK_per_kWh": str(sek),
        "EUR_per_kWh": str(sek / 11.0),
        "EXR": "11.0",
    }


# ---------------------------------------------------------------------------
# Empty / no-data behavior
# ---------------------------------------------------------------------------

def test_capture_no_data_returns_none(fake_quarterly):
    result = capture.calculate_capture_price("SE3")
    assert result["capture_price"] is None
    assert result["average_price"] is None
    assert result["record_count"] == 0


# ---------------------------------------------------------------------------
# Weighting math
# ---------------------------------------------------------------------------

def test_capture_equals_average_when_all_solar_weights_uniform(monkeypatch, fake_quarterly):
    """If solar weight is constant, capture = average price."""
    # Force constant solar weight regardless of timestamp
    monkeypatch.setattr(capture, "get_quarterly_solar_weight",
                        lambda ts, profile: 1.0)

    rows = [
        _row("2025-06-01T10:00:00+02:00", 0.4),
        _row("2025-06-01T11:00:00+02:00", 0.6),
        _row("2025-06-01T12:00:00+02:00", 0.5),
    ]
    _write_quarterly(fake_quarterly, "SE3", 2025, rows)

    result = capture.calculate_capture_price("SE3")
    assert result["record_count"] == 3
    assert result["average_price"] == pytest.approx(0.5)
    assert result["capture_price"] == pytest.approx(0.5)
    assert result["capture_ratio"] == pytest.approx(1.0)


def test_capture_lower_than_average_when_solar_weights_low_priced_hours(monkeypatch, fake_quarterly):
    """Classic solar capture: production peaks at midday when prices are
    lowest → capture < average."""
    weights = {
        "2025-06-01T08:00:00+02:00": 0.0,   # high price, no sun
        "2025-06-01T13:00:00+02:00": 1.0,   # low price, peak sun
        "2025-06-01T20:00:00+02:00": 0.0,   # high price, no sun
    }
    monkeypatch.setattr(capture, "get_quarterly_solar_weight",
                        lambda ts, profile: weights[ts.isoformat()])

    rows = [
        _row("2025-06-01T08:00:00+02:00", 1.0),
        _row("2025-06-01T13:00:00+02:00", 0.2),
        _row("2025-06-01T20:00:00+02:00", 1.0),
    ]
    _write_quarterly(fake_quarterly, "SE3", 2025, rows)

    result = capture.calculate_capture_price("SE3")
    assert result["average_price"] == pytest.approx(2.2 / 3)
    # Only the 13:00 hour weighted in: capture = 0.2
    assert result["capture_price"] == pytest.approx(0.2)
    assert result["capture_ratio"] < 0.4


def test_capture_handles_zero_total_weight_without_dividing(monkeypatch, fake_quarterly):
    """If solar weight is zero everywhere (e.g. winter night data only),
    function should NOT divide by zero — capture stays 0."""
    monkeypatch.setattr(capture, "get_quarterly_solar_weight",
                        lambda ts, profile: 0.0)

    _write_quarterly(fake_quarterly, "SE3", 2025, [
        _row("2025-12-21T00:00:00+01:00", 0.5),
        _row("2025-12-21T01:00:00+01:00", 0.5),
    ])

    result = capture.calculate_capture_price("SE3")
    assert result["capture_price"] == 0  # falls through to fallback
    assert result["average_price"] == pytest.approx(0.5)


def test_capture_handles_negative_prices(monkeypatch, fake_quarterly):
    """Negative spotpriser ska inte specialhanteras — formeln är linjär.
    Capture mot solviktning ska kunna gå negativt om vi får betalt minus
    under produktion."""
    monkeypatch.setattr(capture, "get_quarterly_solar_weight",
                        lambda ts, profile: 1.0)

    _write_quarterly(fake_quarterly, "SE3", 2025, [
        _row("2025-06-01T10:00:00+02:00", -0.1),
        _row("2025-06-01T11:00:00+02:00", -0.2),
        _row("2025-06-01T12:00:00+02:00",  0.6),
    ])

    result = capture.calculate_capture_price("SE3")
    assert result["average_price"] == pytest.approx(0.3 / 3)
    assert result["capture_price"] == pytest.approx(0.3 / 3)


# ---------------------------------------------------------------------------
# Date filtering
# ---------------------------------------------------------------------------

def test_capture_respects_start_date(monkeypatch, fake_quarterly):
    monkeypatch.setattr(capture, "get_quarterly_solar_weight",
                        lambda ts, profile: 1.0)
    _write_quarterly(fake_quarterly, "SE3", 2025, [
        _row("2025-06-01T10:00:00+02:00", 1.0),  # excluded
        _row("2025-06-15T10:00:00+02:00", 0.5),  # included
        _row("2025-06-30T10:00:00+02:00", 0.5),  # included
    ])

    result = capture.calculate_capture_price(
        "SE3", start_date=date(2025, 6, 10), end_date=date(2025, 6, 30)
    )
    assert result["record_count"] == 2
    assert result["average_price"] == pytest.approx(0.5)


def test_calculate_capture_by_period_groups_correctly(monkeypatch, fake_quarterly):
    monkeypatch.setattr(capture, "get_quarterly_solar_weight",
                        lambda ts, profile: 1.0)
    _write_quarterly(fake_quarterly, "SE3", 2025, [
        _row("2025-05-15T12:00:00+02:00", 0.4),
        _row("2025-05-16T12:00:00+02:00", 0.6),
        _row("2025-06-15T12:00:00+02:00", 1.0),
    ])

    results = capture.calculate_capture_by_period("SE3", period="month")
    by_month = {r["period"]: r for r in results}
    assert by_month["2025-05"]["records"] == 2
    assert by_month["2025-06"]["records"] == 1
    assert by_month["2025-05"]["average_price_sek"] == pytest.approx(0.5)
    assert by_month["2025-06"]["average_price_sek"] == pytest.approx(1.0)
