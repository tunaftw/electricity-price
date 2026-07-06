"""Tester för performance_report_data — verkningsgrad (meter/inverter).

Buggen: täljare (meter) och nämnare (inverter) summerades över OLIKA
intervalluppsättningar — nämnaren inkluderade intervall där inverter fanns men
mätaren var 0/negativ, täljaren inte. Det biasar KPI:t nedåt vid gles
mätartäckning. Fixen: identisk intervalluppsättning för båda.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris.performance_report_data import _meter_inverter_efficiency  # noqa: E402


def _rec(active, meter):
    return {"active_power_mw": active, "power_mw": meter}


def test_efficiency_over_identical_intervals():
    """Meter strax under inverter → ~97 %."""
    recs = [_rec(10.0, 9.8), _rec(10.0, 9.6)]
    assert _meter_inverter_efficiency(recs) == 97.0


def test_zero_meter_interval_not_asymmetrically_biasing():
    """Intervall med inverteroutput men mätaren = 0 (mätarfel) ska uteslutas
    ur BÅDE täljare och nämnare — inte bara täljaren. Annars nollas KPI:t."""
    recs = [_rec(10.0, 9.5), _rec(10.0, 0.0)]
    # Gammalt (buggigt): inv=20, meter=9.5 -> 47.5% -> None (utanför 50-105)
    # Nytt: det andra intervallet utesluts ur båda -> inv=10, meter=9.5 -> 95%
    assert _meter_inverter_efficiency(recs) == 95.0


def test_efficiency_none_when_no_valid_intervals():
    recs = [_rec(None, 5.0), _rec(10.0, 0.0)]
    assert _meter_inverter_efficiency(recs) is None


def test_efficiency_none_when_out_of_sanity_range():
    """Meter >> inverter → data broken → None."""
    recs = [_rec(10.0, 20.0)]
    assert _meter_inverter_efficiency(recs) is None


def test_efficiency_none_when_below_floor():
    recs = [_rec(10.0, 4.0)]  # 40% < 50% golv
    assert _meter_inverter_efficiency(recs) is None
