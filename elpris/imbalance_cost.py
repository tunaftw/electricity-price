"""Beräkning av obalansintäkter/-kostnader."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from .battery_sizing import BatterySpec
from .forecast_error import ForecastErrorModel, calculate_production_stats


@dataclass
class ImbalanceCostParams:
    """Parametrar för obalansberäkning.

    Svenska elmarknaden använder tvåprismodell för obalanser.
    Priserna beror på systemets totala obalans.

    Attributes:
        up_regulation_penalty_eur_mwh: Extra kostnad vid underskott
        down_regulation_penalty_eur_mwh: Intäktsförlust vid överskott
        avg_spot_price_eur_mwh: Genomsnittligt spotpris för referens
    """
    up_regulation_penalty_eur_mwh: float = 25.0
    down_regulation_penalty_eur_mwh: float = 15.0
    avg_spot_price_eur_mwh: float = 50.0


@dataclass
class ImbalanceCostResult:
    """Resultat av obalansberäkning.

    Attributes:
        annual_imbalance_mwh: Total obalans per år (MWh)
        annual_cost_eur: Årlig obalans-kostnad (EUR)
        cost_per_mwh_produced: Kostnad per MWh producerad energi
        breakdown: Detaljerad uppdelning
    """
    annual_imbalance_mwh: float
    annual_cost_eur: float
    cost_per_mwh_produced: float
    breakdown: dict


def calculate_imbalance_cost(
    profile_name: str,
    site_capacity_mw: float,
    mape: float,
    params: ImbalanceCostParams | None = None,
) -> ImbalanceCostResult:
    """
    Beräkna årlig obalans-kostnad utan batteri.

    Antaganden:
    - Prognosfelet är symmetriskt fördelat (lika mycket över som under)
    - Genomsnittlig penalty appliceras på all obalans

    Args:
        profile_name: Solprofil
        site_capacity_mw: Site-kapacitet (MW)
        mape: Mean Absolute Percentage Error
        params: Kostnadparametrar (använder default om None)

    Returns:
        ImbalanceCostResult med årlig kostnad
    """
    if params is None:
        params = ImbalanceCostParams()

    # Hämta produktionsstatistik
    prod_stats = calculate_production_stats(profile_name)
    annual_production_mwh = prod_stats.annual_mwh * site_capacity_mw

    # Beräkna total obalans
    annual_imbalance_mwh = annual_production_mwh * mape

    # Antag 50/50 fördelning mellan upp- och nedreglering
    up_regulation_mwh = annual_imbalance_mwh / 2
    down_regulation_mwh = annual_imbalance_mwh / 2

    # Beräkna kostnader
    up_cost = up_regulation_mwh * params.up_regulation_penalty_eur_mwh
    down_cost = down_regulation_mwh * params.down_regulation_penalty_eur_mwh
    total_cost = up_cost + down_cost

    # Kostnad per MWh producerad
    cost_per_mwh = total_cost / annual_production_mwh if annual_production_mwh > 0 else 0

    breakdown = {
        "annual_production_mwh": annual_production_mwh,
        "up_regulation_mwh": up_regulation_mwh,
        "down_regulation_mwh": down_regulation_mwh,
        "up_regulation_cost_eur": up_cost,
        "down_regulation_cost_eur": down_cost,
        "up_regulation_penalty": params.up_regulation_penalty_eur_mwh,
        "down_regulation_penalty": params.down_regulation_penalty_eur_mwh,
    }

    return ImbalanceCostResult(
        annual_imbalance_mwh=annual_imbalance_mwh,
        annual_cost_eur=total_cost,
        cost_per_mwh_produced=cost_per_mwh,
        breakdown=breakdown,
    )


@dataclass
class BatterySavingsResult:
    """Resultat av batteribesparingsberäkning.

    Attributes:
        imbalance_cost_without_battery: Obalans-kostnad utan batteri
        imbalance_cost_with_battery: Obalans-kostnad med batteri
        annual_savings_eur: Årlig besparing
        battery_annual_cost_eur: Årlig batterikostnad
        net_benefit_eur: Netto nytta (besparing - batterikostnad)
        payback_years: Återbetalningstid
    """
    imbalance_cost_without_battery: float
    imbalance_cost_with_battery: float
    annual_savings_eur: float
    battery_annual_cost_eur: float
    net_benefit_eur: float
    payback_years: float | None


def calculate_battery_savings(
    profile_name: str,
    site_capacity_mw: float,
    mape: float,
    battery_spec: BatterySpec,
    coverage_pct: float = 95.0,
    battery_capex_eur: float | None = None,
    battery_lifetime_years: float = 10.0,
    discount_rate: float = 0.05,
    imbalance_params: ImbalanceCostParams | None = None,
) -> BatterySavingsResult:
    """
    Beräkna årlig besparing med batteri.

    Args:
        profile_name: Solprofil
        site_capacity_mw: Site-kapacitet (MW)
        mape: Mean Absolute Percentage Error
        battery_spec: Batterispecifikation
        coverage_pct: Andel av obalanser som batteriet täcker (%)
        battery_capex_eur: Total investeringskostnad (beräknas om None)
        battery_lifetime_years: Batterilivslängd
        discount_rate: Diskonteringsränta
        imbalance_params: Obalans-kostnadparametrar

    Returns:
        BatterySavingsResult med netto nytta och återbetalningstid
    """
    from .battery_sizing import BatteryCost

    # Beräkna obalans-kostnad utan batteri
    cost_without = calculate_imbalance_cost(
        profile_name, site_capacity_mw, mape, imbalance_params
    )

    # Med batteri reduceras obalansen
    residual_fraction = 1 - (coverage_pct / 100)
    cost_with_battery = cost_without.annual_cost_eur * residual_fraction

    annual_savings = cost_without.annual_cost_eur - cost_with_battery

    # Batterikostnad
    if battery_capex_eur is None:
        battery_cost = BatteryCost.from_spec(
            battery_spec,
            lifetime_years=battery_lifetime_years,
            discount_rate=discount_rate,
        )
        battery_capex_eur = battery_cost.capex_eur
        battery_annual_cost = battery_cost.annual_capex_eur
    else:
        # Beräkna annuitet manuellt
        r = discount_rate
        n = battery_lifetime_years
        if r == 0:
            annuity = 1 / n
        else:
            annuity = r * (1 + r) ** n / ((1 + r) ** n - 1)
        battery_annual_cost = battery_capex_eur * annuity

    net_benefit = annual_savings - battery_annual_cost

    # Payback (enkel, utan diskontering)
    if annual_savings > 0:
        payback_years = battery_capex_eur / annual_savings
    else:
        payback_years = None

    return BatterySavingsResult(
        imbalance_cost_without_battery=cost_without.annual_cost_eur,
        imbalance_cost_with_battery=cost_with_battery,
        annual_savings_eur=annual_savings,
        battery_annual_cost_eur=battery_annual_cost,
        net_benefit_eur=net_benefit,
        payback_years=payback_years,
    )


def print_imbalance_summary(
    profile_name: str,
    site_capacity_mw: float,
    mape: float,
    battery_spec: BatterySpec | None = None,
    coverage_pct: float = 95.0,
) -> None:
    """Skriv ut sammanfattning av obalans-analys."""
    print("\n" + "=" * 60)
    print("OBALANSANALYS")
    print("=" * 60)

    # Utan batteri
    cost = calculate_imbalance_cost(profile_name, site_capacity_mw, mape)

    print(f"\nSite: {profile_name}, {site_capacity_mw} MW")
    print(f"Årsproduktion: {cost.breakdown['annual_production_mwh']:.0f} MWh")
    print(f"Prognosfel (MAPE): {mape*100:.1f}%")

    print("\n" + "-" * 40)
    print("OBALANS UTAN BATTERI")
    print("-" * 40)
    print(f"  Årlig obalans: {cost.annual_imbalance_mwh:.1f} MWh")
    print(f"  Årlig kostnad: {cost.annual_cost_eur:,.0f} EUR")
    print(f"  Kostnad/MWh:   {cost.cost_per_mwh_produced:.2f} EUR/MWh")

    if battery_spec:
        savings = calculate_battery_savings(
            profile_name, site_capacity_mw, mape, battery_spec, coverage_pct
        )

        print("\n" + "-" * 40)
        print(f"MED BATTERI ({battery_spec}, {coverage_pct}% coverage)")
        print("-" * 40)
        print(f"  Obalans-kostnad: {savings.imbalance_cost_with_battery:,.0f} EUR/år")
        print(f"  Besparing:       {savings.annual_savings_eur:,.0f} EUR/år")
        print(f"  Batterikostnad:  {savings.battery_annual_cost_eur:,.0f} EUR/år")
        print(f"  Netto nytta:     {savings.net_benefit_eur:,.0f} EUR/år")
        if savings.payback_years:
            print(f"  Payback:         {savings.payback_years:.1f} år")

    print("\n" + "=" * 60)
