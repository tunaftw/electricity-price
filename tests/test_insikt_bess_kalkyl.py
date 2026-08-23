"""Enhetstester för elpris.insikt.bess_kalkyl (investeringskalkyl BESS).

Alla tester körs på handräknade kassaflöden eller syntetisk stack_data —
inga filberoenden. Valideringspunkter:

(a) IRR mot handräknade fall (−1000 + 200×15 → 18,4153 %; −1000 + 300×10
    → 27,3198 %), båda kontrollerade med oberoende bisektion.
(b) NPV-konsistens: NPV(IRR) ≈ 0 och NPV(0) = summan av kassaflödena.
(c) IRR = None när teckenväxling saknas (alla negativa / alla positiva).
(d) build_kalkyl_data: CAPEX skalar med duration, senaste HELA året väljs
    (inte YTD), payback = CAPEX / årligt netto, viable-flaggan mot
    diskonteringsräntan.
(e) revenue_decay_pct_per_yr sänker NPV/IRR monotont och lämnar
    default-fallet (0 %) oförändrat.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris.insikt.bess_kalkyl import (  # noqa: E402
    build_kalkyl_data,
    build_kalkyl_insights,
    irr,
    npv,
)


# ---------------------------------------------------------------------------
# Hjälpare: syntetisk stack_data
# ---------------------------------------------------------------------------

def _yearly_row(year: int, days: int, stacked: float) -> dict:
    """Årsrad i build_stack_data-format med acceptance-känslighet."""
    return {
        "year": year,
        "days": days,
        "stacked_eur": stacked,
        "arb_only_eur": stacked * 0.3,
        "best_ancillary_only_eur": stacked * 0.6,
        "best_ancillary_product": "mfrr_cm_up",
        "uplift_vs_best_single_pct": 40.0,
        "cycles": 200.0,
        "reserve_share_pct": 60.0,
        "top_product_mix": {"mfrr_cm_up": 3000},
        "invariant_ok": True,
        "ancillary_only_by_product_eur": {"mfrr_cm_up": stacked * 0.6},
        "acceptance_sensitivity": {
            "1.0": stacked,
            "0.7": stacked * 0.8,
            "0.4": stacked * 0.6,
        },
    }


def _stack_data(stacked_2h: float = 100_000.0) -> dict:
    """Två zoner × två durationer, 2025 helt år + 2026 halvår (YTD)."""
    def dur_block(scale: float) -> dict:
        return {
            "monthly": [],
            "yearly": [
                _yearly_row(2025, 365, stacked_2h * scale),
                # YTD-året ska INTE användas trots högre "årstakt".
                _yearly_row(2026, 203, stacked_2h * scale * 0.9),
            ],
        }

    return {
        "params": {
            "power_mw": 1.0,
            "durations_h": [2, 4],
            "acceptance_rate": 1.0,
            "acceptance_sensitivity": [0.7, 0.4],
        },
        "zones": {
            "SE3": {"2h": dur_block(1.0), "4h": dur_block(1.4)},
            "SE4": {"2h": dur_block(1.2), "4h": dur_block(1.6)},
        },
    }


# ---------------------------------------------------------------------------
# (a) IRR mot handräknade fall
# ---------------------------------------------------------------------------

def test_irr_known_case_15_years():
    # −1000 år 0, +200 år 1..15. Bisektion ger 0.18415456837513433.
    r = irr([-1000.0] + [200.0] * 15)
    assert r == pytest.approx(0.1841545684, abs=1e-8)


def test_irr_known_case_10_years():
    r = irr([-1000.0] + [300.0] * 10)
    assert r == pytest.approx(0.2731984241, abs=1e-8)


def test_irr_trivial_doubling():
    # −100 år 0, +200 år 1 → exakt 100 %.
    assert irr([-100.0, 200.0]) == pytest.approx(1.0, abs=1e-9)


def test_irr_negative_case():
    # Investeringen betalar aldrig tillbaka sig → negativ IRR.
    r = irr([-1000.0] + [50.0] * 15)
    assert r is not None
    assert -0.99 < r < 0.0
    assert npv(r, [-1000.0] + [50.0] * 15) == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# (b) NPV-konsistens
# ---------------------------------------------------------------------------

def test_npv_at_zero_rate_is_sum():
    cf = [-1000.0] + [200.0] * 15
    assert npv(0.0, cf) == pytest.approx(sum(cf))


def test_npv_at_irr_is_zero():
    for cf in (
        [-1000.0] + [200.0] * 15,
        [-2_240_000.0] + [400_000.0] * 15,
        [-500.0, 100.0, 250.0, 400.0],
    ):
        r = irr(cf)
        assert r is not None
        assert npv(r, cf) == pytest.approx(0.0, abs=1e-4 * abs(cf[0]))


def test_npv_monotone_in_rate():
    cf = [-1000.0] + [200.0] * 15
    assert npv(0.02, cf) > npv(0.06, cf) > npv(0.20, cf)


# ---------------------------------------------------------------------------
# (c) None-fallet
# ---------------------------------------------------------------------------

def test_irr_none_when_all_negative():
    assert irr([-1000.0, -100.0, -100.0]) is None


def test_irr_none_when_all_positive():
    assert irr([1000.0, 100.0, 100.0]) is None


def test_irr_none_for_empty_or_trivial():
    assert irr([]) is None
    assert irr([-100.0]) is None
    assert irr([0.0, 0.0, 0.0]) is None


# ---------------------------------------------------------------------------
# (d) build_kalkyl_data
# ---------------------------------------------------------------------------

def test_kalkyl_uses_last_complete_year_not_ytd():
    data = build_kalkyl_data(stack_data=_stack_data())
    row = data["zones"]["SE3"]["2h"]
    assert row["year"] == 2025
    assert row["year_days"] == 365
    assert row["year_complete"] is True


def test_kalkyl_capex_scales_with_duration():
    data = build_kalkyl_data(
        stack_data=_stack_data(), capex_eur_per_mwh=280_000
    )
    assert data["zones"]["SE3"]["2h"]["capex_eur"] == pytest.approx(560_000)
    assert data["zones"]["SE3"]["4h"]["capex_eur"] == pytest.approx(1_120_000)


def test_kalkyl_annual_net_and_payback():
    # stacked 2h = 100 000 EUR/MW·år vid acceptance 1,0.
    # netto = 100 000 − 8 000 = 92 000; CAPEX = 560 000 → payback 6,087 år.
    data = build_kalkyl_data(
        stack_data=_stack_data(),
        capex_eur_per_mwh=280_000,
        opex_eur_per_mw_yr=8_000,
    )
    case = data["zones"]["SE3"]["2h"]["acceptance"]["1.0"]
    assert case["annual_gross_eur"] == pytest.approx(100_000)
    assert case["annual_net_eur"] == pytest.approx(92_000)
    # payback_yr avrundas till 2 decimaler i utdatat.
    assert case["payback_yr"] == pytest.approx(560_000 / 92_000, abs=0.01)


def test_kalkyl_npv_matches_manual_discounting():
    data = build_kalkyl_data(
        stack_data=_stack_data(),
        capex_eur_per_mwh=280_000,
        opex_eur_per_mw_yr=8_000,
        lifetime_yr=15,
        discount=0.06,
    )
    case = data["zones"]["SE3"]["2h"]["acceptance"]["1.0"]
    manual = -560_000.0 + sum(92_000.0 / 1.06 ** t for t in range(1, 16))
    assert case["npv_eur"] == pytest.approx(manual, abs=1.0)
    # irr_pct avrundas till 4 decimaler i utdatat.
    assert case["irr_pct"] == pytest.approx(
        100.0 * irr([-560_000.0] + [92_000.0] * 15), abs=1e-4
    )


def test_kalkyl_viable_flag_follows_discount():
    stack = _stack_data(stacked_2h=100_000.0)
    high = build_kalkyl_data(stack_data=stack, discount=0.06)
    assert high["zones"]["SE3"]["2h"]["acceptance"]["1.0"]["viable"] is True

    # Med 40 % diskonto ligger IRR (~14 %) under kravet.
    low = build_kalkyl_data(stack_data=stack, discount=0.40)
    assert low["zones"]["SE3"]["2h"]["acceptance"]["1.0"]["viable"] is False


def test_kalkyl_all_acceptance_levels_present_and_ordered():
    data = build_kalkyl_data(stack_data=_stack_data())
    acc = data["zones"]["SE3"]["2h"]["acceptance"]
    assert set(acc) == {"1.0", "0.7", "0.4"}
    # Lägre acceptans → lägre intäkt → lägre IRR.
    assert (
        acc["1.0"]["irr_pct"] > acc["0.7"]["irr_pct"] > acc["0.4"]["irr_pct"]
    )


def test_kalkyl_unprofitable_case_has_no_payback():
    # Intäkt under OPEX → negativt netto: ingen payback, ingen IRR-viability.
    data = build_kalkyl_data(
        stack_data=_stack_data(stacked_2h=5_000.0),
        opex_eur_per_mw_yr=8_000,
    )
    case = data["zones"]["SE3"]["2h"]["acceptance"]["1.0"]
    assert case["annual_net_eur"] < 0
    assert case["payback_yr"] is None
    assert case["viable"] is False
    assert case["npv_eur"] < 0


def test_breakeven_revenue_pct_gives_zero_npv():
    # Skalar man intäkten till breakeven-andelen ska NPV bli ~0.
    data = build_kalkyl_data(
        stack_data=_stack_data(),
        capex_eur_per_mwh=280_000,
        opex_eur_per_mw_yr=8_000,
        lifetime_yr=15,
        discount=0.06,
    )
    case = data["zones"]["SE3"]["2h"]["acceptance"]["1.0"]
    k = case["breakeven_revenue_pct"] / 100.0
    cf = [-560_000.0] + [100_000.0 * k - 8_000.0] * 15
    assert npv(0.06, cf) == pytest.approx(0.0, abs=500.0)


def test_breakeven_revenue_pct_with_decay():
    data = build_kalkyl_data(
        stack_data=_stack_data(),
        capex_eur_per_mwh=280_000,
        opex_eur_per_mw_yr=8_000,
        lifetime_yr=15,
        discount=0.06,
        revenue_decay_pct_per_yr=2.0,
    )
    case = data["zones"]["SE3"]["2h"]["acceptance"]["1.0"]
    k = case["breakeven_revenue_pct"] / 100.0
    cf = [-560_000.0] + [
        100_000.0 * k * 0.98 ** (t - 1) - 8_000.0 for t in range(1, 16)
    ]
    assert npv(0.06, cf) == pytest.approx(0.0, abs=500.0)


def test_kalkyl_best_case_picked_across_zones():
    data = build_kalkyl_data(stack_data=_stack_data())
    best = data["best"]
    # SE4 4h har högst intäkt per MW; CAPEX skalar linjärt men intäkten
    # gör det inte, så bästa IRR ska vara den högsta i tabellen.
    all_irr = [
        c["acceptance"]["1.0"]["irr_pct"]
        for z in data["zones"].values()
        for c in z.values()
    ]
    assert best["irr_pct"] == pytest.approx(max(all_irr))


# ---------------------------------------------------------------------------
# (e) revenue_decay
# ---------------------------------------------------------------------------

def test_revenue_decay_default_is_zero():
    a = build_kalkyl_data(stack_data=_stack_data())
    b = build_kalkyl_data(
        stack_data=_stack_data(), revenue_decay_pct_per_yr=0.0
    )
    assert (
        a["zones"]["SE3"]["2h"]["acceptance"]["1.0"]["npv_eur"]
        == b["zones"]["SE3"]["2h"]["acceptance"]["1.0"]["npv_eur"]
    )


def test_revenue_decay_lowers_npv_and_irr():
    base = build_kalkyl_data(stack_data=_stack_data())
    decayed = build_kalkyl_data(
        stack_data=_stack_data(), revenue_decay_pct_per_yr=2.0
    )
    b = base["zones"]["SE3"]["2h"]["acceptance"]["1.0"]
    d = decayed["zones"]["SE3"]["2h"]["acceptance"]["1.0"]
    assert d["npv_eur"] < b["npv_eur"]
    assert d["irr_pct"] < b["irr_pct"]
    # År 1 är oförändrat (decay verkar från år 2).
    assert d["annual_net_eur"] == pytest.approx(b["annual_net_eur"])
    # Payback förlängs när intäkten faller.
    assert d["payback_yr"] > b["payback_yr"]


def test_revenue_decay_matches_manual_cashflow():
    data = build_kalkyl_data(
        stack_data=_stack_data(),
        capex_eur_per_mwh=280_000,
        opex_eur_per_mw_yr=8_000,
        lifetime_yr=15,
        discount=0.06,
        revenue_decay_pct_per_yr=1.5,
    )
    case = data["zones"]["SE3"]["2h"]["acceptance"]["1.0"]
    cf = [-560_000.0] + [
        100_000.0 * (1.0 - 0.015) ** (t - 1) - 8_000.0
        for t in range(1, 16)
    ]
    assert case["npv_eur"] == pytest.approx(npv(0.06, cf), abs=1.0)


# ---------------------------------------------------------------------------
# Insikter
# ---------------------------------------------------------------------------

def test_insights_shape_and_content():
    data = build_kalkyl_data(stack_data=_stack_data())
    ins = build_kalkyl_insights(data)
    assert len(ins) >= 3
    for item in ins:
        assert set(item) == {"text", "tone"}
        assert item["tone"] in {"pos", "neg", "neutral"}
        assert item["text"].strip()
    blob = " ".join(i["text"] for i in ins)
    assert "IRR" in blob
    # Ärlig varning ska finnas med och vara negativt tonad.
    assert any(
        "perfect foresight" in i["text"].lower() and i["tone"] == "neg"
        for i in ins
    )


def test_insights_handle_empty_data():
    empty = build_kalkyl_data(stack_data={"params": {}, "zones": {}})
    assert empty["zones"] == {}
    assert empty["best"] is None
    ins = build_kalkyl_insights(empty)
    assert isinstance(ins, list)
    for item in ins:
        assert set(item) == {"text", "tone"}
