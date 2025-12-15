"""Batteridimensionering för prognosfelkompensation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from .forecast_error import (
    ForecastErrorModel,
    calculate_deviation_stats,
    calculate_production_stats,
    simulate_forecast_errors,
)


@dataclass
class BatterySpec:
    """Batteridimensionering.

    Attributes:
        power_kw: Maximal effekt (kW)
        energy_kwh: Energikapacitet (kWh)
        round_trip_efficiency: Roundtrip-effektivitet (0-1)
    """
    power_kw: float
    energy_kwh: float
    round_trip_efficiency: float = 0.88

    @property
    def c_rate(self) -> float:
        """C-rate (power/energy ratio)."""
        if self.energy_kwh == 0:
            return 0
        return self.power_kw / self.energy_kwh

    @property
    def max_cycle_energy_kwh(self) -> float:
        """Maximal energi per cykel justerat för effektivitet."""
        return self.energy_kwh * self.round_trip_efficiency

    def __str__(self) -> str:
        return f"{self.power_kw:.0f} kW / {self.energy_kwh:.0f} kWh (C-rate: {self.c_rate:.2f})"


@dataclass
class BatteryCost:
    """Batterikostnad.

    Attributes:
        capex_eur: Total investeringskostnad (EUR)
        energy_cost_eur_kwh: Kostnad per kWh kapacitet
        power_cost_eur_kw: Kostnad per kW effekt
        lifetime_years: Förväntad livslängd
        discount_rate: Diskonteringsränta för annuitetsberäkning
    """
    capex_eur: float
    energy_cost_eur_kwh: float = 500.0
    power_cost_eur_kw: float = 150.0
    lifetime_years: float = 10.0
    discount_rate: float = 0.05

    @property
    def annuity_factor(self) -> float:
        """Annuitetsfaktor för årlig kapitalkostnad."""
        r = self.discount_rate
        n = self.lifetime_years
        if r == 0:
            return 1 / n
        return r * (1 + r) ** n / ((1 + r) ** n - 1)

    @property
    def annual_capex_eur(self) -> float:
        """Årlig kapitalkostnad (EUR)."""
        return self.capex_eur * self.annuity_factor

    @classmethod
    def from_spec(
        cls,
        spec: BatterySpec,
        energy_cost_eur_kwh: float = 500.0,
        power_cost_eur_kw: float = 150.0,
        lifetime_years: float = 10.0,
        discount_rate: float = 0.05,
    ) -> "BatteryCost":
        """Beräkna kostnad från specifikation."""
        capex = spec.energy_kwh * energy_cost_eur_kwh + spec.power_kw * power_cost_eur_kw
        return cls(
            capex_eur=capex,
            energy_cost_eur_kwh=energy_cost_eur_kwh,
            power_cost_eur_kw=power_cost_eur_kw,
            lifetime_years=lifetime_years,
            discount_rate=discount_rate,
        )


@dataclass
class SizingResult:
    """Resultat av batteridimensionering.

    Attributes:
        recommended_spec: Rekommenderad batteristorlek
        design_basis: Antaganden och beräkningar
        alternatives: Alternativa konfigurationer
        cost: Kostnadskalkyl
    """
    recommended_spec: BatterySpec
    design_basis: dict
    alternatives: dict[str, BatterySpec]
    cost: BatteryCost | None = None


def size_for_forecast_error(
    profile_name: str,
    site_capacity_mw: float,
    mape: float = 0.05,
    design_percentile: float = 0.95,
    max_correlation_periods: int = 4,
    use_simulation: bool = False,
    n_simulations: int = 1000,
) -> SizingResult:
    """
    Dimensionera batteri för prognosfelkompensation.

    Args:
        profile_name: Solprofil att använda (t.ex. "south_lundby")
        site_capacity_mw: Installerad kapacitet (MW)
        mape: Mean Absolute Percentage Error (t.ex. 0.05 för 5%)
        design_percentile: Designpercentil (0.95 eller 0.99)
        max_correlation_periods: Max antal korrelerade 15-min perioder
        use_simulation: Använd Monte Carlo-simulering
        n_simulations: Antal simuleringar (om use_simulation=True)

    Returns:
        SizingResult med rekommendation och underlag
    """
    error_model = ForecastErrorModel(
        mape=mape,
        correlation_periods=max_correlation_periods,
    )

    # Hämta produktionsstatistik
    prod_stats = calculate_production_stats(profile_name)

    # Beräkna avvikelser
    dev_stats = calculate_deviation_stats(
        profile_name, site_capacity_mw, error_model
    )

    # Välj designvärden baserat på percentil
    if design_percentile >= 0.99:
        design_power_kw = dev_stats.p99_deviation_kw
        percentile_label = "P99"
    else:
        design_power_kw = dev_stats.p95_deviation_kw
        percentile_label = "P95"

    # Om simulering önskas, använd simulerade värden istället
    if use_simulation:
        sim_results = simulate_forecast_errors(
            profile_name, site_capacity_mw, error_model, n_simulations
        )
        if design_percentile >= 0.99:
            design_power_kw = sim_results["percentiles"]["p99_max_kw"]
            design_energy_kwh = sim_results["percentiles"]["p99_cum_kwh"]
        else:
            design_power_kw = sim_results["percentiles"]["p95_max_kw"]
            design_energy_kwh = sim_results["percentiles"]["p95_cum_kwh"]
    else:
        # Analytisk beräkning av energi
        design_energy_kwh = dev_stats.max_correlated_kwh

    # Runda till praktiska värden
    power_kw = _round_to_practical(design_power_kw, step=25)
    energy_kwh = _round_to_practical(design_energy_kwh, step=25)

    recommended = BatterySpec(power_kw=power_kw, energy_kwh=energy_kwh)

    # Beräkna kostnad
    cost = BatteryCost.from_spec(recommended)

    # Skapa alternativ
    alternatives = {
        "minimal": BatterySpec(
            power_kw=_round_to_practical(dev_stats.mean_deviation_kw * 2, step=25),
            energy_kwh=_round_to_practical(dev_stats.max_correlated_kwh * 0.7, step=25),
        ),
        "conservative": BatterySpec(
            power_kw=_round_to_practical(dev_stats.p99_deviation_kw * 1.1, step=25),
            energy_kwh=_round_to_practical(dev_stats.max_correlated_kwh * 1.5, step=25),
        ),
    }

    # Design basis
    design_basis = {
        "profile_name": profile_name,
        "site_capacity_mw": site_capacity_mw,
        "mape": mape,
        "design_percentile": percentile_label,
        "peak_production_kw": prod_stats.peak_mw * site_capacity_mw * 1000,
        "annual_production_mwh": prod_stats.annual_mwh * site_capacity_mw,
        "error_model": {
            "mape": error_model.mape,
            "std": error_model.std,
            "p95_error": error_model.p95_error,
            "p99_error": error_model.p99_error,
            "correlation_periods": error_model.correlation_periods,
        },
        "deviation_stats": {
            "mean_deviation_kw": dev_stats.mean_deviation_kw,
            "p95_deviation_kw": dev_stats.p95_deviation_kw,
            "p99_deviation_kw": dev_stats.p99_deviation_kw,
            "max_correlated_kwh": dev_stats.max_correlated_kwh,
        },
        "use_simulation": use_simulation,
    }

    return SizingResult(
        recommended_spec=recommended,
        design_basis=design_basis,
        alternatives=alternatives,
        cost=cost,
    )


def calculate_coverage(
    spec: BatterySpec,
    profile_name: str,
    site_capacity_mw: float,
    error_model: ForecastErrorModel,
    n_simulations: int = 1000,
) -> dict:
    """
    Beräkna hur stor andel av prognosfel batteriet täcker.

    Args:
        spec: Batterispecifikation
        profile_name: Solprofil
        site_capacity_mw: Site-kapacitet
        error_model: Prognosfelmodell
        n_simulations: Antal simuleringar

    Returns:
        Dict med coverage_pct, uncovered_events, etc.
    """
    sim_results = simulate_forecast_errors(
        profile_name, site_capacity_mw, error_model, n_simulations
    )

    max_devs = sim_results["max_deviations"]
    cum_devs = sim_results["cumulative_deviations"]

    # Power coverage
    power_covered = sum(1 for d in max_devs if d <= spec.power_kw)
    power_coverage_pct = power_covered / len(max_devs) * 100

    # Energy coverage
    energy_covered = sum(1 for d in cum_devs if d <= spec.energy_kwh)
    energy_coverage_pct = energy_covered / len(cum_devs) * 100

    # Combined coverage (båda måste klaras)
    combined_covered = sum(
        1 for p, e in zip(max_devs, cum_devs)
        if p <= spec.power_kw and e <= spec.energy_kwh
    )
    combined_coverage_pct = combined_covered / len(max_devs) * 100

    return {
        "power_coverage_pct": power_coverage_pct,
        "energy_coverage_pct": energy_coverage_pct,
        "combined_coverage_pct": combined_coverage_pct,
        "uncovered_power_events": len(max_devs) - power_covered,
        "uncovered_energy_events": len(cum_devs) - energy_covered,
        "n_simulations": n_simulations,
    }


def _round_to_practical(value: float, step: float = 25) -> float:
    """Runda till praktiskt värde (uppåt till närmaste step)."""
    import math
    return math.ceil(value / step) * step


def print_sizing_summary(result: SizingResult) -> None:
    """Skriv ut sammanfattning av dimensionering."""
    print("\n" + "=" * 60)
    print("BATTERIDIMENSIONERING FÖR PROGNOSFELKOMPENSATION")
    print("=" * 60)

    basis = result.design_basis
    print(f"\nSite: {basis['profile_name']}, {basis['site_capacity_mw']} MW")
    print(f"Årsproduktion: {basis['annual_production_mwh']:.0f} MWh")
    print(f"Peak-produktion: {basis['peak_production_kw']:.0f} kW")

    print(f"\nPrognosfel (MAPE): {basis['mape']*100:.1f}%")
    print(f"Design-percentil: {basis['design_percentile']}")

    print("\n" + "-" * 40)
    print("REKOMMENDERAD BATTERISTORLEK")
    print("-" * 40)
    spec = result.recommended_spec
    print(f"  Power:  {spec.power_kw:.0f} kW")
    print(f"  Energi: {spec.energy_kwh:.0f} kWh")
    print(f"  C-rate: {spec.c_rate:.2f}")

    if result.cost:
        print(f"\n  Investering: {result.cost.capex_eur:,.0f} EUR")
        print(f"  Årlig kostnad: {result.cost.annual_capex_eur:,.0f} EUR/år")

    print("\n" + "-" * 40)
    print("ALTERNATIV")
    print("-" * 40)
    for name, alt in result.alternatives.items():
        cost = BatteryCost.from_spec(alt)
        print(f"  {name}: {alt} - {cost.capex_eur:,.0f} EUR")

    print("\n" + "=" * 60)
