"""Kannibaliseringskoefficient — OLS av capture ratio mot installerad sol.

Rework-dashboarden visar redan capture ratio och installerad solkapacitet
bredvid varandra, men lämnar åt läsaren att dra slutsatsen. Den här modulen
gör kopplingen citerbar:

    "Ytterligare 1 GW installerad sol i zonen sammanfaller med
     −X procentenheter lägre capture ratio (95 % KI …, R² = …, n = … år)."

Metod
-----
Enkel OLS (minsta kvadrat) på **årsdata** per elområde:

* ``y`` = capture ratio för profilen ``sol_syd``, uttryckt i
  **procentenheter** (ratio × 100).
* ``x`` = installerad solkapacitet i zonen, i **GW**.

Regressionen bygger alltså på TMY-profilviktade capture-ratios — samma
serie som cannibalization-analysen i ``rework_capture_analysis`` och med
samma kända skevhet: PVsyst-profilerna överskattar solcapture med ~10 % i
medel mot ENTSO-E:s faktiska nationella solproduktion, och avvikelsen
växer med solpenetrationen (se
``docs/insights/2026-04-05-pvsyst-vs-entsoe-validation.md``). Eftersom en
fast TMY-profil per konstruktion *inte* fångar kannibalisering är den här
koefficienten sannolikt en **underskattning** av den verkliga effekten:
den mäter hur mycket prisformen i zonen har försämrats för en oförändrad
produktionsform.

Viktiga avgränsningar
---------------------
* Bara **kompletta år** från och med ``MIN_YEAR`` ingår. Innevarande
  partiella år ingår ALDRIG i fitten — det är säsongsskevt.
* Energimyndighetens installerade kapacitet slutar 2024 medan
  ratio-serien fortsätter. Åren däremellan **extrapoleras** linjärt med
  de senaste tre årens genomsnittliga årliga tillskott (MW/år) och
  flaggas med ``installed_extrapolated: true``.
* Detta är en **korrelation på fyra–sex observationer**, inte ett
  kausalt estimat. Enskilda år styrs minst lika mycket av bränslepriser,
  vattenläge och kärnkraftstillgänglighet som av solutbyggnaden. R²
  redovisas alltid och insikterna bär en brasklapp när R² < 0,7.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

from ..config import ZONES
from ..rework_capture_analysis import load_installed_capacity
from ..rework_portfolio import fmt_num

# Första år som får ingå i regressionen. Spotdata börjar 2021-11-01, så i
# praktiken blir första kompletta året 2022 — konstanten finns för att
# kunna klippa bort strukturellt avvikande tidigare år om historiken
# någon gång backfillas.
MIN_YEAR = 2020

# Minsta antal årsobservationer för att över huvud taget rapportera en
# koefficient. Under detta flaggas zonen "insufficient_data".
MIN_YEARS = 4

# Antal år bakåt som medelvärdesbildar tillväxttakten vid extrapolering.
GROWTH_LOOKBACK_YEARS = 3

# Tvåsidiga t-kvantiler för 95 % konfidensintervall, per frihetsgrad
# (df = n − 2). Hårdkodade eftersom repot är stdlib-only (ingen scipy).
# Värdena är standardtabell, avrundade till tre decimaler.
T_QUANTILE_95: Dict[int, float] = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
}

# Fallback för df > 10: normalapproximationen. Något för snäv (t.ex.
# t(11) = 2,201 mot 1,960) men skillnaden är liten och df > 10 kräver
# minst 13 årsobservationer — långt bortom nuvarande historik.
Z_QUANTILE_95 = 1.960

# PVsyst-profilen regressionen använder (samma som cannibalization-vyn).
RATIO_PROFILE = "sol_syd"
_PVSYST_PROFILE_FILE = "south_lundby"

# Minsta antal dagar med spotdata för att ett år ska räknas som komplett.
# 365 fungerar även för skottår (366 dagar ≥ 365).
_COMPLETE_YEAR_DAYS = 365

_INSTALLED_CACHE: Optional[dict] = None


# ---------------------------------------------------------------------------
# Ren OLS (stdlib)
# ---------------------------------------------------------------------------

def t_quantile_95(df: int) -> Optional[float]:
    """Tvåsidig t-kvantil för 95 % KI vid ``df`` frihetsgrader.

    Returnerar ``None`` för df < 1 (då finns inget KI att tala om) och
    normalapproximationen 1,960 för df > 10.
    """
    if df < 1:
        return None
    if df in T_QUANTILE_95:
        return T_QUANTILE_95[df]
    return Z_QUANTILE_95


def ols_fit(points: Sequence[Tuple[float, float]]) -> dict:
    """Enkel linjär regression ``y = intercept + slope · x`` med stdlib.

    Args:
        points: sekvens av ``(x, y)``.

    Returns:
        dict med ``n``, ``slope``, ``intercept``, ``r2``, ``stderr``
        (standardfel på lutningen), ``t_crit``, ``df``, ``ci_low``,
        ``ci_high``, ``mean_x``, ``mean_y``.

        Fält som inte går att beräkna är ``None``:

        * n < 2, eller all x lika (Sxx = 0) → ``slope``/``intercept`` None.
        * Sxx > 0 men Syy = 0 (helt platt y) → ``r2`` None, slope = 0.
        * df < 1 (n = 2) → ``stderr``/``ci_*`` None.

        En perfekt linje ger ``r2 = 1.0``, ``stderr = 0.0`` och ett
        KI-band med bredd noll — matematiskt korrekt, men i praktiken en
        varning om att observationerna är för få.
    """
    n = len(points)
    empty = {
        "n": n, "slope": None, "intercept": None, "r2": None,
        "stderr": None, "t_crit": None, "df": max(n - 2, 0),
        "ci_low": None, "ci_high": None,
        "mean_x": None, "mean_y": None,
    }
    if n < 2:
        return empty

    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    sxx = sum((x - mean_x) ** 2 for x in xs)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    syy = sum((y - mean_y) ** 2 for y in ys)

    if sxx <= 0.0:
        # Ingen variation i x — lutningen är odefinierad.
        empty["mean_x"] = mean_x
        empty["mean_y"] = mean_y
        return empty

    slope = sxy / sxx
    intercept = mean_y - slope * mean_x

    ss_res = sum(
        (y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys)
    )
    # Numeriskt brus kan ge ett minimalt negativt ss_res på perfekta linjer.
    if ss_res < 0.0:
        ss_res = 0.0
    r2 = 1.0 - ss_res / syy if syy > 0.0 else None

    df = n - 2
    stderr = t_crit = ci_low = ci_high = None
    if df >= 1:
        stderr = math.sqrt((ss_res / df) / sxx)
        t_crit = t_quantile_95(df)
        if t_crit is not None:
            ci_low = slope - t_crit * stderr
            ci_high = slope + t_crit * stderr

    return {
        "n": n,
        "slope": slope,
        "intercept": intercept,
        "r2": r2,
        "stderr": stderr,
        "t_crit": t_crit,
        "df": df,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "mean_x": mean_x,
        "mean_y": mean_y,
    }


# ---------------------------------------------------------------------------
# Installerad kapacitet: extrapolering
# ---------------------------------------------------------------------------

def average_annual_growth(
    records: Sequence[dict], lookback: int = GROWTH_LOOKBACK_YEARS
) -> Optional[float]:
    """Genomsnittligt årligt tillskott (MW/år) över de senaste åren.

    Absolut tillskott, inte procentuell CAGR: solutbyggnaden växer
    superlinjärt, och en CAGR-extrapolering exploderar på två års sikt.
    Linjär framskrivning är medvetet konservativ — den underskattar
    sannolikt utbyggnaden och därmed den projicerade kannibaliseringen.

    Luckor i serien hanteras: tillskottet divideras med antalet år mellan
    observationerna, så ett hopp 2019 → 2022 räknas som tre årstillskott.

    Args:
        records: ``[{"year": int, "mw": float}, ...]``, godtycklig ordning.
        lookback: antal årsdiffar som medelvärdesbildas (de senaste).

    Returns:
        MW per år, eller ``None`` om det finns färre än två observationer.
    """
    series = sorted(records, key=lambda r: r["year"])
    if len(series) < 2:
        return None
    diffs = []
    for i in range(1, len(series)):
        span = series[i]["year"] - series[i - 1]["year"]
        if span <= 0:
            continue
        diffs.append((series[i]["mw"] - series[i - 1]["mw"]) / span)
    if not diffs:
        return None
    tail = diffs[-lookback:] if lookback > 0 else diffs
    return sum(tail) / len(tail)


def extrapolate_installed(
    records: Sequence[dict], through_year: int
) -> Tuple[List[dict], Optional[float]]:
    """Förläng installerad-serien till och med ``through_year``.

    Faktiska år behåller ``installed_extrapolated: False``; framskrivna år
    får ``True`` så att renderaren kan markera dem.

    Returns:
        ``(serie, growth_mw_per_year)``. Serien är sorterad på år. Om
        tillväxttakten inte går att beräkna (< 2 observationer) returneras
        serien oförlängd och growth = ``None``.
    """
    series = [
        {
            "year": int(r["year"]),
            "mw": float(r["mw"]),
            "installed_extrapolated": False,
        }
        for r in sorted(records, key=lambda r: r["year"])
    ]
    if not series:
        return [], None

    growth = average_annual_growth(series)
    if growth is None:
        return series, None

    last_year = series[-1]["year"]
    for year in range(last_year + 1, through_year + 1):
        prev = series[-1]
        series.append({
            "year": year,
            "mw": round(prev["mw"] + growth, 1),
            "installed_extrapolated": True,
        })
    return series, growth


# ---------------------------------------------------------------------------
# Dataladdning (capture ratio per år)
# ---------------------------------------------------------------------------

def load_ratio_yearly(zone: str) -> List[dict]:
    """Årlig capture ratio för ``sol_syd`` i en zon, med komplett-flagga.

    Beräknas med samma byggstenar som dashboard_v2 (PVsyst-profilviktad
    capture mot kvartersspot), men laddar bara spot + en profil — inte
    hela unified-kedjan.

    Returns:
        ``[{"year", "ratio", "capture", "baseload", "days", "complete"}]``
        sorterat på år. Tom lista om spot- eller profildata saknas.
    """
    from ..dashboard_v2_data import (  # lokalt: undvik tung import vid modulladdning
        _aggregate_to_yearly,
        _calculate_profile_capture,
        load_pvsyst_profile,
        load_spot_prices,
    )

    spot = load_spot_prices(zone)
    if not spot:
        return []
    profile = load_pvsyst_profile(_PVSYST_PROFILE_FILE)
    if not profile:
        return []

    daily = _calculate_profile_capture(spot, profile)
    if not daily:
        return []

    days_per_year: Dict[int, int] = {}
    for rec in daily.values():
        days_per_year[rec["year"]] = days_per_year.get(rec["year"], 0) + 1

    out: List[dict] = []
    for rec in _aggregate_to_yearly(daily):
        days = days_per_year.get(rec["year"], 0)
        out.append({
            "year": rec["year"],
            "ratio": rec.get("ratio"),
            "capture": rec.get("capture"),
            "baseload": rec.get("baseload"),
            "days": days,
            "complete": days >= _COMPLETE_YEAR_DAYS,
        })
    return out


def _installed_solar() -> Dict[str, List[dict]]:
    """Installerad sol per zon/år (cachad — läser CSV en gång)."""
    global _INSTALLED_CACHE
    if _INSTALLED_CACHE is None:
        _INSTALLED_CACHE = load_installed_capacity()
    return _INSTALLED_CACHE.get("solar", {}) or {}


# ---------------------------------------------------------------------------
# Regression per zon
# ---------------------------------------------------------------------------

def _insufficient(zone: str, reason: str, points: List[dict], n: int) -> dict:
    return {
        "zone": zone,
        "status": "insufficient_data",
        "reason": reason,
        "n": n,
        "points": points,
        "slope_pp_per_gw": None,
        "intercept_pp": None,
        "r2": None,
        "stderr_pp_per_gw": None,
        "ci95_low": None,
        "ci95_high": None,
        "df": None,
        "t_crit": None,
        "years_used": [],
        "growth_mw_per_year": None,
        "installed_actual_through": None,
        "significant": None,
    }


def _is_significant(ci_low: Optional[float], ci_high: Optional[float]) -> Optional[bool]:
    """True om 95 %-KI utesluter noll (lutningen är skild från noll).

    SE1/SE2 har nästan ingen variation i x (tiotals MW installerad sol),
    vilket ger en lutning med ett KI som spänner hundratals procentenheter.
    Flaggan gör den skillnaden maskinläsbar utan att någon zon hårdkodas.
    """
    if ci_low is None or ci_high is None:
        return None
    return ci_low > 0.0 or ci_high < 0.0


def fit_cannibalization(
    zone: str,
    ratio_yearly: Optional[Sequence[dict]] = None,
    installed_solar: Optional[Sequence[dict]] = None,
    min_year: int = MIN_YEAR,
    min_years: int = MIN_YEARS,
) -> dict:
    """OLS: capture ratio (procentenheter) mot installerad sol (GW).

    Args:
        zone: elområde, t.ex. ``"SE3"``.
        ratio_yearly: valfri injicerad ratio-serie
            (``[{"year", "ratio", "complete", ...}]``). Laddas annars via
            :func:`load_ratio_yearly`.
        installed_solar: valfri injicerad installerad-serie
            (``[{"year", "mw"}]``). Laddas annars från Energimyndighetens
            CSV via ``rework_capture_analysis.load_installed_capacity``.
        min_year: tidigaste år som får ingå.
        min_years: minsta antal observationer för ``status="ok"``.

    Returns:
        dict med ``status`` (``"ok"`` | ``"insufficient_data"``),
        ``slope_pp_per_gw`` (procentenheter capture ratio per GW),
        ``intercept_pp``, ``r2``, ``n``, ``df``, ``stderr_pp_per_gw``,
        ``ci95_low``/``ci95_high``, ``t_crit``, ``years_used``,
        ``growth_mw_per_year``, ``installed_actual_through`` och
        ``points`` (per-år-observationerna för scatterplot).
    """
    ratios = (
        list(ratio_yearly)
        if ratio_yearly is not None
        else load_ratio_yearly(zone)
    )
    installed_raw = (
        list(installed_solar)
        if installed_solar is not None
        else _installed_solar().get(zone, [])
    )

    usable_ratios = [
        r for r in sorted(ratios, key=lambda r: r["year"])
        if r.get("ratio") is not None
        and int(r["year"]) >= min_year
        # Saknad complete-flagga tolkas som komplett (injicerad testdata).
        and r.get("complete", True)
    ]
    if not usable_ratios:
        return _insufficient(zone, "inga kompletta år med capture ratio", [], 0)
    if not installed_raw:
        return _insufficient(
            zone, "ingen installerad solkapacitet för zonen", [], 0
        )

    installed_actual_through = max(int(r["year"]) for r in installed_raw)
    last_ratio_year = max(int(r["year"]) for r in usable_ratios)
    installed_series, growth = extrapolate_installed(
        installed_raw, max(last_ratio_year, installed_actual_through)
    )
    installed_by_year = {r["year"]: r for r in installed_series}

    points: List[dict] = []
    xy: List[Tuple[float, float]] = []
    for rec in usable_ratios:
        year = int(rec["year"])
        inst = installed_by_year.get(year)
        if inst is None:
            continue
        gw = inst["mw"] / 1000.0
        ratio_pp = float(rec["ratio"]) * 100.0
        points.append({
            "year": year,
            "installed_mw": round(inst["mw"], 1),
            "installed_gw": round(gw, 4),
            "installed_extrapolated": inst["installed_extrapolated"],
            "ratio": rec.get("ratio"),
            "ratio_pp": round(ratio_pp, 2),
            "capture": rec.get("capture"),
            "baseload": rec.get("baseload"),
        })
        xy.append((gw, ratio_pp))

    if len(xy) < min_years:
        return _insufficient(
            zone,
            f"bara {len(xy)} år med både ratio och installerad kapacitet "
            f"(kräver {min_years})",
            points,
            len(xy),
        )

    fit = ols_fit(xy)
    if fit["slope"] is None:
        return _insufficient(
            zone, "ingen variation i installerad kapacitet", points, len(xy)
        )

    return {
        "zone": zone,
        "status": "ok",
        "slope_pp_per_gw": round(fit["slope"], 3),
        "intercept_pp": round(fit["intercept"], 3),
        "r2": round(fit["r2"], 4) if fit["r2"] is not None else None,
        "n": fit["n"],
        "df": fit["df"],
        "stderr_pp_per_gw": (
            round(fit["stderr"], 3) if fit["stderr"] is not None else None
        ),
        "ci95_low": (
            round(fit["ci_low"], 3) if fit["ci_low"] is not None else None
        ),
        "ci95_high": (
            round(fit["ci_high"], 3) if fit["ci_high"] is not None else None
        ),
        "t_crit": fit["t_crit"],
        "significant": _is_significant(fit["ci_low"], fit["ci_high"]),
        "mean_installed_gw": (
            round(fit["mean_x"], 4) if fit["mean_x"] is not None else None
        ),
        "years_used": [p["year"] for p in points],
        "profile": RATIO_PROFILE,
        "growth_mw_per_year": (
            round(growth, 1) if growth is not None else None
        ),
        "installed_actual_through": installed_actual_through,
        "points": points,
    }


# ---------------------------------------------------------------------------
# Framskrivning
# ---------------------------------------------------------------------------

def project_ratio(
    zone: str,
    years_ahead: int = 2,
    fit: Optional[dict] = None,
) -> List[dict]:
    """Förväntad capture ratio kommande år vid fortsatt utbyggnadstakt.

    Installerad kapacitet skrivs fram med samma genomsnittliga årliga
    tillskott som i :func:`fit_cannibalization`, och regressionslinjen
    utvärderas i den framskrivna punkten.

    Osäkerhetsbandet propagerar **enbart lutningens** osäkerhet, uttryckt
    i centrerad form::

        ŷ(x) = ȳ + slope · (x − x̄)
        ± t₀.₉₅(df) · SE_slope · |x − x̄|

    Interceptets (och residualernas) osäkerhet ignoreras medvetet — bandet
    är alltså **smalare** än ett äkta prediktionsintervall och ska läsas
    som "hur mycket lutningens osäkerhet ensam flyttar prognosen", inte
    som ett fullständigt konfidensintervall för utfallet.

    Args:
        zone: elområde.
        years_ahead: antal år efter sista fit-året.
        fit: valfritt förberäknat resultat från :func:`fit_cannibalization`.

    Returns:
        ``[{"year", "installed_mw", "installed_gw", "ratio_pp",
        "ratio_pp_low", "ratio_pp_high", "installed_extrapolated": True},
        ...]``. Tom lista om regressionen saknas eller är otillräcklig.
    """
    f = fit if fit is not None else fit_cannibalization(zone)
    if f.get("status") != "ok" or not f.get("points"):
        return []
    growth = f.get("growth_mw_per_year")
    if growth is None:
        return []

    slope = f["slope_pp_per_gw"]
    intercept = f["intercept_pp"]
    mean_x = f.get("mean_installed_gw")
    stderr = f.get("stderr_pp_per_gw")
    t_crit = f.get("t_crit")

    last = f["points"][-1]
    out: List[dict] = []
    mw = last["installed_mw"]
    for i in range(1, max(years_ahead, 0) + 1):
        year = last["year"] + i
        mw = mw + growth
        gw = mw / 1000.0
        pred = intercept + slope * gw
        low = high = None
        if stderr is not None and t_crit is not None and mean_x is not None:
            band = t_crit * stderr * abs(gw - mean_x)
            low, high = pred - band, pred + band
        out.append({
            "year": year,
            "installed_mw": round(mw, 1),
            "installed_gw": round(gw, 4),
            "installed_extrapolated": True,
            "ratio_pp": round(pred, 2),
            "ratio_pp_low": round(low, 2) if low is not None else None,
            "ratio_pp_high": round(high, 2) if high is not None else None,
        })
    return out


# ---------------------------------------------------------------------------
# Sektionsdata + insikter
# ---------------------------------------------------------------------------

def build_kannibalisering_data(
    zones: Optional[Sequence[str]] = None,
    years_ahead: int = 2,
    ratio_yearly_by_zone: Optional[Dict[str, Sequence[dict]]] = None,
    installed_by_zone: Optional[Dict[str, Sequence[dict]]] = None,
) -> dict:
    """Regression + framskrivning för alla elområden.

    Ingen zon är hårdkodad som "fungerande": varje zon körs genom samma
    regression och den som saknar underlag får
    ``status="insufficient_data"`` med en läsbar ``reason``.

    Args:
        zones: elområden att köra (default: ``config.ZONES``).
        years_ahead: antal framskrivna år per zon.
        ratio_yearly_by_zone: valfri injicerad ratio-data per zon (tester).
        installed_by_zone: valfri injicerad installerad-data per zon.

    Returns:
        ``{"profile", "min_year", "min_years", "zones": {zon: fit + projection},
        "best_zone", "assumptions": [...]}``
    """
    zone_list = list(zones) if zones is not None else list(ZONES)
    results: Dict[str, dict] = {}
    for zone in zone_list:
        fit = fit_cannibalization(
            zone,
            ratio_yearly=(
                (ratio_yearly_by_zone or {}).get(zone)
                if ratio_yearly_by_zone is not None else None
            ),
            installed_solar=(
                (installed_by_zone or {}).get(zone)
                if installed_by_zone is not None else None
            ),
        )
        fit["projection"] = (
            project_ratio(zone, years_ahead=years_ahead, fit=fit)
            if fit.get("status") == "ok" else []
        )
        results[zone] = fit

    # Starkast kannibalisering = mest negativ lutning. Zoner vars KI
    # utesluter noll går före — annars skulle en brusdominerad zon med
    # nästan ingen x-variation kunna vinna på en slumpmässig lutning.
    ok = [f for f in results.values() if f.get("status") == "ok"]
    ranked = [f for f in ok if f.get("significant")] or ok
    best = min(ranked, key=lambda f: f["slope_pp_per_gw"]) if ranked else None

    return {
        "profile": RATIO_PROFILE,
        "min_year": MIN_YEAR,
        "min_years": MIN_YEARS,
        "zones": results,
        "best_zone": best["zone"] if best else None,
        "assumptions": [
            "Capture ratio kommer från den TMY-baserade PVsyst-profilen "
            "sol_syd — samma serie som cannibaliseringsvyn. En fast profil "
            "fångar inte formförändringen i den faktiska flottan, så "
            "koefficienten är sannolikt en underskattning.",
            "Endast kompletta kalenderår från och med "
            f"{MIN_YEAR} ingår; innevarande partiella år utesluts alltid.",
            "Energimyndighetens installerade kapacitet slutar 2024. "
            "Senare år skrivs fram linjärt med de senaste tre årens "
            "genomsnittliga årliga tillskott och flaggas "
            "installed_extrapolated.",
            "Konfidensintervallet är slopens 95 % t-intervall. "
            "Framskrivningens band propagerar bara slope-osäkerheten "
            "(intercept och residualspridning ignoreras) och är därför "
            "smalare än ett äkta prediktionsintervall.",
            "Fyra till sex årsobservationer per zon: detta är en "
            "korrelation, inte ett kausalt estimat.",
        ],
    }


def _fmt_pp(value: Optional[float], decimals: int = 1) -> str:
    """Procentenheter med svenskt minustecken."""
    if value is None:
        return "–"
    sign = "−" if value < 0 else ""
    return f"{sign}{fmt_num(abs(value), decimals)}"


def build_kannibalisering_insights(data: dict) -> List[dict]:
    """Klartextinsikter (svenska) ur :func:`build_kannibalisering_data`.

    Returns:
        ``[{"text": str, "tone": "pos"|"neg"|"neutral"}, ...]``
    """
    insights: List[dict] = []
    zones = (data or {}).get("zones", {}) or {}
    ok = [f for f in zones.values() if f.get("status") == "ok"]
    if not ok:
        insights.append({
            "text": (
                "Underlaget räcker inte för en kannibaliseringsregression — "
                "det krävs minst "
                f"{data.get('min_years', MIN_YEARS)} kompletta år med både "
                "capture ratio och installerad solkapacitet per elområde."
            ),
            "tone": "neutral",
        })
        return insights

    ranked = [f for f in ok if f.get("significant")] or ok
    lead = min(ranked, key=lambda f: f["slope_pp_per_gw"])
    slope = lead["slope_pp_per_gw"]
    ci_low, ci_high = lead.get("ci95_low"), lead.get("ci95_high")
    ci_txt = (
        f" (95 % KI {_fmt_pp(ci_low)}…{_fmt_pp(ci_high)})"
        if ci_low is not None and ci_high is not None else ""
    )

    if slope < 0:
        insights.append({
            "text": (
                f"{lead['zone']}: varje ytterligare GW installerad sol i "
                f"elområdet sammanfaller med {_fmt_pp(abs(slope))} "
                f"procentenheter lägre capture ratio för en sydvänd "
                f"solprofil{ci_txt}. "
                f"R² = {fmt_num(lead.get('r2'), 2)} på {lead['n']} årsobservationer "
                f"({lead['years_used'][0]}–{lead['years_used'][-1]})."
            ),
            "tone": "neg",
        })
    else:
        # Ingen efterhandskonstruktion: rapportera tecknet som det är.
        insights.append({
            "text": (
                f"Ingen zon visar negativ lutning. Starkast samband är "
                f"{lead['zone']} med {_fmt_pp(slope)} procentenheter capture "
                f"ratio per GW installerad sol{ci_txt}, R² = "
                f"{fmt_num(lead.get('r2'), 2)} på {lead['n']} år. Ett positivt "
                f"tecken betyder att prisformen i zonen dominerats av andra "
                f"faktorer än solutbyggnaden under perioden — inte att "
                f"kannibalisering saknas."
            ),
            "tone": "neutral",
        })

    # Övriga zoner, kort sammanställning.
    others = [f for f in ok if f["zone"] != lead["zone"]]
    if others:
        parts = []
        for f in sorted(others, key=lambda f: f["zone"]):
            mark = "" if f.get("significant") else ", ej signifikant"
            parts.append(
                f"{f['zone']} {_fmt_pp(f['slope_pp_per_gw'])} p.e./GW "
                f"(R² {fmt_num(f.get('r2'), 2)}{mark})"
            )
        insights.append({
            "text": (
                "Övriga elområden: " + ", ".join(parts) + ". "
                "'Ej signifikant' betyder att 95 %-intervallet spänner över "
                "noll — i norr är den installerade solen så liten att det "
                "inte finns någon utbyggnadsvariation att mäta mot."
            ),
            "tone": "neutral",
        })

    insufficient = sorted(
        f["zone"] for f in zones.values()
        if f.get("status") != "ok"
    )
    if insufficient:
        insights.append({
            "text": (
                "Otillräckligt underlag för regression i "
                + ", ".join(insufficient)
                + " — för få kompletta år med både capture ratio och "
                "installerad solkapacitet."
            ),
            "tone": "neutral",
        })

    # Framskrivning för ledande zon.
    proj = lead.get("projection") or []
    if proj:
        last = proj[-1]
        growth = lead.get("growth_mw_per_year")
        band = ""
        if last.get("ratio_pp_low") is not None:
            band = (
                f" (band {_fmt_pp(last['ratio_pp_low'])}–"
                f"{_fmt_pp(last['ratio_pp_high'])} %)"
            )
        insights.append({
            "text": (
                f"Om utbyggnaden fortsätter i samma takt "
                f"(+{fmt_num(growth, 0)} MW/år i {lead['zone']}) landar "
                f"capture ratio på cirka {_fmt_pp(last['ratio_pp'])} % "
                f"{last['year']}{band}, mot "
                f"{_fmt_pp(lead['points'][-1]['ratio_pp'])} % "
                f"{lead['points'][-1]['year']}."
            ),
            "tone": "neg" if last["ratio_pp"] < lead["points"][-1]["ratio_pp"]
            else "neutral",
        })

    # Ärlig brasklapp när lutningen inte ens är skild från noll.
    if lead.get("significant") is False:
        insights.append({
            "text": (
                f"Brasklapp: {lead['zone']}:s 95 %-intervall spänner över noll "
                f"— med det underlaget går det inte att belägga någon "
                f"kannibaliseringseffekt alls, bara att beskriva riktningen."
            ),
            "tone": "neutral",
        })

    # Ärlig brasklapp när förklaringsgraden är svag.
    r2 = lead.get("r2")
    if r2 is not None and r2 < 0.7:
        insights.append({
            "text": (
                f"Brasklapp: R² = {fmt_num(r2, 2)} betyder att solutbyggnaden "
                f"bara förklarar {fmt_num(r2 * 100, 0)} % av variationen i "
                f"{lead['zone']}:s capture ratio. Resten drivs av bränslepriser, "
                f"vattenläge och kärnkraftstillgänglighet — koefficienten är "
                f"en riktning, inte en prognosmotor."
            ),
            "tone": "neutral",
        })

    # Extrapolerad installerad kapacitet ska alltid nämnas.
    if any(p.get("installed_extrapolated") for p in lead.get("points", [])):
        insights.append({
            "text": (
                "Installerad solkapacitet är officiell till och med "
                f"{lead.get('installed_actual_through')}; senare år i "
                "regressionen är linjärt framskrivna."
            ),
            "tone": "neutral",
        })

    return insights
