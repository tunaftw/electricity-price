"""Tester för investerarrapporten (elpris.insikt.investerare).

Fokus ligger på det som är produktlöftet: att den exekutiva
sammanfattningen följer sina regler (namnger största avvikaren, döljer
inte datakvalitetsproblem, säger något om YTD), att KPI-aggregeringen
räknar rätt, och att tom data ger en ärlig text istället för en krasch.

Alla tester kör på syntetiska parkstrukturer — inga filsystemsanrop.
"""

from __future__ import annotations

import pytest

from elpris.insikt.investerare import (
    build_executive_summary,
    build_history,
    build_investor_data,
    build_market_context,
    build_park_rows,
    build_portfolio_kpis,
    build_ppa_effect,
    render_investor_html,
)


# ---------------------------------------------------------------------------
# Fixtures — syntetiska parker i samma format som parkoversikt producerar
# ---------------------------------------------------------------------------

def _month(
    year: int,
    month: int,
    energy: float,
    budget: float,
    *,
    losses: dict = None,
    revenue: float = None,
    revenue_ppa: float = None,
    volume: float = None,
    capture: float = None,
    baseload: float = None,
    is_partial: bool = False,
) -> dict:
    vs = round((energy / budget - 1.0) * 100.0, 1) if budget else None
    return {
        "year": year,
        "month": month,
        "is_partial": is_partial,
        "energy_mwh": energy,
        "budget_mwh": budget,
        "vs_budget_pct": vs,
        "losses": losses,
        "revenue_eur": revenue,
        "revenue_eur_ppa": revenue_ppa,
        "bazefield_volume_mwh": volume,
        "capture_eur_mwh": capture,
        "baseload_eur_mwh": baseload,
    }


def _losses(budget: float, actual: float, **components) -> dict:
    out = {
        "budget_mwh": budget,
        "actual_mwh": actual,
        "irradiance_shortfall_mwh": 0.0,
        "availability_mwh": 0.0,
        "temperature_mwh": 0.0,
        "clipping_mwh": 0.0,
        "residual_mwh": 0.0,
    }
    out.update(components)
    return out


@pytest.fixture
def parks() -> dict:
    """Två parker: en normal (Alfa) och en med datalucka (Beta)."""
    return {
        "alfa": {
            "name": "Alfa",
            "zone": "SE3",
            "capacity_mwp": 10.0,
            "months": [
                _month(2026, 5, 900.0, 1000.0),
                _month(
                    2026, 6, 950.0, 1000.0,
                    losses=_losses(1000.0, 950.0, irradiance_shortfall_mwh=40.0),
                    revenue=45000.0, revenue_ppa=48000.0, volume=950.0,
                    capture=47.4, baseload=60.0,
                ),
            ],
        },
        "beta": {
            "name": "Beta",
            "zone": "SE4",
            "capacity_mwp": 20.0,
            "months": [
                _month(2026, 5, 1900.0, 2000.0),
                # Instrålning 0 + residual > 30 % av budget → DQ-flagga
                _month(
                    2026, 6, 400.0, 2000.0,
                    losses=_losses(2000.0, 400.0, residual_mwh=1600.0),
                    revenue=18000.0, revenue_ppa=17000.0, volume=400.0,
                    capture=45.0, baseload=60.0,
                ),
            ],
        },
    }


# ---------------------------------------------------------------------------
# Park-rader och KPI:er
# ---------------------------------------------------------------------------

def test_park_rows_speglar_manadsraden(parks):
    rows = build_park_rows(parks, 2026, 6)
    by_name = {r["name"]: r for r in rows}
    assert by_name["Alfa"]["energy_mwh"] == 950.0
    assert by_name["Alfa"]["vs_budget_pct"] == -5.0
    # YTD summerar maj + juni, inte hela året
    assert by_name["Alfa"]["ytd_energy_mwh"] == 1850.0
    assert by_name["Alfa"]["ytd_budget_mwh"] == 2000.0
    assert by_name["Alfa"]["ytd_vs_budget_pct"] == -7.5


def test_park_rows_klipper_vid_rapportmanaden(parks):
    """En rapport för maj får inte innehålla juni."""
    rows = build_park_rows(parks, 2026, 5)
    alfa = next(r for r in rows if r["name"] == "Alfa")
    assert alfa["energy_mwh"] == 900.0
    assert alfa["ytd_energy_mwh"] == 900.0


def test_park_rows_utan_data_ger_tom_rad(parks):
    rows = build_park_rows(parks, 2026, 4)
    assert len(rows) == 2
    assert all(r["energy_mwh"] is None for r in rows)
    assert all(not r["has_month"] for r in rows)


def test_dq_flagga_undertrycker_skenbar_orsak(parks):
    """Residualen förklarar inte något när instrålningsdata saknas."""
    rows = build_park_rows(parks, 2026, 6)
    beta = next(r for r in rows if r["name"] == "Beta")
    assert beta["dq_flag"] is True
    assert beta["cause"] is None
    alfa = next(r for r in rows if r["name"] == "Alfa")
    assert alfa["dq_flag"] is False
    assert "instrålning" in alfa["cause"]


def test_portfolio_kpis_summerar_och_volymviktar(parks):
    kpis = build_portfolio_kpis(build_park_rows(parks, 2026, 6))
    assert kpis["energy_mwh"] == 1350.0
    assert kpis["budget_mwh"] == 3000.0
    assert kpis["vs_budget_pct"] == -55.0
    assert kpis["ytd_energy_mwh"] == 4150.0
    assert kpis["ytd_budget_mwh"] == 6000.0
    assert kpis["ytd_vs_budget_pct"] == -30.8
    assert kpis["park_count"] == 2
    assert kpis["reporting_park_count"] == 2
    assert kpis["capacity_mwp"] == 30.0
    # Capture volymviktas: (45000 + 18000) / (950 + 400)
    assert kpis["capture_eur_mwh"] == pytest.approx(46.7, abs=0.05)
    assert kpis["baseload_eur_mwh"] == pytest.approx(60.0, abs=0.05)
    assert kpis["capture_premium_pct"] == pytest.approx(-22.2, abs=0.2)
    assert kpis["revenue_eur"] == 63000
    assert kpis["revenue_eur_ppa"] == 65000


def test_portfolio_kpis_utan_budget_ger_none():
    rows = build_park_rows(
        {"x": {"name": "X", "zone": "SE3", "capacity_mwp": 1.0,
               "months": [_month(2026, 6, 100.0, 0.0)]}},
        2026, 6,
    )
    kpis = build_portfolio_kpis(rows)
    assert kpis["energy_mwh"] == 100.0
    assert kpis["vs_budget_pct"] is None
    assert kpis["capture_eur_mwh"] is None


def test_historik_hoppar_over_manader_utan_data(parks):
    hist = build_history(parks, 2026, 6, n=13)
    assert [h["month"] for h in hist] == ["2026-05", "2026-06"]
    assert hist[-1]["is_report_month"] is True
    assert hist[0]["is_report_month"] is False
    assert hist[-1]["energy_mwh"] == 1350.0


def test_ppa_effekt_ytd(parks):
    ppa = build_ppa_effect(parks, 2026, 6)
    # Alfa +3000, Beta −1000
    assert ppa["uplift_eur"] == 2000
    assert ppa["park_count"] == 2
    assert ppa["parks"] == ["Alfa", "Beta"]


def test_ppa_effekt_none_utan_kontraktsdata():
    parks = {"x": {"name": "X", "zone": "SE3", "capacity_mwp": 1.0,
                   "months": [_month(2026, 6, 100.0, 100.0, revenue=5000.0)]}}
    assert build_ppa_effect(parks, 2026, 6) is None


# ---------------------------------------------------------------------------
# Exekutiv sammanfattning — produktlöftet
# ---------------------------------------------------------------------------

def _summary(parks, year=2026, month=6):
    rows = build_park_rows(parks, year, month)
    data = {
        "period": {
            "year": year, "month": month,
            "month_label": "juni", "label": f"juni {year}",
        },
        "portfolio": build_portfolio_kpis(rows),
        "parks": rows,
    }
    return build_executive_summary(data)


def test_sammanfattning_har_tre_till_fyra_meningar(parks):
    assert 3 <= len(_summary(parks)) <= 4


def test_sammanfattning_leder_med_manadens_utfall(parks):
    first = _summary(parks)[0]
    assert "juni 2026" in first
    assert "under budget" in first


def test_sammanfattning_namner_storsta_avvikaren(parks):
    text = " ".join(_summary(parks))
    # Beta (−80 %) avviker mer än Alfa (−5 %)
    assert "Beta" in text
    assert "−80,0 %" in text or "−80 %" in text


def test_sammanfattning_namner_dq_flagga_nar_sadan_finns(parks):
    text = " ".join(_summary(parks))
    assert "Instrålningsdata saknas" in text
    assert "Beta" in text
    assert "osäker" in text


def test_sammanfattning_utan_dq_flagga_redovisar_capture(parks):
    """Utan datakvalitetsproblem används sista meningen till capture."""
    clean = {"alfa": parks["alfa"]}
    text = " ".join(_summary(clean))
    assert "Instrålningsdata saknas" not in text
    assert "capture-pris" in text
    assert "baseload" in text


def test_sammanfattning_har_ytd_mening(parks):
    assert any("Hittills i år" in s for s in _summary(parks))


def test_sammanfattning_dominerande_orsak_nar_den_gar_att_peka_ut(parks):
    clean = {"alfa": parks["alfa"]}
    text = " ".join(_summary(clean))
    assert "instrålning" in text


def test_sammanfattning_sager_ifran_nar_ingen_park_avviker():
    parks = {
        "a": {"name": "A", "zone": "SE3", "capacity_mwp": 1.0,
              "months": [_month(2026, 6, 1000.0, 1000.0)]},
        "b": {"name": "B", "zone": "SE3", "capacity_mwp": 1.0,
              "months": [_month(2026, 6, 1010.0, 1000.0)]},
    }
    text = " ".join(_summary(parks))
    assert "Ingen enskild park avvek" in text


def test_sammanfattning_tom_data_ger_arlig_text():
    summary = _summary({})
    assert len(summary) == 1
    assert "Ingen stängd produktionsdata" in summary[0]


def test_sammanfattning_tom_data_kraschar_inte_pa_saknade_nycklar():
    assert build_executive_summary({}) == [
        "Ingen stängd produktionsdata finns för perioden — rapporten kan "
        "inte sammanfatta utfallet."
    ]


# ---------------------------------------------------------------------------
# Marknadskontext
# ---------------------------------------------------------------------------

def test_marknadskontext_begransas_till_portfoljens_zoner():
    market = {
        "SE1": {"2026-06": {"avg": 5.0, "neg_hours": 20.0}},
        "SE3": {"2026-06": {"avg": 50.0, "neg_hours": 1.0},
                "2026-05": {"avg": 40.0, "neg_hours": 0.0}},
        "SE4": {"2026-06": {"avg": 80.0, "neg_hours": 0.0}},
    }
    ctx = build_market_context(market, 2026, 6, portfolio_zones={"SE3", "SE4"})
    assert [z["zone"] for z in ctx["zones"]] == ["SE3", "SE4"]
    assert "SE1" not in " ".join(ctx["sentences"])
    assert len(ctx["sentences"]) <= 3


def test_marknadskontext_none_utan_data():
    assert build_market_context({}, 2026, 6) is None
    assert build_market_context(
        {"SE3": {"2026-05": {"avg": 1.0, "neg_hours": 0.0}}}, 2026, 6
    ) is None


# ---------------------------------------------------------------------------
# Byggning + rendering från ände till ände (utan filsystem)
# ---------------------------------------------------------------------------

def _fake_parkoversikt(parks: dict) -> dict:
    return {"parks": parks, "kpis": {"latest_closed_month": "2026-06"}}


def test_build_investor_data_valjer_senaste_stangda_manad(parks):
    data = build_investor_data(
        parkoversikt=_fake_parkoversikt(parks), obalans={}, market={}
    )
    assert data["period"]["month_key"] == "2026-06"
    assert data["period"]["label"] == "juni 2026"
    assert data["portfolio"]["energy_mwh"] == 1350.0
    assert data["summary"]


def test_build_investor_data_respekterar_vald_manad(parks):
    data = build_investor_data(
        2026, 5, parkoversikt=_fake_parkoversikt(parks),
        obalans={}, market={},
    )
    assert data["period"]["month_key"] == "2026-05"
    assert data["portfolio"]["energy_mwh"] == 2800.0
    assert data["imbalance"] is None
    assert data["market"] is None


def test_rendering_ar_fristaende_och_utskriftsvanlig(parks):
    data = build_investor_data(
        parkoversikt=_fake_parkoversikt(parks), obalans={}, market={}
    )
    html = render_investor_html(data)
    assert html.startswith("<!DOCTYPE html>")
    # Ingen CDN, ingen JS — rapporten ska gå att mejla och skriva ut offline.
    # Enda tillåtna URL:en är SVG-namnrymden (inte en nätverksbegäran).
    without_ns = html.replace("http://www.w3.org/2000/svg", "")
    assert "http://" not in without_ns
    assert "https://" not in without_ns
    assert "<script" not in html
    # Utskriftsregler
    assert "@media print" in html
    assert "size: A4 portrait" in html
    # Grafen är inline-SVG
    assert "<svg" in html
    # Avvikelsen döljs inte
    assert "Beta" in html
    assert "Instrålningsdata saknas" in html


def test_rendering_tom_portfolj_kraschar_inte():
    data = build_investor_data(
        2026, 6, parkoversikt={"parks": {}}, obalans={}, market={}
    )
    html = render_investor_html(data)
    assert "Ingen stängd produktionsdata" in html
    assert "Ingen historik tillgänglig" in html
