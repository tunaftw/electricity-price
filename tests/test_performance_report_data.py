"""Tester för performance_report_data.

1) Verkningsgrad (meter/inverter): täljare och nämnare måste summeras över
   IDENTISK intervalluppsättning — annars biasas KPI:t nedåt vid gles
   mätartäckning.
2) Förlustkaskaden: temperaturförlust mot klimatologi (anomali, inte 25 °C),
   clippingförlust bara när parken bevisligen ligger mot exportgränsen, och
   residualen = budget − actual − irr − avail − temp − clipping.
3) _aggregate_daily: riktig lufttemperatur från temperaturmappen — ingen
   påhittad 10 °C-konstant när data saknas (ärlig None).
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris.performance_report_data import (  # noqa: E402
    _aggregate_daily,
    _calculate_loss_cascade,
    _meter_inverter_efficiency,
)


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


# ---------------------------------------------------------------------------
# Förlustkaskaden — temperatur mot klimatologi + clipping mot exportgräns
# ---------------------------------------------------------------------------

_UTC = timezone.utc


def _interval(hour, minute, eff_mw, poa=None, avail=None):
    """Syntetisk 15-min-post i juli 2026 (UTC)."""
    ts = datetime(2026, 7, 15, hour, minute, tzinfo=_UTC)
    rec = {
        "timestamp_utc": ts,
        "date": ts.strftime("%Y-%m-%d"),
        "year": ts.year,
        "month": ts.month,
        "power_mw": eff_mw,
        "effective_power_mw": eff_mw,
    }
    if poa is not None:
        rec["irradiance_poa"] = poa
    if avail is not None:
        rec["availability"] = avail
    return rec


def _hour_key(hour):
    return datetime(2026, 7, 15, hour, 0, tzinfo=_UTC)


def _cascade(records, temp_map, climatology, *, budget=100.0,
             capacity_kwp=10_000.0, standard_pr=0.85,
             temp_coeff=-0.4, export_limit_mw=None,
             has_irradiance=False, has_availability=False,
             actual_irr=None, budget_irr=0.0):
    actual = sum(r["effective_power_mw"] * 0.25 for r in records)
    return _calculate_loss_cascade(
        budget_energy_mwh=budget,
        actual_energy_mwh=actual,
        budget_irr_kwh_m2=budget_irr,
        actual_irr_kwh_m2=actual_irr,
        capacity_kwp=capacity_kwp,
        standard_pr=standard_pr,
        records=records,
        has_irradiance=has_irradiance,
        has_availability=has_availability,
        temp_map=temp_map,
        climatology=climatology,
        temp_coeff_pct_per_c=temp_coeff,
        export_limit_mw=export_limit_mw,
    )


def test_temperature_loss_from_known_anomaly():
    """+5 °C mot klimatologin, γ=-0.4 %/°C, 4 MWh energi → 0.08 MWh förlust."""
    records = [
        _interval(12, m, 2.0) for m in (0, 15, 30, 45)
    ] + [
        _interval(13, m, 2.0) for m in (0, 15, 30, 45)
    ]
    temp_map = {_hour_key(12): 25.0, _hour_key(13): 25.0}
    clim = {7: 20.0}
    lc = _cascade(records, temp_map, clim)
    # (0.4/100) × 5 °C × 4 MWh = 0.08 MWh
    assert lc.temperature_loss_mwh == pytest.approx(0.08, abs=1e-6)
    # Residualen krymper med det vi förklarar
    assert lc.residual_loss_mwh == pytest.approx(100.0 - 4.0 - 0.08, abs=1e-6)


def test_temperature_gain_when_colder_than_normal():
    """Kallare än normalt → negativ temperaturpost (vinst)."""
    records = [_interval(12, m, 2.0) for m in (0, 15, 30, 45)]
    temp_map = {_hour_key(12): 15.0}
    clim = {7: 20.0}
    lc = _cascade(records, temp_map, clim)
    # (0.4/100) × (−5 °C) × 2 MWh = −0.04 MWh
    assert lc.temperature_loss_mwh == pytest.approx(-0.04, abs=1e-6)


def test_temperature_missing_hours_contribute_zero():
    """Timmar utan temperaturdata bidrar 0 — ingen påhittad konstant."""
    records = [
        _interval(12, m, 2.0) for m in (0, 15, 30, 45)
    ] + [
        _interval(13, m, 2.0) for m in (0, 15, 30, 45)
    ]
    temp_map = {_hour_key(12): 25.0}  # 13:00 saknas
    clim = {7: 20.0}
    lc = _cascade(records, temp_map, clim)
    assert lc.temperature_loss_mwh == pytest.approx(0.04, abs=1e-6)


def test_temperature_zero_without_climatology():
    records = [_interval(12, 0, 2.0)]
    lc = _cascade(records, {_hour_key(12): 25.0}, {})
    assert lc.temperature_loss_mwh == 0.0


def test_clipping_when_pegged_at_export_limit():
    """Pegged effekt + irr-förväntan över gränsen → känd clippingförlust."""
    # 10 MWp, gräns 7 MW. Förväntad gen vid POA 1000 W/m²:
    # 1000 × 0.25/1000 × 10000 × 0.85 / 1000 = 2.125 MWh > 7 × 0.25 = 1.75 MWh
    records = [
        _interval(12, 0, 7.0, poa=1000.0),    # pegged + över gräns → 0.375
        _interval(12, 15, 6.9, poa=1000.0),   # ≥ 0.97×7=6.79 → pegged → 0.375
        _interval(12, 30, 5.0, poa=1000.0),   # inte pegged → 0
        _interval(12, 45, 7.0),               # pegged men ingen POA → 0
        _interval(13, 0, 7.0, poa=500.0),     # pegged, förväntan 1.0625 < 1.75 → 0
    ]
    lc = _cascade(records, {}, {}, export_limit_mw=7.0, has_irradiance=True)
    assert lc.clipping_loss_mwh == pytest.approx(0.75, abs=1e-6)


def test_no_clipping_when_never_at_limit():
    records = [_interval(12, m, 3.0, poa=1000.0) for m in (0, 15, 30, 45)]
    lc = _cascade(records, {}, {}, export_limit_mw=7.0, has_irradiance=True)
    assert lc.clipping_loss_mwh == 0.0


def test_cascade_components_sum_to_budget_minus_actual():
    """Identiteten budget − actual = irr + avail + temp + clipping + residual."""
    records = [
        _interval(12, 0, 7.0, poa=1000.0, avail=0.9),
        _interval(12, 15, 2.0, poa=800.0, avail=1.0),
    ]
    temp_map = {_hour_key(12): 25.0}
    clim = {7: 20.0}
    lc = _cascade(
        records, temp_map, clim,
        export_limit_mw=7.0, has_irradiance=True, has_availability=True,
        actual_irr=100.0, budget_irr=120.0,
    )
    total = (
        lc.irradiance_shortfall_loss_mwh
        + lc.availability_loss_mwh
        + lc.temperature_loss_mwh
        + lc.clipping_loss_mwh
        + lc.residual_loss_mwh
    )
    assert total == pytest.approx(
        lc.budget_energy_mwh - lc.actual_energy_mwh, abs=1e-3)


# ---------------------------------------------------------------------------
# _aggregate_daily — riktig lufttemperatur, ärlig None
# ---------------------------------------------------------------------------

def test_daily_ambient_temp_from_map():
    records = [
        _interval(12, 0, 2.0, poa=800.0),
        _interval(13, 0, 2.0, poa=600.0),
    ]
    temp_map = {_hour_key(12): 20.0, _hour_key(13): 22.0}
    daily = _aggregate_daily(records, 10_000.0, 0.85, True, False, temp_map)
    assert len(daily) == 1
    d = daily[0]
    assert d.avg_ambient_temp_c == pytest.approx(21.0, abs=0.1)
    # T_mod = T_amb + 0.03 × POA per intervall: (20+24 + 22+18)/2 = 42.0
    assert d.avg_module_temp_c == pytest.approx(42.0, abs=0.1)


def test_daily_temps_none_without_temperature_data():
    """Ingen temperaturdata → None, inte 10 °C."""
    records = [_interval(12, 0, 2.0, poa=800.0)]
    daily = _aggregate_daily(records, 10_000.0, 0.85, True, False, {})
    assert daily[0].avg_ambient_temp_c is None
    assert daily[0].avg_module_temp_c is None


def test_default_ambient_constant_removed():
    import elpris.performance_report_data as prd
    assert not hasattr(prd, "_DEFAULT_AMBIENT_TEMP_C")
