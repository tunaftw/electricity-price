"""Tester för bess_dashboard_data — särskilt att ofullständiga dygn hoppas över.

Tidigare nollfylldes saknade timmar (``price_by_hour.get(h, 0.0)``), vilket lät
arbitrage-DP:n se 0 EUR/MWh-luckor som gratis laddningsläge och boka fantom-
intäkt. Nu ska bara kompletta UTC-dygn (timme 0..23) tas med.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris.bess_dashboard_data import _build_daily_prices  # noqa: E402


def _day(hours):
    """Bygg en spot-dygnslista {utc_hour, eur_mwh} för givna timmar."""
    return [{"utc_hour": h, "eur_mwh": float(h)} for h in hours]


def test_complete_day_included_with_24_ordered_prices():
    spot = {"2026-01-01": _day(range(24))}
    out = _build_daily_prices(spot)
    assert set(out) == {"2026-01-01"}
    assert out["2026-01-01"] == [float(h) for h in range(24)]


def test_partial_trailing_day_skipped():
    """Innevarande dag med bara timme 0..19 ska hoppas över."""
    spot = {"2026-01-02": _day(range(20))}
    assert _build_daily_prices(spot) == {}


def test_interior_gap_day_skipped():
    """Dygn med lucka mitt i (saknar timme 5) ska hoppas över — annars
    nollfylls timme 5 och DP:n bokar fantomintäkt."""
    hours = [h for h in range(24) if h != 5]
    spot = {"2026-01-03": _day(hours)}
    assert _build_daily_prices(spot) == {}


def test_only_complete_days_kept_in_mixed_input():
    spot = {
        "2026-01-01": _day(range(24)),    # komplett
        "2026-01-02": _day(range(20)),    # partiell
        "2026-01-03": _day(range(24)),    # komplett
    }
    out = _build_daily_prices(spot)
    assert set(out) == {"2026-01-01", "2026-01-03"}
