"""Modellering av solprognosfel för batteridimensionering."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterator, Optional
import math
import random
from statistics import mean

from .solar_profile import load_pvsyst_profile, list_available_profiles


@dataclass
class ForecastErrorModel:
    """Konfiguration för prognosfelmodell.

    Modellerar day-ahead prognosfel för solkraft baserat på MAPE.
    Felet antas vara proportionellt mot produktionen.

    Attributes:
        mape: Mean Absolute Percentage Error (t.ex. 0.05 för 5%)
        std_factor: Standardavvikelse som multipel av MAPE
        correlation_periods: Antal korrelerade 15-min perioder (molnpassage)
    """
    mape: float = 0.05
    std_factor: float = 1.4
    correlation_periods: int = 4

    @property
    def std(self) -> float:
        """Standardavvikelse av felet."""
        return self.mape * self.std_factor

    @property
    def p95_error(self) -> float:
        """95:e percentilen av absolut fel."""
        return self.mape + 1.645 * self.std

    @property
    def p99_error(self) -> float:
        """99:e percentilen av absolut fel."""
        return self.mape + 2.33 * self.std

    def sample_error(self) -> float:
        """Sampla ett prognosfel från fördelningen.

        Returns:
            Relativt fel (kan vara positivt eller negativt)
        """
        # Använd normalfördelning centrerad på 0 med std
        return random.gauss(0, self.std)


@dataclass
class ProductionStats:
    """Statistik över solproduktion från en profil.

    Attributes:
        profile_name: Namnet på profilen
        peak_mw: Maximal produktion (MW per MW installerad)
        annual_mwh: Årlig produktion (MWh per MW installerad)
        monthly_peaks: Peak-produktion per månad
        hourly_avg: Genomsnittlig produktion per timme
    """
    profile_name: str
    peak_mw: float
    annual_mwh: float
    monthly_peaks: dict[int, float] = field(default_factory=dict)
    hourly_avg: dict[int, float] = field(default_factory=dict)
    production_hours: int = 0


def calculate_production_stats(profile_name: str) -> ProductionStats:
    """
    Beräkna produktionsstatistik från solprofil.

    Args:
        profile_name: Namn på PVsyst-profil (t.ex. "south_lundby")

    Returns:
        ProductionStats med peak, årsproduktion, etc.
    """
    profile = load_pvsyst_profile(profile_name)

    # Extrahera alla värden
    values = list(profile.values())

    peak_mw = max(values)
    annual_mwh = sum(values)  # Varje värde är MW för en timme = MWh
    production_hours = sum(1 for v in values if v > 0.001)

    # Monthly peaks
    monthly_peaks: dict[int, float] = {}
    for (month, day, hour), power in profile.items():
        if month not in monthly_peaks or power > monthly_peaks[month]:
            monthly_peaks[month] = power

    # Hourly average
    hourly_sums: dict[int, list[float]] = {h: [] for h in range(24)}
    for (month, day, hour), power in profile.items():
        hourly_sums[hour].append(power)

    hourly_avg = {h: mean(vals) if vals else 0.0 for h, vals in hourly_sums.items()}

    return ProductionStats(
        profile_name=profile_name,
        peak_mw=peak_mw,
        annual_mwh=annual_mwh,
        monthly_peaks=monthly_peaks,
        hourly_avg=hourly_avg,
        production_hours=production_hours,
    )


@dataclass
class DeviationStats:
    """Statistik över prognosavvikelser.

    Attributes:
        mean_deviation_kw: Genomsnittlig avvikelse i kW
        p95_deviation_kw: 95:e percentilen av avvikelse i kW
        p99_deviation_kw: 99:e percentilen av avvikelse i kW
        max_correlated_kwh: Max ackumulerad avvikelse över korrelerade perioder
    """
    mean_deviation_kw: float
    p95_deviation_kw: float
    p99_deviation_kw: float
    max_correlated_kwh: float


def calculate_deviation_stats(
    profile_name: str,
    site_capacity_mw: float,
    error_model: ForecastErrorModel,
) -> DeviationStats:
    """
    Beräkna avvikelsestatistik för given site.

    Args:
        profile_name: Solprofil att använda
        site_capacity_mw: Installerad kapacitet (MW)
        error_model: Prognosfelmodell

    Returns:
        DeviationStats med avvikelser i kW/kWh
    """
    stats = calculate_production_stats(profile_name)

    # Skalera till site-kapacitet
    peak_kw = stats.peak_mw * site_capacity_mw * 1000

    # Beräkna avvikelser
    mean_deviation_kw = peak_kw * error_model.mape
    p95_deviation_kw = peak_kw * error_model.p95_error
    p99_deviation_kw = peak_kw * error_model.p99_error

    # Max ackumulerad avvikelse över korrelerade perioder
    # Antar 15-min perioder = 0.25h
    max_correlated_kwh = (
        error_model.correlation_periods
        * p95_deviation_kw
        * 0.25  # timmar per period
    )

    return DeviationStats(
        mean_deviation_kw=mean_deviation_kw,
        p95_deviation_kw=p95_deviation_kw,
        p99_deviation_kw=p99_deviation_kw,
        max_correlated_kwh=max_correlated_kwh,
    )


def _percentile(data: list[float], p: float) -> float:
    """Beräkna percentil utan numpy."""
    sorted_data = sorted(data)
    n = len(sorted_data)
    k = (n - 1) * (p / 100)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    return sorted_data[f] * (c - k) + sorted_data[c] * (k - f)


def simulate_forecast_errors(
    profile_name: str,
    site_capacity_mw: float,
    error_model: ForecastErrorModel,
    n_simulations: int = 1000,
    seed: int | None = None,
) -> dict:
    """
    Monte Carlo-simulering av prognosfel över ett år.

    Args:
        profile_name: Solprofil att använda
        site_capacity_mw: Installerad kapacitet (MW)
        error_model: Prognosfelmodell
        n_simulations: Antal simuleringar
        seed: Random seed för reproducerbarhet

    Returns:
        Dict med simuleringsresultat:
        - max_deviations: Lista av max avvikelse per år (kW)
        - percentiles: Dict med percentilvärden
        - cumulative_deviations: Max ackumulerad avvikelse per simulering
    """
    if seed is not None:
        random.seed(seed)

    profile = load_pvsyst_profile(profile_name)

    # Konvertera profil till lista
    production = [v * site_capacity_mw * 1000 for v in profile.values()]  # kW

    max_deviations: list[float] = []
    cumulative_deviations: list[float] = []

    for _ in range(n_simulations):
        # Generera korrelerade fel
        errors = [0.0] * len(production)

        for i in range(len(production)):
            if production[i] > 0:
                base_error = error_model.sample_error()

                # Lägg till korrelation med föregående perioder
                if i > 0 and production[i-1] > 0:
                    correlation = 0.7  # Autokorrelation
                    prev_rel_error = errors[i-1] / max(production[i-1], 1)
                    base_error = correlation * prev_rel_error + (1 - correlation) * base_error

                errors[i] = production[i] * base_error

        # Absoluta avvikelser
        abs_deviations = [abs(e) for e in errors]
        max_deviations.append(max(abs_deviations))

        # Ackumulerade avvikelser (rullande summa över korrelationsperioder)
        n_periods = error_model.correlation_periods
        max_cum = 0.0
        for i in range(len(errors) - n_periods + 1):
            cum_sum = sum(errors[i:i + n_periods])
            if abs(cum_sum) > max_cum:
                max_cum = abs(cum_sum)
        cumulative_deviations.append(max_cum * 0.25)  # kWh

    return {
        "max_deviations": max_deviations,
        "cumulative_deviations": cumulative_deviations,
        "percentiles": {
            "p50_max_kw": _percentile(max_deviations, 50),
            "p95_max_kw": _percentile(max_deviations, 95),
            "p99_max_kw": _percentile(max_deviations, 99),
            "p50_cum_kwh": _percentile(cumulative_deviations, 50),
            "p95_cum_kwh": _percentile(cumulative_deviations, 95),
            "p99_cum_kwh": _percentile(cumulative_deviations, 99),
        },
    }


def identify_critical_periods(
    profile_name: str,
    production_threshold_fraction: float = 0.5,
) -> list[dict]:
    """
    Identifiera perioder med hög produktion (stort absolut fel).

    Args:
        profile_name: Solprofil att använda
        production_threshold_fraction: Andel av peak som räknas som kritisk

    Returns:
        Lista av kritiska perioder med month, hour, avg_production
    """
    stats = calculate_production_stats(profile_name)
    profile = load_pvsyst_profile(profile_name)

    threshold = stats.peak_mw * production_threshold_fraction

    # Gruppera per månad-timme kombination
    monthly_hourly: dict[tuple[int, int], list[float]] = {}
    for (month, day, hour), power in profile.items():
        key = (month, hour)
        if key not in monthly_hourly:
            monthly_hourly[key] = []
        monthly_hourly[key].append(power)

    critical = []
    for (month, hour), powers in monthly_hourly.items():
        avg_power = mean(powers) if powers else 0.0
        if avg_power >= threshold:
            critical.append({
                "month": month,
                "hour": hour,
                "avg_production_mw": float(avg_power),
                "days_above_threshold": sum(1 for p in powers if p >= threshold),
            })

    # Sortera efter produktion (högst först)
    critical.sort(key=lambda x: x["avg_production_mw"], reverse=True)

    return critical
