"""Tester för inverter_data — alarm-aggregering och MTBA."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris.inverter_data import AlarmEvent, aggregate_alarm_stats  # noqa: E402


def _event(day: str, name: str = "OverTemp") -> AlarmEvent:
    return AlarmEvent(
        inverter_name="INV01",
        event_name=name,
        event_code=1,
        description="",
        time_start_utc=f"2024-{day}T10:00:00Z",
        time_end_utc=f"2024-{day}T10:30:00Z",
        duration_min=30.0,
    )


def test_mtba_uses_actual_days_in_february_leap_year():
    """MTBA ska baseras på faktiska dagar i månaden (29 för feb 2024),
    inte hårdkodade 31 — annars överskattas tiden mellan alarm."""
    events = [_event("02-05"), _event("02-10")]  # 2 alarm i feb 2024

    stats = aggregate_alarm_stats(events, 2024, 2)

    # 29 dagar * 24h / 2 alarm = 348.0h  (inte 31*24/2 = 372.0)
    assert stats.avg_mtba_hours == 348.0


def test_mtba_uses_actual_days_in_31_day_month():
    """En 31-dagarsmånad ska ge 31*24/n som förut."""
    events = [_event("01-05"), _event("01-10")]  # 2 alarm i jan 2024

    stats = aggregate_alarm_stats(events, 2024, 1)

    assert stats.avg_mtba_hours == 372.0  # 31 * 24 / 2


def test_mtba_uses_actual_days_in_30_day_month():
    events = [_event("04-05"), _event("04-10")]  # 2 alarm i april 2024

    stats = aggregate_alarm_stats(events, 2024, 4)

    assert stats.avg_mtba_hours == 360.0  # 30 * 24 / 2
