"""Enhetstester för rework-dashboardens rena analysfunktioner.

Alla tester använder syntetisk data — inga filberoenden — så de är
snabba och kan köras i CI utan Resultat/-katalogen.
"""

import pytest

from elpris.rework_capture_analysis import (
    aggregate_installed_solar,
    aggregate_installed_wind,
    calculate_orientation_yearly,
)
from elpris.rework_dashboard_data import (
    prune_capture_data,
    prune_forward,
)
from elpris.rework_imbalance import aggregate_imbalance_monthly
from elpris.rework_market_analysis import (
    analyze_zone_quarters,
    calculate_zone_spreads,
)
from elpris.rework_portfolio import (
    _front_year_label,
    build_fleet_series,
    build_insights,
    fmt_num,
    fmt_signed_pct,
)


# ---------------------------------------------------------------------------
# build_insights — intradagsspread-trend får inte jämföra partiellt år
# ---------------------------------------------------------------------------

def _spread_insight(insights):
    """Plocka ut ev. intradagsspread-insikt ur marknads-sektionen."""
    return [
        i for i in insights["marknad"]
        if "Intradagsspreaden" in i["text"]
    ]


def _market_analysis_with_spreads(yearly):
    return {"zones": {"SE3": {"yearly": yearly, "monthly": []}}}


def test_spread_insight_compares_complete_years_not_partial():
    """Innevarande partiella år är säsongsskevt (vinter-tungt) och får inte
    jämföras som strukturell trend. Insikten ska jämföra de två senaste
    HELA åren."""
    yearly = [
        {"year": 2024, "intraday_spread": 20.0, "complete": True, "avg": 40},
        {"year": 2025, "intraday_spread": 30.0, "complete": True, "avg": 45},
        {"year": 2026, "intraday_spread": 12.0, "complete": False, "avg": 30},
    ]
    insights = build_insights(
        {}, _market_analysis_with_spreads(yearly), {}, {}, {}, {}, "SE3"
    )
    spread = _spread_insight(insights)
    assert len(spread) == 1
    # Jämför 2024 (20) → 2025 (30): vidgas — inte "krymper" mot partiella 2026
    assert "vidgas" in spread[0]["text"]
    assert "2025" in spread[0]["text"] and "2024" in spread[0]["text"]
    assert "2026" not in spread[0]["text"]


def test_spread_insight_suppressed_without_two_complete_years():
    """Med bara ett helt år (+ partiella) finns ingen trend att uttala sig om."""
    yearly = [
        {"year": 2025, "intraday_spread": 30.0, "complete": True, "avg": 45},
        {"year": 2026, "intraday_spread": 12.0, "complete": False, "avg": 30},
    ]
    insights = build_insights(
        {}, _market_analysis_with_spreads(yearly), {}, {}, {}, {}, "SE3"
    )
    assert _spread_insight(insights) == []


# ---------------------------------------------------------------------------
# rework_market_analysis
# ---------------------------------------------------------------------------

def _make_quarter_rows(day: str, price_by_hour, tz: str = "+02:00"):
    """Bygg 96 kvartersrader för en dag med pris per timme (EUR/MWh)."""
    rows = []
    for hour in range(24):
        price_eur_mwh = price_by_hour(hour)
        for q in range(4):
            rows.append({
                "time_start": f"{day}T{hour:02d}:{q*15:02d}:00{tz}",
                "EUR_per_kWh": str(price_eur_mwh / 1000.0),
            })
    return rows


def test_analyze_zone_quarters_basic():
    rows = _make_quarter_rows("2024-06-01", lambda h: float(h))
    rows += _make_quarter_rows("2024-06-02", lambda h: float(h))
    result = analyze_zone_quarters(rows)

    assert len(result["yearly"]) == 1
    y = result["yearly"][0]
    assert y["year"] == 2024
    assert y["avg"] == pytest.approx(11.5, abs=0.01)
    assert y["neg_hours"] == 0.0
    # Timmedel 0..23 → spread 23
    assert y["intraday_spread"] == pytest.approx(23.0, abs=0.01)
    assert y["complete"] is False  # bara 2 dagar

    assert len(result["monthly"]) == 1
    m = result["monthly"][0]
    assert m["month"] == "2024-06"
    assert m["avg_daily_spread"] == pytest.approx(23.0, abs=0.01)
    assert result["last_ts"] == "2024-06-02T23:45:00+02:00"


def test_analyze_zone_quarters_negative_hours():
    # 4 kvarter med negativt pris = 1.0 negativa timmar
    rows = _make_quarter_rows(
        "2024-07-01", lambda h: -5.0 if h == 13 else 20.0
    )
    result = analyze_zone_quarters(rows)
    assert result["yearly"][0]["neg_hours"] == 1.0
    assert result["monthly"][0]["neg_hours"] == 1.0


def test_analyze_zone_quarters_duck_curve_local_time():
    rows = _make_quarter_rows("2024-06-01", lambda h: float(h * 2))
    result = analyze_zone_quarters(rows)
    duck = result["duck_by_year"]["2024"]
    assert duck[0] == pytest.approx(0.0)
    assert duck[12] == pytest.approx(24.0)
    # month_hour: juni = index 5
    mh = result["month_hour_by_year"]["2024"]
    assert mh[5][12] == pytest.approx(24.0)
    assert mh[0][12] is None  # januari saknar data


def test_calculate_zone_spreads():
    monthly = {
        "SE3": [{"month": "2025-01", "avg": 50.0}],
        "SE4": [{"month": "2025-01", "avg": 62.5}],
        "SE1": [{"month": "2025-01", "avg": 30.0}],
    }
    spreads = calculate_zone_spreads(
        monthly, pairs=[("SE4", "SE3"), ("SE3", "SE1")]
    )
    assert spreads == [
        {"month": "2025-01", "SE4-SE3": 12.5, "SE3-SE1": 20.0}
    ]


def test_calculate_zone_spreads_missing_zone():
    monthly = {"SE3": [{"month": "2025-01", "avg": 50.0}]}
    spreads = calculate_zone_spreads(monthly, pairs=[("SE4", "SE3")])
    assert spreads[0]["SE4-SE3"] is None


# ---------------------------------------------------------------------------
# rework_capture_analysis
# ---------------------------------------------------------------------------

def test_aggregate_installed_solar_maps_lan_and_skips_noise():
    rows = [
        # Länsrader (ska räknas)
        {"ar": "2023", "region": "12 Skåne län",
         "installerad_effekt_(mw)": "100.5"},
        {"ar": "2023", "region": "10 Blekinge län",
         "installerad_effekt_(mw)": "20.0"},
        # Kommunrad (4 siffror — ska ignoreras)
        {"ar": "2023", "region": "1280 Malmö",
         "installerad_effekt_(mw)": "999"},
        # Riket (ska ignoreras)
        {"ar": "2023", "region": "00 Riket",
         "installerad_effekt_(mw)": "5000"},
        # PxWeb-saknat värde
        {"ar": "2023", "region": "25 Norrbottens län",
         "installerad_effekt_(mw)": ".."},
    ]
    result = aggregate_installed_solar(rows)
    assert result["SE4"] == [{"year": 2023, "mw": 120.5}]
    assert result["SE1"] == [{"year": 2023, "mw": 0.0}]


def test_aggregate_installed_wind():
    rows = [
        {"year": "2023", "zone": "SE2", "installed_mw": "6823.0"},
        {"year": "2024", "zone": "SE2", "installed_mw": "7075.0"},
    ]
    result = aggregate_installed_wind(rows)
    assert result["SE2"] == [
        {"year": 2023, "mw": 6823.0},
        {"year": 2024, "mw": 7075.0},
    ]


def test_calculate_orientation_yearly_premium_and_eur_kwp():
    market_data = {
        "SE4": {
            "sol_syd": {"yearly": [
                {"year": 2025, "capture": 40.0, "ratio": 0.66},
            ]},
            "sol_ov": {"yearly": [
                {"year": 2025, "capture": 44.0, "ratio": 0.73},
            ]},
            "sol_tracker": {"yearly": [
                {"year": 2025, "capture": 42.0, "ratio": 0.70},
            ]},
        }
    }
    result = calculate_orientation_yearly(market_data)
    prem = result["premium_vs_syd"]["SE4"][0]
    assert prem["ov_pct"] == pytest.approx(10.0, abs=0.1)
    assert prem["tracker_pct"] == pytest.approx(5.0, abs=0.1)

    ekwp = result["eur_per_kwp"]["SE4"][0]
    # syd: 40.0 × 1012/1000 = 40.5
    assert ekwp["syd"] == pytest.approx(40.5, abs=0.1)
    # ew: 44.0 × 911/1000 = 40.1 — trots 10 % högre capture vinner syd
    assert ekwp["ov"] == pytest.approx(40.1, abs=0.1)
    # tracker: 42.0 × 1202/1000 = 50.5
    assert ekwp["tracker"] == pytest.approx(50.5, abs=0.1)


# ---------------------------------------------------------------------------
# rework_imbalance
# ---------------------------------------------------------------------------

def test_aggregate_imbalance_monthly():
    rows = [
        {"time_start": "2025-03-01T00:00:00Z",
         "imbl_spot_diff_eur_mwh": "10.0", "main_dir_reg_power": "1.0"},
        {"time_start": "2025-03-01T00:15:00Z",
         "imbl_spot_diff_eur_mwh": "-30.0", "main_dir_reg_power": "-1.0"},
        {"time_start": "2025-03-01T00:30:00Z",
         "imbl_spot_diff_eur_mwh": "0.0", "main_dir_reg_power": "0"},
        # Trasig rad ignoreras
        {"time_start": "2025-03-01T00:45:00Z",
         "imbl_spot_diff_eur_mwh": "", "main_dir_reg_power": "1"},
    ]
    result = aggregate_imbalance_monthly(rows)
    assert len(result) == 1
    m = result[0]
    assert m["month"] == "2025-03"
    assert m["n"] == 3
    assert m["mean_abs_diff"] == pytest.approx(13.33, abs=0.01)
    assert m["mean_diff"] == pytest.approx(-6.67, abs=0.01)
    assert m["share_up"] == pytest.approx(33.3, abs=0.1)
    assert m["share_down"] == pytest.approx(33.3, abs=0.1)


# ---------------------------------------------------------------------------
# rework_dashboard_data (pruning)
# ---------------------------------------------------------------------------

def test_prune_capture_data_drops_daily_and_extra_profiles():
    market_data = {
        "SE3": {
            "baseload": {"yearly": [1], "monthly": [2], "daily": [3]},
            "sol_syd": {"yearly": [1], "monthly": [2], "daily": [3]},
            "park_horby": {"yearly": [1], "monthly": [2]},
            "bess_tb2": {"yearly": [1]},
        }
    }
    pruned = prune_capture_data(market_data)
    assert set(pruned["SE3"].keys()) == {"baseload", "sol_syd"}
    assert set(pruned["SE3"]["baseload"].keys()) == {"yearly", "monthly"}


def test_prune_forward_drops_history():
    forward = {
        "settlement_date": "2026-04-29",
        "contracts": [{"label": "YR-27", "type": "year"}],
        "sys": {"YR-27": 47.15},
        "zone_fwd": {"SE3": {"YR-27": 50.0}},
        "forward_history": {"YR-27": {"sys_series": [1] * 1000}},
        "forward_health": {"stale_finals": []},
    }
    pruned = prune_forward(forward)
    assert "forward_history" not in pruned
    assert "forward_health" not in pruned
    assert pruned["settlement_date"] == "2026-04-29"
    assert prune_forward(None) is None


# ---------------------------------------------------------------------------
# rework_portfolio
# ---------------------------------------------------------------------------

def test_build_fleet_series_sums_parks():
    assets = {
        "parks": {
            "a": {"months": [
                {"year": 2026, "month": 4, "is_partial": False,
                 "energy_mwh": 100.0, "budget_mwh": 90.0,
                 "revenue_eur": 5000.0, "revenue_eur_ppa": 5500.0,
                 "bazefield_volume_mwh": 100.0},
            ]},
            "b": {"months": [
                {"year": 2026, "month": 4, "is_partial": False,
                 "energy_mwh": 50.0, "budget_mwh": 60.0,
                 "revenue_eur": 2000.0, "revenue_eur_ppa": None,
                 "bazefield_volume_mwh": 50.0},
            ]},
        }
    }
    series = build_fleet_series(assets)
    assert len(series) == 1
    m = series[0]
    assert m["month"] == "2026-04"
    assert m["energy_mwh"] == 150.0
    assert m["budget_mwh"] == 150.0
    assert m["vs_budget_pct"] == 0.0
    assert m["revenue_eur"] == 7000.0
    # Park b saknar PPA → fall tillbaka på spot-revenue
    assert m["revenue_ppa_eur"] == 7500.0
    assert m["capture"] == pytest.approx(46.67, abs=0.01)
    assert m["is_partial"] is False


def test_front_year_label_skips_in_delivery():
    forward = {
        "settlement_date": "2026-04-29",
        "contracts": [
            {"label": "Q3-26", "type": "quarter", "start": "2026-07-01"},
            {"label": "YR-26", "type": "year", "start": "2026-01-01"},
            {"label": "YR-27", "type": "year", "start": "2027-01-01"},
        ],
    }
    # YR-26 är i leverans (start < settlement) → YR-27 är hedge-referensen
    assert _front_year_label(forward) == "YR-27"
    assert _front_year_label(None) is None
    # Bara kontrakt i leverans → fall tillbaka på första
    forward["contracts"] = [
        {"label": "YR-26", "type": "year", "start": "2026-01-01"},
    ]
    assert _front_year_label(forward) == "YR-26"


def test_fmt_num_swedish():
    assert fmt_num(1234.5, 1) == f"1{chr(8239)}234,5"
    assert fmt_num(None) == "–"
    assert fmt_signed_pct(4.26) == "+4,3 %"
    assert fmt_signed_pct(-3.1) == "−3,1 %"
