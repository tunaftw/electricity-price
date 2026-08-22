"""Enhetstester för elpris.insikt.obalans (realiserad obalanskostnad).

Alla tester använder syntetisk data — inga filberoenden. Valideringspunkter
från spec:en:

1. prognos == faktisk → kostnad exakt 0.
2. känd avvikelse × kända priser → handräknad kostnad.
3. tidszonsjoin: eSett (UTC "Z") + spot (lokal offset) + park (UTC) möts
   på exakt samma kvart.
4. enprismodell: vinst (negativ kostnad) är möjlig när obalansen ligger i
   "rätt" riktning; brutto tar absolutbelopp per kvart.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from elpris.insikt.obalans import (
    budget_shape_forecast,
    energies_from_records,
    interval_cost,
    persistence_forecast,
    settle_monthly,
)

UTC = ZoneInfo("UTC")
SE = ZoneInfo("Europe/Stockholm")


def _utc(y, mo, d, h=0, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=UTC)


# ---------------------------------------------------------------------------
# interval_cost — sign-konventioner (hjärtat i avräkningen)
# ---------------------------------------------------------------------------

def test_interval_cost_zero_when_prices_equal_spot():
    # Obalanspris == spot → prognosfel kostar inget, oavsett riktning.
    assert interval_cost(0.5, 50.0, 50.0, 50.0) == 0.0
    assert interval_cost(-0.5, 50.0, 50.0, 50.0) == 0.0


def test_interval_cost_surplus_sold_below_spot():
    # Producerade 0,5 MWh mer än nominerat; överskott säljs till 40 i
    # stället för spot 50 → kostnad 0,5 × (50 − 40) = 5 €.
    assert interval_cost(0.5, 50.0, 40.0, 60.0) == pytest.approx(5.0)


def test_interval_cost_deficit_bought_above_spot():
    # Producerade 0,5 MWh mindre; underskott köps till 60 mot spot 50
    # → kostnad 0,5 × (60 − 50) = 5 €.
    assert interval_cost(-0.5, 50.0, 40.0, 60.0) == pytest.approx(5.0)


def test_interval_cost_can_be_negative_profit():
    # Enprismodell, systemet kort: sales 60 > spot 50. Överskott i rätt
    # riktning ger VINST: 0,5 × (50 − 60) = −5 €.
    assert interval_cost(0.5, 50.0, 60.0, 60.0) == pytest.approx(-5.0)


def test_interval_cost_zero_diff():
    assert interval_cost(0.0, 50.0, 10.0, 90.0) == 0.0


# ---------------------------------------------------------------------------
# energies_from_records — nattproduktionsvakt (stuck inverter + POA ≈ 0)
# ---------------------------------------------------------------------------

def _rec(ts, effective, power=0.0, poa=None):
    rec = {"timestamp_utc": ts, "power_mw": power,
           "effective_power_mw": effective}
    if poa is not None:
        rec["irradiance_poa"] = poa
    return rec


def test_energies_night_guard_zeroes_stuck_inverter():
    # Mätare saknas, invertervärde 4.28 MW fast POA = 0 → fysiskt omöjligt
    # för sol → energi 0 (björke 2025-03-22-fallet).
    t = _utc(2025, 3, 22, 21, 15)
    energies = energies_from_records([_rec(t, 4.2781, power=0.0, poa=0.0)])
    assert energies[t] == 0.0


def test_energies_night_guard_trusts_meter():
    # Mätarsignal finns → ingen vakt, även med POA 0 (mätaren är facit).
    t = _utc(2025, 3, 22, 12, 0)
    energies = energies_from_records([_rec(t, 3.0, power=3.0, poa=0.0)])
    assert energies[t] == pytest.approx(3.0 * 0.25)


def test_energies_night_guard_keeps_daylight_inverter():
    # Inverter-fallback med dagsljus-POA → behålls (MW × 0,25 h = MWh).
    t = _utc(2025, 3, 22, 12, 0)
    energies = energies_from_records([_rec(t, 3.0, power=0.0, poa=450.0)])
    assert energies[t] == pytest.approx(0.75)


def test_energies_night_guard_no_poa_passthrough():
    # Utan POA-data kan vakten inte avgöra → värdet behålls.
    t = _utc(2025, 3, 22, 21, 15)
    energies = energies_from_records([_rec(t, 0.5, power=0.0)])
    assert energies[t] == pytest.approx(0.125)


# ---------------------------------------------------------------------------
# persistence_forecast — D-1 samma kvart
# ---------------------------------------------------------------------------

def test_persistence_uses_same_quarter_previous_day():
    t0 = _utc(2024, 6, 1, 10, 0)
    t1 = t0 + timedelta(days=1)
    energies = {t0: 1.25, t1: 0.75}
    fc = persistence_forecast(energies)
    # Dag 1 saknar D-1 → hoppas över. Dag 2 prognosen = dag 1-värdet.
    assert t0 not in fc
    assert fc[t1] == pytest.approx(1.25)


# ---------------------------------------------------------------------------
# budget_shape_forecast — månadens dygnsform skalad till budgetenergi
# ---------------------------------------------------------------------------

def _identical_days_month(daily_shape, year=2024, month=6, n_days=30):
    """Bygg en månad där varje dag har exakt samma form (lokal tid)."""
    energies = {}
    for d in range(1, n_days + 1):
        for qod, e in daily_shape.items():
            h, mi = divmod(qod * 15, 60)
            local = datetime(year, month, d, h, mi, tzinfo=SE)
            energies[local.astimezone(UTC)] = e
    return energies


def test_budget_shape_equals_actual_when_budget_matches():
    # Identiska dagar + budget == faktisk månadsenergi → prognos == faktisk.
    shape = {40: 0.2, 41: 0.4, 42: 0.4, 43: 0.2}  # kl 10:00–11:00 lokal
    energies = _identical_days_month(shape)
    total = sum(energies.values())
    fc = budget_shape_forecast(energies, {"2024-06": total})
    assert set(fc) == set(energies)
    for ts, e in energies.items():
        assert fc[ts] == pytest.approx(e)


def test_budget_shape_scales_to_budget_energy():
    # Budget = 2 × faktisk → prognosen dubbleras kvart för kvart.
    shape = {40: 0.3, 41: 0.5}
    energies = _identical_days_month(shape)
    total = sum(energies.values())
    fc = budget_shape_forecast(energies, {"2024-06": 2.0 * total})
    for ts, e in energies.items():
        assert fc[ts] == pytest.approx(2.0 * e)
    assert sum(fc.values()) == pytest.approx(2.0 * total)


def test_budget_shape_skips_month_without_budget():
    energies = _identical_days_month({40: 0.5})
    assert budget_shape_forecast(energies, {}) == {}


# ---------------------------------------------------------------------------
# settle_monthly — join, månadsbucketing, brutto/netto, täckning
# ---------------------------------------------------------------------------

def test_settle_monthly_hand_computed_example():
    """Tidszonsjoin + handräknad kostnad på en enda kvart.

    Park (UTC), spot (lokal CEST-offset) och eSett (Z-suffix parsad till
    UTC) refererar alla samma ögonblick: 2024-06-02 10:00 UTC
    = 2024-06-02 12:00 lokal svensk sommartid.
    """
    t_d1 = _utc(2024, 6, 1, 10, 0)   # D-1: ger persistensprognos
    t = _utc(2024, 6, 2, 10, 0)

    energies = {t_d1: 1.0, t: 1.5}   # diff_a = 1.5 − 1.0 = +0.5 MWh
    fc_a = persistence_forecast(energies)
    fc_b = {t_d1: 1.0, t: 2.0}       # diff_b = 1.5 − 2.0 = −0.5 MWh

    # Spot definierad från lokal tid — samma instant som t.
    local = datetime(2024, 6, 2, 12, 0, tzinfo=SE)
    assert local.astimezone(UTC) == t
    spot = {local.astimezone(UTC): 50.0, t_d1: 50.0}
    prices = {t: (40.0, 60.0), t_d1: (50.0, 50.0)}

    monthly = settle_monthly(energies, fc_a, fc_b, spot, prices)
    assert len(monthly) == 1
    row = monthly[0]
    assert row["month"] == "2024-06"
    # Endast t utvärderas (t_d1 saknar persistensprognos).
    assert row["n"] == 1
    # kostnad a: +0.5 × (50 − 40) = 5 €
    assert row["cost_eur_a"] == pytest.approx(5.0)
    # kostnad b: |−0.5| × (60 − 50) = 5 €
    assert row["cost_eur_b"] == pytest.approx(5.0)
    assert row["gross_a"] == pytest.approx(5.0)
    assert row["volume_mwh"] == pytest.approx(1.5)
    assert row["cost_per_mwh_a"] == pytest.approx(5.0 / 1.5, abs=1e-3)


def test_settle_monthly_perfect_forecast_costs_zero():
    # prognos == faktisk för båda proxies → netto och brutto exakt 0.
    ts = [_utc(2024, 6, d, 10, 0) for d in range(1, 11)]
    energies = {t: 1.0 for t in ts}
    fc = dict(energies)
    spot = {t: 45.0 for t in ts}
    prices = {t: (30.0, 70.0) for t in ts}
    monthly = settle_monthly(energies, fc, fc, spot, prices)
    assert monthly[0]["cost_eur_a"] == 0.0
    assert monthly[0]["cost_eur_b"] == 0.0
    assert monthly[0]["gross_a"] == 0.0
    assert monthly[0]["gross_b"] == 0.0


def test_settle_monthly_net_vs_gross():
    # Två kvartar: +5 € och −5 € → netto 0, brutto 10.
    t1, t2 = _utc(2024, 6, 2, 10, 0), _utc(2024, 6, 2, 10, 15)
    energies = {t1: 1.5, t2: 1.5}
    fc = {t1: 1.0, t2: 1.0}          # diff = +0.5 båda
    spot = {t1: 50.0, t2: 50.0}
    prices = {t1: (40.0, 40.0), t2: (60.0, 60.0)}
    monthly = settle_monthly(energies, fc, fc, spot, prices)
    row = monthly[0]
    assert row["cost_eur_a"] == pytest.approx(0.0)
    assert row["gross_a"] == pytest.approx(10.0)


def test_settle_monthly_skips_unmatched_quarters():
    # Kvart utan spot- eller eSett-match utvärderas inte.
    t1, t2, t3 = (_utc(2024, 6, 2, 10, q * 15) for q in range(3))
    energies = {t1: 1.0, t2: 1.0, t3: 1.0}
    fc = {t1: 1.0, t2: 1.0, t3: 1.0}
    spot = {t1: 50.0, t2: 50.0}              # t3 saknar spot
    prices = {t1: (50.0, 50.0), t3: (50.0, 50.0)}  # t2 saknar eSett
    monthly = settle_monthly(energies, fc, fc, spot, prices)
    assert monthly[0]["n"] == 1


def test_settle_monthly_months_bucketed_in_local_time():
    # 2024-06-30 23:00 UTC = 2024-07-01 01:00 lokal → bokförs på juli.
    t = _utc(2024, 6, 30, 23, 0)
    energies = {t: 1.0}
    fc = {t: 0.5}
    spot = {t: 50.0}
    prices = {t: (50.0, 50.0)}
    monthly = settle_monthly(energies, fc, fc, spot, prices)
    assert monthly[0]["month"] == "2024-07"


def test_settle_monthly_coverage_pct():
    # Juni 2024 har 30 × 96 = 2880 kvartar; 1 utvärderad → ~0,03 %.
    t_d1 = _utc(2024, 6, 1, 10, 0)
    t = _utc(2024, 6, 2, 10, 0)
    energies = {t_d1: 1.0, t: 1.0}
    fc_a = persistence_forecast(energies)
    fc_b = {t_d1: 1.0, t: 1.0}
    spot = {t: 50.0, t_d1: 50.0}
    prices = {t: (50.0, 50.0), t_d1: (50.0, 50.0)}
    monthly = settle_monthly(energies, fc_a, fc_b, spot, prices)
    row = monthly[0]
    assert row["n"] == 1
    assert row["coverage_pct"] == pytest.approx(100.0 / 2880, abs=0.01)


def test_settle_monthly_single_price_share():
    t1, t2 = _utc(2024, 6, 2, 10, 0), _utc(2024, 6, 2, 10, 15)
    energies = {t1: 1.0, t2: 1.0}
    fc = {t1: 0.5, t2: 0.5}
    spot = {t1: 50.0, t2: 50.0}
    prices = {t1: (40.0, 40.0), t2: (40.0, 60.0)}  # en enpris, en tvåpris
    monthly = settle_monthly(energies, fc, fc, spot, prices)
    assert monthly[0]["single_price_share_pct"] == pytest.approx(50.0)
