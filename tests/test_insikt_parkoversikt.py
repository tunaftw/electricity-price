"""Enhetstester för elpris.insikt.parkoversikt (Parköversikt — insiktsgenerator).

Insiktsgeneratorerna är rena funktioner över park-dictar (samma format som
``unified_dashboard_data._build_assets_section`` producerar), så testerna
bygger syntetiska månadslistor med känd förlustkaskad och verifierar:

1. **Statusregeln** — |vs_budget_pct| <= 3 → neutral, annars pos/neg
   (gränsvärdet exakt ±3,0 % testas).
2. **Dominerande orsak** — största förlustposten namnges på klartext.
3. **Datakvalitetsflaggan** — irr_shortfall == 0 och residual > 30 % av
   budget → OBS-mening.
4. **Trendregeln** — tre stängda månader åt samma håll → "tredje månaden
   i rad".
5. **Portföljinsikterna** — YTD-läge, största avvikare, PPA-effekt.
"""

from __future__ import annotations

import pytest

from elpris.insikt.parkoversikt import (
    BUDGET_TOLERANCE_PCT,
    RESIDUAL_DQ_SHARE,
    TREND_MONTHS,
    build_park_insight,
    build_portfolio_insights,
    build_ytd_summary,
)


# ---------------------------------------------------------------------------
# Syntetiska byggstenar
# ---------------------------------------------------------------------------

def make_losses(budget, actual, irr=0.0, avail=0.0, temp=0.0,
                clip=0.0, residual=None):
    """Bygg en förlustkaskad-dict. residual beräknas om ej given."""
    if residual is None:
        residual = budget - actual - irr - avail - temp - clip
    return {
        "budget_mwh": round(budget, 2),
        "actual_mwh": round(actual, 2),
        "irradiance_shortfall_mwh": round(irr, 2),
        "availability_mwh": round(avail, 2),
        "temperature_mwh": round(temp, 2),
        "clipping_mwh": round(clip, 2),
        "residual_mwh": round(residual, 2),
    }


def make_month(year, month, energy, budget, losses=None, is_partial=False,
               pr=None, budget_pr=None, revenue=None, revenue_ppa=None,
               volume=None):
    vs = round((energy / budget - 1.0) * 100.0, 1) if budget else None
    return {
        "year": year,
        "month": month,
        "is_partial": is_partial,
        "energy_mwh": round(energy, 2),
        "budget_mwh": round(budget, 2),
        "vs_budget_pct": vs,
        "yield_kwh_kwp": None,
        "pr_pct": pr,
        "budget_pr_pct": budget_pr,
        "availability_pct": None,
        "losses": losses,
        "revenue_eur": revenue,
        "revenue_eur_ppa": revenue_ppa,
        "bazefield_volume_mwh": volume,
    }


def make_park(months, name="Testparken", zone="SE3", capacity_mwp=10.0):
    return {
        "name": name,
        "zone": zone,
        "capacity_mwp": capacity_mwp,
        "months": months,
    }


# ---------------------------------------------------------------------------
# Statusregeln (±3 %-tröskeln)
# ---------------------------------------------------------------------------

class TestStatusThreshold:
    def test_exactly_plus_3_is_neutral(self):
        # 103 / 100 → exakt +3,0 % — inom tolerans
        park = make_park([make_month(2026, 7, 103.0, 100.0)])
        ins = build_park_insight(park)
        assert ins["tone"] == "neutral"
        assert "i linje med budget" in ins["text"]

    def test_exactly_minus_3_is_neutral(self):
        park = make_park([make_month(2026, 7, 97.0, 100.0)])
        ins = build_park_insight(park)
        assert ins["tone"] == "neutral"
        assert "i linje med budget" in ins["text"]

    def test_above_tolerance_is_pos(self):
        park = make_park([make_month(2026, 7, 104.0, 100.0)])
        ins = build_park_insight(park)
        assert ins["tone"] == "pos"

    def test_below_tolerance_is_neg(self):
        park = make_park([make_month(2026, 7, 96.0, 100.0)])
        ins = build_park_insight(park)
        assert ins["tone"] == "neg"

    def test_tolerance_constant_is_3(self):
        assert BUDGET_TOLERANCE_PCT == 3.0

    def test_no_closed_month(self):
        park = make_park([make_month(2026, 8, 10.0, 12.0, is_partial=True)])
        ins = build_park_insight(park)
        assert ins["tone"] == "neutral"
        assert "stängd månad" in ins["text"]

    def test_partial_month_ignored(self):
        # MTD-månaden (−50 %) får inte styra insikten — juli (+5 %) gör det
        park = make_park([
            make_month(2026, 7, 105.0, 100.0),
            make_month(2026, 8, 10.0, 20.0, is_partial=True),
        ])
        ins = build_park_insight(park)
        assert ins["tone"] == "pos"
        assert "juli" in ins["text"].lower()

    def test_numbers_in_text(self):
        park = make_park([make_month(2026, 7, 96.0, 100.0)])
        ins = build_park_insight(park)
        assert "96" in ins["text"]          # MWh
        assert "4,0" in ins["text"]         # −4,0 %


# ---------------------------------------------------------------------------
# Dominerande orsak
# ---------------------------------------------------------------------------

class TestDominantCause:
    def test_availability_dominates(self):
        losses = make_losses(100.0, 80.0, irr=2.0, avail=15.0, temp=1.0,
                             clip=0.5)
        park = make_park([make_month(2026, 7, 80.0, 100.0, losses=losses)])
        ins = build_park_insight(park)
        assert "tillgänglighetsbortfall" in ins["text"]
        assert ins["tone"] == "neg"
        # 15 av 20 MWh gap = 75 % av gapet
        assert "75" in ins["text"]

    def test_irradiance_dominates(self):
        losses = make_losses(100.0, 85.0, irr=12.0, avail=2.0, temp=1.0)
        park = make_park([make_month(2026, 7, 85.0, 100.0, losses=losses)])
        ins = build_park_insight(park)
        assert "svag instrålning" in ins["text"]

    def test_temperature_dominates(self):
        losses = make_losses(100.0, 90.0, irr=1.0, avail=1.0, temp=7.0)
        park = make_park([make_month(2026, 7, 90.0, 100.0, losses=losses)])
        ins = build_park_insight(park)
        assert "varmare än normalt" in ins["text"]

    def test_clipping_dominates(self):
        losses = make_losses(100.0, 90.0, irr=1.0, clip=8.0)
        park = make_park([make_month(2026, 7, 90.0, 100.0, losses=losses)])
        ins = build_park_insight(park)
        assert "exportbegränsning" in ins["text"]

    def test_residual_dominates(self):
        losses = make_losses(100.0, 90.0, irr=1.0, avail=1.0)  # residual=8
        park = make_park([make_month(2026, 7, 90.0, 100.0, losses=losses)])
        ins = build_park_insight(park)
        assert "oförklarad förlust" in ins["text"]
        assert "utredning" in ins["text"]

    def test_positive_deviation_strong_irradiance(self):
        # +10 % över budget drivet av stark instrålning (negativ irr-post)
        losses = make_losses(100.0, 110.0, irr=-12.0, avail=1.0)
        park = make_park([make_month(2026, 7, 110.0, 100.0, losses=losses)])
        ins = build_park_insight(park)
        assert ins["tone"] == "pos"
        assert "stark instrålning" in ins["text"]

    def test_no_losses_still_gives_status(self):
        park = make_park([make_month(2026, 7, 90.0, 100.0, losses=None)])
        ins = build_park_insight(park)
        assert ins["tone"] == "neg"
        assert "10,0" in ins["text"]


# ---------------------------------------------------------------------------
# Datakvalitetsflaggan
# ---------------------------------------------------------------------------

class TestDataQualityFlag:
    def test_flag_when_irr_zero_and_residual_large(self):
        # Hörby juli 2026-fallet: POA saknas → irr==0, residualen sväljer allt
        losses = make_losses(100.0, 20.0, irr=0.0, avail=2.0)  # residual=78
        park = make_park([make_month(2026, 7, 20.0, 100.0, losses=losses)])
        ins = build_park_insight(park)
        assert "instrålningsdata saknas" in ins["text"]
        assert "OBS" in ins["text"]

    def test_no_flag_when_residual_at_30_pct(self):
        # Exakt 30 % är inte "> 30 %"
        losses = make_losses(100.0, 68.0, irr=0.0, avail=2.0)  # residual=30
        park = make_park([make_month(2026, 7, 68.0, 100.0, losses=losses)])
        ins = build_park_insight(park)
        assert "instrålningsdata saknas" not in ins["text"]

    def test_no_flag_when_irr_nonzero(self):
        losses = make_losses(100.0, 20.0, irr=40.0, avail=2.0)  # residual=38
        park = make_park([make_month(2026, 7, 20.0, 100.0, losses=losses)])
        ins = build_park_insight(park)
        assert "instrålningsdata saknas" not in ins["text"]

    def test_share_constant(self):
        assert RESIDUAL_DQ_SHARE == 0.30


# ---------------------------------------------------------------------------
# Trendregeln
# ---------------------------------------------------------------------------

class TestTrend:
    def test_three_months_under(self):
        park = make_park([
            make_month(2026, 5, 90.0, 100.0),
            make_month(2026, 6, 92.0, 100.0),
            make_month(2026, 7, 91.0, 100.0),
        ])
        ins = build_park_insight(park)
        assert "tredje månaden i rad under budget" in ins["text"].lower()

    def test_three_months_over(self):
        park = make_park([
            make_month(2026, 5, 110.0, 100.0),
            make_month(2026, 6, 108.0, 100.0),
            make_month(2026, 7, 109.0, 100.0),
        ])
        ins = build_park_insight(park)
        assert "tredje månaden i rad över budget" in ins["text"].lower()

    def test_mixed_signs_no_trend(self):
        park = make_park([
            make_month(2026, 5, 110.0, 100.0),
            make_month(2026, 6, 90.0, 100.0),
            make_month(2026, 7, 91.0, 100.0),
        ])
        ins = build_park_insight(park)
        assert "i rad" not in ins["text"]

    def test_only_two_months_no_trend(self):
        park = make_park([
            make_month(2026, 6, 90.0, 100.0),
            make_month(2026, 7, 91.0, 100.0),
        ])
        ins = build_park_insight(park)
        assert "i rad" not in ins["text"]

    def test_trend_months_constant(self):
        assert TREND_MONTHS == 3

    def test_dq_flag_wins_over_trend(self):
        # Max 2 meningar: datakvalitetsflaggan prioriteras före trenden
        losses = make_losses(100.0, 20.0, irr=0.0)
        park = make_park([
            make_month(2026, 5, 90.0, 100.0),
            make_month(2026, 6, 92.0, 100.0),
            make_month(2026, 7, 20.0, 100.0, losses=losses),
        ])
        ins = build_park_insight(park)
        assert "instrålningsdata saknas" in ins["text"]
        assert "i rad" not in ins["text"]


class TestMaxTwoSentences:
    @pytest.mark.parametrize("months", [
        [make_month(2026, 7, 96.0, 100.0)],
        [make_month(2026, 5, 90.0, 100.0),
         make_month(2026, 6, 92.0, 100.0),
         make_month(2026, 7, 91.0, 100.0,
                    losses=make_losses(100.0, 91.0, avail=6.0))],
        [make_month(2026, 7, 20.0, 100.0,
                    losses=make_losses(100.0, 20.0, irr=0.0))],
    ])
    def test_at_most_two_sentences(self, months):
        # Texterna använder decimalkomma — punkt förekommer bara som
        # meningsavslut, så antal punkter == antal meningar.
        ins = build_park_insight(make_park(months))
        assert ins["text"].count(".") <= 2


# ---------------------------------------------------------------------------
# YTD-summering
# ---------------------------------------------------------------------------

class TestYtdSummary:
    def test_sums_current_year_only(self):
        months = [
            make_month(2025, 12, 50.0, 60.0),
            make_month(2026, 6, 100.0, 100.0),
            make_month(2026, 7, 110.0, 100.0),
        ]
        ytd = build_ytd_summary(months, 2026)
        assert ytd["energy_mwh"] == pytest.approx(210.0)
        assert ytd["budget_mwh"] == pytest.approx(200.0)
        assert ytd["vs_budget_pct"] == pytest.approx(5.0)
        assert ytd["year"] == 2026

    def test_includes_partial_month(self):
        # MTD räknas med — budgeten är redan pro-ratad uppströms
        months = [
            make_month(2026, 7, 100.0, 100.0),
            make_month(2026, 8, 30.0, 40.0, is_partial=True),
        ]
        ytd = build_ytd_summary(months, 2026)
        assert ytd["energy_mwh"] == pytest.approx(130.0)
        assert ytd["budget_mwh"] == pytest.approx(140.0)

    def test_empty(self):
        ytd = build_ytd_summary([], 2026)
        assert ytd["energy_mwh"] == 0.0
        assert ytd["vs_budget_pct"] is None


# ---------------------------------------------------------------------------
# Portföljinsikter
# ---------------------------------------------------------------------------

def _portfolio_data():
    """Tre parker med känd YTD och senaste stängda månad 2026-07."""
    park_a = make_park(
        [make_month(2026, 6, 100.0, 100.0),
         make_month(2026, 7, 120.0, 100.0,
                    revenue=5000.0, revenue_ppa=5500.0, volume=100.0)],
        name="Alfa", zone="SE3", capacity_mwp=10.0,
    )
    park_b = make_park(
        [make_month(2026, 6, 95.0, 100.0),
         make_month(2026, 7, 80.0, 100.0,
                    revenue=4000.0, revenue_ppa=3800.0, volume=80.0)],
        name="Beta", zone="SE4", capacity_mwp=5.0,
    )
    park_c = make_park(
        [make_month(2026, 7, 101.0, 100.0)],
        name="Gamma", zone="SE3", capacity_mwp=8.0,
    )
    from elpris.insikt.parkoversikt import build_park_summary
    parks = {}
    for key, park in [("alfa", park_a), ("beta", park_b), ("gamma", park_c)]:
        parks[key] = build_park_summary(park)
    return {"parks": parks}


class TestPortfolioInsights:
    def test_returns_two_to_four(self):
        out = build_portfolio_insights(_portfolio_data())
        assert 2 <= len(out) <= 4
        for ins in out:
            assert set(ins) >= {"text", "tone"}
            assert ins["tone"] in ("pos", "neg", "neutral")

    def test_ytd_totals(self):
        out = build_portfolio_insights(_portfolio_data())
        ytd_text = out[0]["text"]
        # 3 parker, 23 MWp, 496 MWh mot 500 MWh budget
        assert "3 parker" in ytd_text
        assert "496" in ytd_text

    def test_best_and_worst_named(self):
        out = build_portfolio_insights(_portfolio_data())
        joined = " ".join(i["text"] for i in out)
        assert "Alfa" in joined   # +20 %
        assert "Beta" in joined   # −20 %

    def test_ppa_effect_when_present(self):
        out = build_portfolio_insights(_portfolio_data())
        joined = " ".join(i["text"] for i in out)
        # +500 (Alfa) − 200 (Beta) = +300 EUR uplift YTD
        assert "PPA" in joined

    def test_dq_insight_singular_park(self):
        # En enda flaggad park → "orsaksanalysen för parken är osäker"
        data = _portfolio_data()
        lc = data["parks"]["beta"]["latest_closed"]
        lc["losses"] = make_losses(100.0, 20.0, irr=0.0)  # residual 80 > 30 %
        out = build_portfolio_insights(data)
        dq = [i for i in out if "instrålningsdata saknas" in i["text"]]
        assert len(dq) == 1
        assert "Beta" in dq[0]["text"]
        assert "parken är osäker" in dq[0]["text"]
        assert "dessa parker" not in dq[0]["text"]

    def test_no_ppa_insight_without_ppa_data(self):
        data = _portfolio_data()
        for p in data["parks"].values():
            for m in p["months"]:
                m["revenue_eur_ppa"] = None
                m["revenue_eur"] = None
        out = build_portfolio_insights(data)
        joined = " ".join(i["text"] for i in out)
        assert "PPA" not in joined
