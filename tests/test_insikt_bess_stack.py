"""Enhetstester för elpris.insikt.bess_stack (revenue stacking-DP).

Alla tester körs på syntetiska dygn — inga filberoenden. Valideringspunkter
från spec:en:

(a) extrem spread + inga reservpriser → ren arbitrage, handräknad optimal
    intäkt.
(b) noll spread + högt FCR-pris (ned, kräver bara headroom) → 24 h reserv,
    intäkt = 24 × pris × acceptance.
(c) blandat dygn där optimum kräver att SoC laddas INFÖR en aFRR-upp-timme.
(d) invarianten stacked ≥ max(arb_only, bästa ancillary-only) på 20
    slumpdygn (seedad PRNG).
(e) cykelkostnad ↑ ⇒ cycles ↓ (monotoni).
(f) headroom-kravet blockerar fcr_d_down vid full SoC.

Plus: FCR-N-diskretiseringsartefakten vid 1h (dokumenterad i modulen),
acceptansskalning och tidsstämpelkonvertering Mimer-lokaltid → UTC.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris.insikt.bess_stack import (  # noqa: E402
    ALL_RESERVE_PRODUCTS,
    CYCLE_COST_EUR_PER_MWH,
    _ts_to_utc_day_hour,
    optimize_stack_day,
    reserve_feasible,
)

EFF = 0.88
CC = CYCLE_COST_EUR_PER_MWH  # 8.0


def _flat(price: float, n: int = 24) -> list:
    return [float(price)] * n


def _no_reserves() -> dict:
    return {}


# ---------------------------------------------------------------------------
# (a) Extrem spread + noll reservpriser → ren arbitrage, handräknat
# ---------------------------------------------------------------------------

def test_pure_arbitrage_known_optimum_1h():
    # Enda intressanta timmen är h12 = 100, resten 0.
    # Optimalt: ladda gratis (0 EUR), urladda h12:
    #   100 × 0.88 − 8 (cykelkostnad) = 80.00
    # Inga fler lönsamma cykler (urladdning vid pris 0 ger −8).
    prices = [0.0] * 12 + [100.0] + [0.0] * 11
    res = optimize_stack_day(prices, _no_reserves(), capacity_mwh=1.0)
    assert res["revenue_eur"] == pytest.approx(80.0)
    assert res["hours_charge"] == 1
    assert res["hours_discharge"] == 1
    assert res["cycles"] == pytest.approx(1.0)
    assert res["hours_by_product"] == {}
    # Med reservprodukter som alla har pris 0 ska optimum vara identiskt.
    zero_res = {p: [0.0] * 24 for p in ALL_RESERVE_PRODUCTS}
    res2 = optimize_stack_day(prices, zero_res, capacity_mwh=1.0)
    assert res2["revenue_eur"] == pytest.approx(80.0)


def test_pure_arbitrage_two_spikes_2h():
    # Kapacitet 2 MWh, två pristoppar → två urladdningar.
    # Ladda h0+h1 (kostnad 2 × 10 = 20), urladda h10 och h20 à 200:
    #   2 × (200 × 0.88 − 8) − 20 = 2 × 168 − 20 = 316.
    prices = [10.0] * 24
    prices[10] = 200.0
    prices[20] = 200.0
    res = optimize_stack_day(prices, _no_reserves(), capacity_mwh=2.0)
    assert res["revenue_eur"] == pytest.approx(316.0)
    assert res["cycles"] == pytest.approx(1.0)  # 2 MWh genomströmning / 2 MWh


# ---------------------------------------------------------------------------
# (b) Noll spread + högt reservpris → 24 h reserv
# ---------------------------------------------------------------------------

def test_full_day_reserve_fcr_d_down():
    # fcr_d_down kräver bara headroom (0.34) — uppfyllt vid SoC 0 hela
    # dygnet. Noll spread → arbitrage värdelöst. Förväntat: 24 h reserv.
    prices = _flat(0.0)
    reserves = {"fcr_d_down": [50.0] * 24}
    res = optimize_stack_day(prices, reserves, capacity_mwh=1.0)
    assert res["revenue_eur"] == pytest.approx(24 * 50.0)
    assert res["hours_by_product"] == {"fcr_d_down": 24}
    assert res["cycles"] == 0.0
    assert res["hours_charge"] == 0 and res["hours_discharge"] == 0


def test_full_day_reserve_scales_with_acceptance():
    prices = _flat(0.0)
    reserves = {"fcr_d_down": [50.0] * 24}
    res = optimize_stack_day(
        prices, reserves, capacity_mwh=1.0, acceptance_rate=0.5
    )
    assert res["revenue_eur"] == pytest.approx(24 * 50.0 * 0.5)
    assert res["hours_by_product"] == {"fcr_d_down": 24}


# ---------------------------------------------------------------------------
# (c) DP:n laddar INFÖR en aFRR-upp-timme
# ---------------------------------------------------------------------------

def test_charges_ahead_of_afrr_up_hour():
    # Platta priser (10) → arbitrage-rundtur olönsam
    # (−10 + 8.8 − 8 = −9.2). aFRR upp (kräver SoC ≥ 1.0) betalar 500
    # ENDAST timme 5. Optimum: ladda någon timme < 5 (−10), committa
    # h5 (+500), och töm sedan lagret en timme (10 × 0.88 − 8 = +0.8).
    # Totalt: −10 + 500 + 0.8 = 490.8.
    prices = _flat(10.0)
    afrr_up = [None] * 24
    afrr_up[5] = 500.0
    reserves = {"afrr_up": afrr_up}
    res = optimize_stack_day(prices, reserves, capacity_mwh=1.0)
    assert res["revenue_eur"] == pytest.approx(490.8)
    assert res["hours_by_product"] == {"afrr_up": 1}
    assert res["hours_charge"] == 1
    assert res["hours_discharge"] == 1
    # Utan laddning hade reserven varit ogörlig: verifiera att ett
    # batteri som inte får ladda (kapacitet 0-fallet täcks separat)
    # inte kan nå 500-intäkten — arb_only på samma dygn är 0.
    res_arb = optimize_stack_day(prices, reserves, capacity_mwh=1.0,
                                 products=())
    assert res_arb["revenue_eur"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# (d) Invariant: stacked ≥ max(arb_only, bästa ancillary_only) på slumpdygn
# ---------------------------------------------------------------------------

def test_invariant_stacked_ge_singles_on_random_days():
    rng = random.Random(42)
    for day in range(20):
        prices = [rng.uniform(-20.0, 150.0) for _ in range(24)]
        reserves = {}
        for p in ALL_RESERVE_PRODUCTS:
            series = [
                None if rng.random() < 0.3 else rng.uniform(0.0, 60.0)
                for _ in range(24)
            ]
            reserves[p] = series

        for capacity in (1.0, 2.0, 4.0):
            stacked = optimize_stack_day(prices, reserves, capacity)
            arb = optimize_stack_day(prices, reserves, capacity,
                                     products=())
            singles = [arb["revenue_eur"]]
            for p in ALL_RESERVE_PRODUCTS:
                anc = optimize_stack_day(
                    prices, reserves, capacity,
                    arbitrage_revenue=False, products=(p,),
                )
                singles.append(anc["revenue_eur"])
            # 0.011 EUR tolerans: varje dygnsvärde avrundas till 2 dec.
            assert stacked["revenue_eur"] >= max(singles) - 0.011, (
                f"dag {day}, kapacitet {capacity}: "
                f"stacked {stacked['revenue_eur']} < max(singlar) "
                f"{max(singles)}"
            )
            assert stacked["revenue_eur"] >= -0.011  # idle är alltid möjligt


# ---------------------------------------------------------------------------
# (e) Cykelkostnad ↑ ⇒ cycles ↓ (monotoni)
# ---------------------------------------------------------------------------

def test_cycle_cost_monotonically_reduces_cycles():
    # Sågtandspriser med rejäl spread → många cykler lönar sig vid låg
    # cykelkostnad, färre vid hög.
    prices = [5.0 if h % 2 == 0 else 90.0 for h in range(24)]
    prev_cycles = None
    for cc in (0.0, 8.0, 30.0, 100.0):
        res = optimize_stack_day(
            prices, _no_reserves(), capacity_mwh=1.0,
            cycle_cost_eur_per_mwh=cc,
        )
        if prev_cycles is not None:
            assert res["cycles"] <= prev_cycles + 1e-9
        prev_cycles = res["cycles"]
    # Vid absurd cykelkostnad ska batteriet stå still.
    assert prev_cycles == 0.0


# ---------------------------------------------------------------------------
# (f) Headroom-kravet blockerar fcr_d_down vid full SoC
# ---------------------------------------------------------------------------

def test_reserve_feasible_headroom_blocks_at_full_soc():
    # Direkta feasibility-kontroller.
    assert reserve_feasible("fcr_d_down", soc_mwh=0.0, capacity_mwh=1.0)
    assert not reserve_feasible("fcr_d_down", soc_mwh=1.0, capacity_mwh=1.0)
    assert not reserve_feasible("afrr_down", soc_mwh=4.0, capacity_mwh=4.0)
    assert reserve_feasible("afrr_down", soc_mwh=3.0, capacity_mwh=4.0)
    # Uppregleringskrav: energi.
    assert not reserve_feasible("afrr_up", soc_mwh=0.0, capacity_mwh=2.0)
    assert reserve_feasible("afrr_up", soc_mwh=1.0, capacity_mwh=2.0)
    # Okänd produkt → aldrig feasible.
    assert not reserve_feasible("okänd", soc_mwh=1.0, capacity_mwh=2.0)


def test_full_soc_blocks_fcr_d_down_in_dp():
    # Batteri som STARTAR fullt (initial_soc_mwh = kapacitet), absurd
    # cykelkostnad (ingen urladdning) och fcr_d_down-pris bara timme 0:
    # headroom-kravet gör reserven ogörlig → intäkt 0.
    prices = _flat(0.0)
    reserves = {"fcr_d_down": [100.0] + [None] * 23}
    res_full = optimize_stack_day(
        prices, reserves, capacity_mwh=1.0,
        cycle_cost_eur_per_mwh=1e6, initial_soc_mwh=1.0,
    )
    assert res_full["revenue_eur"] == pytest.approx(0.0)
    assert res_full["hours_by_product"] == {}
    # Kontroll: tomt batteri kan committa → 100.
    res_empty = optimize_stack_day(
        prices, reserves, capacity_mwh=1.0,
        cycle_cost_eur_per_mwh=1e6, initial_soc_mwh=0.0,
    )
    assert res_empty["revenue_eur"] == pytest.approx(100.0)
    assert res_empty["hours_by_product"] == {"fcr_d_down": 1}


# ---------------------------------------------------------------------------
# FCR-N-diskretiseringsartefakten (dokumenterad i modul-docstringen)
# ---------------------------------------------------------------------------

def test_fcr_n_infeasible_at_1h_feasible_at_2h():
    # 1h-batteri med 1 MWh-steg: SoC 0 saknar energi, SoC 1 saknar
    # headroom → FCR-N kan aldrig committas (känd artefakt).
    prices = _flat(0.0)
    reserves = {"fcr_n": [100.0] * 24}
    res1 = optimize_stack_day(prices, reserves, capacity_mwh=1.0)
    assert res1["revenue_eur"] == pytest.approx(0.0)
    # 2h-batteri: ladda 1 timme (gratis vid pris 0) → SoC 1 uppfyller
    # både energi- och headroom-kravet → 23 timmar FCR-N à 100.
    res2 = optimize_stack_day(prices, reserves, capacity_mwh=2.0)
    assert res2["revenue_eur"] == pytest.approx(2300.0)
    assert res2["hours_by_product"] == {"fcr_n": 23}
    assert res2["hours_charge"] == 1


# ---------------------------------------------------------------------------
# ancillary_only-varianten: urladdning ger ingen spotintäkt
# ---------------------------------------------------------------------------

def test_ancillary_only_discharge_earns_nothing():
    # Hög spread men arbitrage_revenue=False → urladdning ger bara
    # cykelkostnad. Utan reservprodukter i products blir optimum 0
    # (idle hela dygnet — ladda+urladda vore ren kostnad).
    prices = [0.0] * 12 + [500.0] + [0.0] * 11
    res = optimize_stack_day(
        prices, {"fcr_d_down": [None] * 24}, capacity_mwh=1.0,
        arbitrage_revenue=False, products=("fcr_d_down",),
    )
    assert res["revenue_eur"] == pytest.approx(0.0)
    assert res["hours_discharge"] == 0


# ---------------------------------------------------------------------------
# Tomma/degenererade indata
# ---------------------------------------------------------------------------

def test_empty_day_returns_zero():
    res = optimize_stack_day([], _no_reserves(), capacity_mwh=2.0)
    assert res["revenue_eur"] == 0.0
    assert res["hours_idle"] == 0


def test_zero_capacity_returns_zero():
    res = optimize_stack_day(_flat(50.0), _no_reserves(), capacity_mwh=0.0)
    assert res["revenue_eur"] == 0.0


# ---------------------------------------------------------------------------
# Mimer-tidsstämpel → UTC-dygn/timme
# ---------------------------------------------------------------------------

def test_ts_conversion_naive_local_winter():
    # 2025-01-15 00:00 CET = 2025-01-14 23:00 UTC.
    assert _ts_to_utc_day_hour("2025-01-15T00:00:00") == ("2025-01-14", 23)


def test_ts_conversion_naive_local_summer():
    # 2025-07-15 00:00 CEST = 2025-07-14 22:00 UTC.
    assert _ts_to_utc_day_hour("2025-07-15T00:00:00") == ("2025-07-14", 22)


def test_ts_conversion_aware_utc_passthrough():
    assert _ts_to_utc_day_hour("2025-07-15T00:00:00Z") == ("2025-07-15", 0)


def test_ts_conversion_garbage_returns_none():
    assert _ts_to_utc_day_hour("inte-en-tidsstämpel") is None
