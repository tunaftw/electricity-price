"""Enhetstester för kannibaliseringsregressionen (elpris.insikt.kannibalisering).

All testdata är syntetisk — inga filberoenden, ingen nätverkstrafik.
OLS:en verifieras mot handräknade exempel så att stdlib-implementationen
inte kan glida.
"""

import math

import pytest

from elpris.insikt.kannibalisering import (
    MIN_YEARS,
    average_annual_growth,
    build_kannibalisering_data,
    build_kannibalisering_insights,
    extrapolate_installed,
    fit_cannibalization,
    ols_fit,
    project_ratio,
    t_quantile_95,
)


# ---------------------------------------------------------------------------
# OLS — handräknade exempel
# ---------------------------------------------------------------------------

def test_ols_perfect_line():
    """y = 10 − 2x exakt → slope −2, intercept 10, r2 = 1, stderr 0."""
    points = [(x, 10.0 - 2.0 * x) for x in (1.0, 2.0, 3.0, 4.0)]
    fit = ols_fit(points)
    assert fit["slope"] == pytest.approx(-2.0, abs=1e-12)
    assert fit["intercept"] == pytest.approx(10.0, abs=1e-12)
    assert fit["r2"] == pytest.approx(1.0, abs=1e-12)
    assert fit["n"] == 4
    assert fit["df"] == 2
    assert fit["stderr"] == pytest.approx(0.0, abs=1e-9)
    # Nollbrett band på en perfekt linje
    assert fit["ci_low"] == pytest.approx(-2.0, abs=1e-9)
    assert fit["ci_high"] == pytest.approx(-2.0, abs=1e-9)


def test_ols_known_noise():
    """Handräknat brusexempel: x = 1..4, y = 2, 4, 5, 8.

    x̄ = 2,5  ȳ = 4,75
    Sxy = (−1,5)(−2,75) + (−0,5)(−0,75) + (0,5)(0,25) + (1,5)(3,25) = 9,5
    Sxx = 2,25 + 0,25 + 0,25 + 2,25 = 5,0        → slope = 1,9
    intercept = 4,75 − 1,9 · 2,5 = 0,0
    Syy = 7,5625 + 0,5625 + 0,0625 + 10,5625 = 18,75
    residualer: 0,1  0,2  −0,7  0,4 → SSres = 0,01+0,04+0,49+0,16 = 0,70
    r2 = 1 − 0,70/18,75 = 0,962666…
    s² = 0,70/2 = 0,35 → SE = sqrt(0,35/5) = 0,264575…
    KI = 1,9 ± 4,303 · 0,264575 = 1,9 ± 1,138467…
    """
    points = [(1.0, 2.0), (2.0, 4.0), (3.0, 5.0), (4.0, 8.0)]
    fit = ols_fit(points)
    assert fit["slope"] == pytest.approx(1.9, abs=1e-12)
    assert fit["intercept"] == pytest.approx(0.0, abs=1e-12)
    assert fit["r2"] == pytest.approx(1.0 - 0.70 / 18.75, abs=1e-12)
    assert fit["stderr"] == pytest.approx(math.sqrt(0.35 / 5.0), abs=1e-12)
    assert fit["t_crit"] == pytest.approx(4.303)
    half = 4.303 * math.sqrt(0.35 / 5.0)
    assert fit["ci_low"] == pytest.approx(1.9 - half, abs=1e-9)
    assert fit["ci_high"] == pytest.approx(1.9 + half, abs=1e-9)


def test_ols_too_few_points():
    assert ols_fit([])["slope"] is None
    assert ols_fit([(1.0, 2.0)])["slope"] is None
    # n = 2: lutning finns, men df = 0 → inget KI
    fit = ols_fit([(1.0, 2.0), (2.0, 4.0)])
    assert fit["slope"] == pytest.approx(2.0)
    assert fit["stderr"] is None
    assert fit["ci_low"] is None


def test_ols_no_variation_in_x():
    fit = ols_fit([(3.0, 1.0), (3.0, 2.0), (3.0, 5.0)])
    assert fit["slope"] is None
    assert fit["intercept"] is None


def test_ols_flat_y_gives_no_r2():
    """Syy = 0 → r2 odefinierat (ingen varians att förklara)."""
    fit = ols_fit([(1.0, 5.0), (2.0, 5.0), (3.0, 5.0)])
    assert fit["slope"] == pytest.approx(0.0)
    assert fit["r2"] is None


def test_t_quantile_table_and_fallback():
    assert t_quantile_95(0) is None
    assert t_quantile_95(1) == pytest.approx(12.706)
    assert t_quantile_95(2) == pytest.approx(4.303)
    assert t_quantile_95(10) == pytest.approx(2.228)
    # df > 10 → normalapproximation
    assert t_quantile_95(25) == pytest.approx(1.960)


# ---------------------------------------------------------------------------
# Extrapolering av installerad kapacitet
# ---------------------------------------------------------------------------

def _installed(pairs):
    return [{"year": y, "mw": mw} for y, mw in pairs]


def test_average_annual_growth_uses_last_three_diffs():
    recs = _installed([
        (2020, 100.0), (2021, 110.0),  # diff 10 (utanför lookback)
        (2022, 210.0), (2023, 410.0), (2024, 510.0),  # diffar 100, 200, 100
    ])
    assert average_annual_growth(recs) == pytest.approx(400.0 / 3.0)
    # Färre än två punkter → ingen takt
    assert average_annual_growth(_installed([(2024, 100.0)])) is None
    assert average_annual_growth([]) is None


def test_average_annual_growth_handles_year_gaps():
    """Ett hopp 2019 → 2022 är tre års tillskott, inte ett."""
    recs = _installed([(2019, 100.0), (2022, 400.0)])
    assert average_annual_growth(recs) == pytest.approx(100.0)


def test_extrapolate_installed_flags_future_years():
    recs = _installed([(2022, 100.0), (2023, 200.0), (2024, 300.0)])
    series, growth = extrapolate_installed(recs, 2026)
    assert growth == pytest.approx(100.0)
    assert [r["year"] for r in series] == [2022, 2023, 2024, 2025, 2026]
    assert [r["mw"] for r in series] == [100.0, 200.0, 300.0, 400.0, 500.0]
    assert [r["installed_extrapolated"] for r in series] == [
        False, False, False, True, True
    ]


def test_extrapolate_installed_no_op_when_already_covered():
    recs = _installed([(2023, 100.0), (2024, 150.0)])
    series, growth = extrapolate_installed(recs, 2024)
    assert growth == pytest.approx(50.0)
    assert len(series) == 2
    assert all(not r["installed_extrapolated"] for r in series)


def test_extrapolate_installed_empty():
    assert extrapolate_installed([], 2026) == ([], None)


# ---------------------------------------------------------------------------
# fit_cannibalization
# ---------------------------------------------------------------------------

def _ratios(pairs, complete=True):
    return [
        {"year": y, "ratio": r, "capture": 40.0, "baseload": 50.0,
         "complete": complete}
        for y, r in pairs
    ]


def test_fit_cannibalization_perfect_negative_relation():
    """1 GW mer sol → 10 p.e. lägre ratio, exakt linjärt."""
    ratios = _ratios([
        (2021, 0.90), (2022, 0.80), (2023, 0.70), (2024, 0.60),
    ])
    installed = _installed([
        (2021, 1000.0), (2022, 2000.0), (2023, 3000.0), (2024, 4000.0),
    ])
    fit = fit_cannibalization("SE3", ratios, installed)
    assert fit["status"] == "ok"
    assert fit["slope_pp_per_gw"] == pytest.approx(-10.0, abs=1e-6)
    assert fit["intercept_pp"] == pytest.approx(100.0, abs=1e-6)
    assert fit["r2"] == pytest.approx(1.0)
    assert fit["n"] == 4
    assert fit["years_used"] == [2021, 2022, 2023, 2024]
    assert fit["growth_mw_per_year"] == pytest.approx(1000.0)
    assert fit["installed_actual_through"] == 2024
    assert all(not p["installed_extrapolated"] for p in fit["points"])
    assert fit["points"][0]["ratio_pp"] == pytest.approx(90.0)


def test_fit_cannibalization_extrapolates_installed_for_2025():
    """Installerad slutar 2024 men ratio finns 2025 → framskriven punkt."""
    ratios = _ratios([
        (2022, 0.80), (2023, 0.70), (2024, 0.60), (2025, 0.50),
    ])
    installed = _installed([(2022, 1000.0), (2023, 2000.0), (2024, 3000.0)])
    fit = fit_cannibalization("SE4", ratios, installed)
    assert fit["status"] == "ok"
    assert fit["years_used"] == [2022, 2023, 2024, 2025]
    last = fit["points"][-1]
    assert last["year"] == 2025
    assert last["installed_mw"] == pytest.approx(4000.0)
    assert last["installed_extrapolated"] is True
    assert fit["installed_actual_through"] == 2024
    assert fit["slope_pp_per_gw"] == pytest.approx(-10.0, abs=1e-6)


def test_fit_cannibalization_excludes_partial_and_old_years():
    """Partiella år och år före min_year får inte påverka lutningen."""
    ratios = _ratios([
        (2022, 0.80), (2023, 0.70), (2024, 0.60), (2025, 0.50),
    ])
    # Partiellt innevarande år med kraftigt avvikande ratio
    ratios.append({"year": 2026, "ratio": 0.95, "capture": 60.0,
                   "baseload": 63.0, "complete": False})
    # För gammalt år (< MIN_YEAR = 2020)
    ratios.insert(0, {"year": 2019, "ratio": 0.99, "capture": 60.0,
                      "baseload": 61.0, "complete": True})
    installed = _installed([
        (2022, 1000.0), (2023, 2000.0), (2024, 3000.0),
    ])
    fit = fit_cannibalization("SE4", ratios, installed)
    assert fit["years_used"] == [2022, 2023, 2024, 2025]
    assert 2026 not in fit["years_used"]
    assert 2019 not in fit["years_used"]
    assert fit["slope_pp_per_gw"] == pytest.approx(-10.0, abs=1e-6)


def test_fit_cannibalization_insufficient_data():
    ratios = _ratios([(2023, 0.70), (2024, 0.60), (2025, 0.50)])
    installed = _installed([(2023, 1000.0), (2024, 2000.0)])
    fit = fit_cannibalization("SE1", ratios, installed)
    assert fit["status"] == "insufficient_data"
    assert fit["n"] == 3
    assert fit["slope_pp_per_gw"] is None
    assert str(MIN_YEARS) in fit["reason"]
    # Punkterna finns kvar för scatter även utan regression
    assert len(fit["points"]) == 3


def test_fit_cannibalization_no_installed_data():
    fit = fit_cannibalization("SE1", _ratios([(2023, 0.7), (2024, 0.6)]), [])
    assert fit["status"] == "insufficient_data"
    assert "installerad" in fit["reason"]


def test_fit_cannibalization_no_complete_years():
    ratios = _ratios([(2024, 0.6), (2025, 0.5)], complete=False)
    fit = fit_cannibalization("SE2", ratios, _installed([(2024, 100.0)]))
    assert fit["status"] == "insufficient_data"
    assert fit["n"] == 0


def test_fit_cannibalization_flat_installed_is_degenerate():
    ratios = _ratios([(2022, 0.8), (2023, 0.7), (2024, 0.6), (2025, 0.5)])
    installed = _installed([
        (2022, 1000.0), (2023, 1000.0), (2024, 1000.0),
    ])
    fit = fit_cannibalization("SE2", ratios, installed)
    assert fit["status"] == "insufficient_data"
    assert "variation" in fit["reason"]


# ---------------------------------------------------------------------------
# project_ratio
# ---------------------------------------------------------------------------

def test_project_ratio_follows_growth_and_line():
    ratios = _ratios([
        (2021, 0.90), (2022, 0.80), (2023, 0.70), (2024, 0.60),
    ])
    installed = _installed([
        (2021, 1000.0), (2022, 2000.0), (2023, 3000.0), (2024, 4000.0),
    ])
    fit = fit_cannibalization("SE3", ratios, installed)
    proj = project_ratio("SE3", years_ahead=2, fit=fit)
    assert [p["year"] for p in proj] == [2025, 2026]
    assert proj[0]["installed_mw"] == pytest.approx(5000.0)
    assert proj[1]["installed_mw"] == pytest.approx(6000.0)
    # 100 − 10 · GW
    assert proj[0]["ratio_pp"] == pytest.approx(50.0, abs=1e-6)
    assert proj[1]["ratio_pp"] == pytest.approx(40.0, abs=1e-6)
    # Perfekt linje → nollbrett band
    assert proj[1]["ratio_pp_low"] == pytest.approx(40.0, abs=1e-6)
    assert proj[1]["installed_extrapolated"] is True


def test_project_ratio_band_widens_with_distance():
    """Med brus ska bandet växa ju längre från x̄ vi extrapolerar."""
    ratios = _ratios([
        (2021, 0.90), (2022, 0.78), (2023, 0.72), (2024, 0.58),
    ])
    installed = _installed([
        (2021, 1000.0), (2022, 2000.0), (2023, 3000.0), (2024, 4000.0),
    ])
    fit = fit_cannibalization("SE3", ratios, installed)
    proj = project_ratio("SE3", years_ahead=2, fit=fit)
    w1 = proj[0]["ratio_pp_high"] - proj[0]["ratio_pp_low"]
    w2 = proj[1]["ratio_pp_high"] - proj[1]["ratio_pp_low"]
    assert w1 > 0
    assert w2 > w1


def test_project_ratio_empty_when_fit_insufficient():
    fit = {"status": "insufficient_data", "points": []}
    assert project_ratio("SE1", fit=fit) == []


# ---------------------------------------------------------------------------
# build_kannibalisering_data + insikter
# ---------------------------------------------------------------------------

def _two_zone_payload():
    good_ratios = _ratios([
        (2022, 0.85), (2023, 0.74), (2024, 0.63), (2025, 0.52),
    ])
    good_installed = _installed([
        (2022, 1000.0), (2023, 2000.0), (2024, 3000.0),
    ])
    thin_ratios = _ratios([(2024, 0.90), (2025, 0.88)])
    thin_installed = _installed([(2024, 50.0)])
    return build_kannibalisering_data(
        zones=["SE3", "SE1"],
        ratio_yearly_by_zone={"SE3": good_ratios, "SE1": thin_ratios},
        installed_by_zone={"SE3": good_installed, "SE1": thin_installed},
    )


def test_build_kannibalisering_data_marks_zones_individually():
    data = _two_zone_payload()
    assert data["zones"]["SE3"]["status"] == "ok"
    assert data["zones"]["SE1"]["status"] == "insufficient_data"
    assert data["best_zone"] == "SE3"
    assert len(data["zones"]["SE3"]["projection"]) == 2
    assert data["zones"]["SE1"]["projection"] == []
    assert data["assumptions"]


def test_build_insights_mentions_coefficient_projection_and_caveat():
    data = _two_zone_payload()
    insights = build_kannibalisering_insights(data)
    assert insights
    assert all(set(i) == {"text", "tone"} for i in insights)
    joined = " ".join(i["text"] for i in insights)
    assert "SE3" in joined
    assert "GW" in joined
    assert "95 % KI" in joined
    assert "2027" in joined          # framskrivning två år efter 2025
    assert "SE1" in joined           # insufficient_data redovisas
    assert "framskrivna" in joined   # extrapoleringsbrasklapp


def test_build_insights_r2_caveat_only_when_weak():
    data = _two_zone_payload()
    # Perfekt konstruerad serie ovan har högt R² → ingen brasklapp
    assert data["zones"]["SE3"]["r2"] > 0.7
    assert "Brasklapp" not in " ".join(
        i["text"] for i in build_kannibalisering_insights(data)
    )

    noisy = build_kannibalisering_data(
        zones=["SE3"],
        ratio_yearly_by_zone={"SE3": _ratios([
            (2022, 0.60), (2023, 0.85), (2024, 0.55), (2025, 0.80),
        ])},
        installed_by_zone={"SE3": _installed([
            (2022, 1000.0), (2023, 2000.0), (2024, 3000.0),
        ])},
    )
    assert noisy["zones"]["SE3"]["r2"] < 0.7
    assert "Brasklapp" in " ".join(
        i["text"] for i in build_kannibalisering_insights(noisy)
    )


def test_build_insights_reports_positive_slope_honestly():
    data = build_kannibalisering_data(
        zones=["SE2"],
        ratio_yearly_by_zone={"SE2": _ratios([
            (2022, 0.50), (2023, 0.60), (2024, 0.70), (2025, 0.80),
        ])},
        installed_by_zone={"SE2": _installed([
            (2022, 1000.0), (2023, 2000.0), (2024, 3000.0),
        ])},
    )
    assert data["zones"]["SE2"]["slope_pp_per_gw"] > 0
    texts = [i["text"] for i in build_kannibalisering_insights(data)]
    assert any("Ingen zon visar negativ lutning" in t for t in texts)


def test_significance_flag_and_lead_selection():
    """En brusig zon med nästan ingen x-variation får inte leda insikten.

    SE1-liknande fall: installerad sol i tiotals MW, ratio-brus i tiotals
    procentenheter → lutningen kan bli godtyckligt stor och negativ men
    KI spänner över noll. Den signifikanta zonen ska väljas i stället.
    """
    data = build_kannibalisering_data(
        zones=["SE1", "SE4"],
        ratio_yearly_by_zone={
            # Brus, ingen trend
            "SE1": _ratios([
                (2022, 0.83), (2023, 0.95), (2024, 0.91), (2025, 0.84),
            ]),
            # Tydligt negativ
            "SE4": _ratios([
                (2022, 1.08), (2023, 0.91), (2024, 0.73), (2025, 0.64),
            ]),
        },
        installed_by_zone={
            "SE1": _installed([(2022, 26.0), (2023, 41.0), (2024, 58.0)]),
            "SE4": _installed([(2022, 1345.0), (2023, 2280.0), (2024, 2715.0)]),
        },
    )
    assert data["zones"]["SE1"]["significant"] is False
    assert data["zones"]["SE4"]["significant"] is True
    assert data["best_zone"] == "SE4"

    texts = [i["text"] for i in build_kannibalisering_insights(data)]
    assert any(t.startswith("SE4:") for t in texts)
    assert any("ej signifikant" in t for t in texts)


def test_significant_flag_none_without_ci():
    """n = 3 klarar inte min_years, men flaggan får aldrig ljuga om KI."""
    fit = fit_cannibalization(
        "SE3",
        _ratios([(2023, 0.7), (2024, 0.6), (2025, 0.5)]),
        _installed([(2023, 1000.0), (2024, 2000.0)]),
    )
    assert fit["significant"] is None


def test_build_insights_without_any_fit():
    insights = build_kannibalisering_insights({"zones": {}})
    assert len(insights) == 1
    assert insights[0]["tone"] == "neutral"
