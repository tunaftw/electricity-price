"""Realiserad obalanskostnad per park och månad — simulerad prognos.

Bakgrund
========
Portföljen saknar sparade produktionsprognoser, så den *faktiska*
obalanskostnaden kan inte återskapas exakt. Men vi har (i) faktisk
15-min-produktion per park (Bazefield, ``effective_power_mw``) och
(ii) eSett:s 15-min-obalanspriser per zon. Det räcker för att SIMULERA
vad en given prognosstrategi hade kostat i obalansavräkningen — en riktig
EUR-siffra i stället för prisklimat-proxyn i ``rework_imbalance``.

Osäkerheten om verklig prognoskvalitet redovisas som ett SPANN mellan två
prognosproxies (a) och (b) — ingen falsk precision.

Metodik (för granskning av energihandlare)
==========================================

Avräkningsmodell (produktionsobalans)
-------------------------------------
Per 15-min-kvart::

    diff = faktisk_energi − prognos_energi          [MWh]
    energi = effective_power_mw × 0,25 h            (MW → MWh per kvart)

Positiv ``diff`` = producerade mer än nominerat; överskottet säljs till
eSett:s ``imbl_sales_price_eur_mwh``. Negativ ``diff`` = underskott som
köps tillbaka till ``imbl_purchase_price_eur_mwh``. Kostnaden uttrycks
RELATIVT PERFEKT PROGNOS (dvs. relativt att hela volymen sålts till spot)::

    kostnad = diff⁺ × (spot − sales) + |diff⁻| × (purchase − spot)   [EUR]

* Om obalanspriserna == spot är kostnaden exakt 0 oavsett prognosfel.
* I nordisk ENPRISMODELL för produktion (sales == purchase sedan
  2021-11-01) kan kostnaden per kvart bli NEGATIV (= vinst): obalans i
  systemets hjälpriktning ersätts bättre än spot. Sign behålls; vi
  rapporterar både **netto** (Σ termer, vinster kvittar förluster) och
  **brutto** (Σ |termer|, total friktion). Andelen kvartar med
  sales == purchase rapporteras som verifiering (``single_price_share_pct``).

Prognosproxies
--------------
(a) **Persistens (D-1)**: prognos(t) = faktisk produktion samma kvart
    föregående dygn (t − 24 h i UTC). Saknas D-1-värdet hoppas kvarten
    över (syns i täckningsgraden). Approximerar en naiv dagen-före-
    nominering utan väderprognos — en ÖVRE gräns för vad en riktig
    prognostjänst bör kosta.
(b) **Budgetform**: parkens PVsyst-månadsbudget (``park_config.get_budget``)
    fördelad över månadens kvartar enligt månadens *genomsnittliga
    faktiska dygnsform* (medelenergi per lokal kvart-på-dygnet, beräknad
    ur parkens egen data för månaden), normaliserad så att prognosens
    månadsenergi == budgetens. Approximerar en "perfekt säsongsprognos
    utan väderinformation": rätt form och rätt månadsvolym (om budgeten
    träffar), men noll dag-till-dag-väderinformation.

Jämförbarhet: båda proxies utvärderas på SAMMA kvartsmängd — kvartar där
parkdata, spotpris, eSett-priser OCH D-1-värdet finns. Därmed mäter
skillnaden a↔b prognoskvalitet, inte datatäckning.

Tid och enheter
---------------
* Parkdata: ``timestamp_utc`` (tz-aware UTC) från ``load_park_15min``.
* eSett: ``time_start`` med "Z"-suffix → parsas till UTC.
* Spot: quarterly-CSV med lokal offset (+01/+02) → konverteras till UTC.
  Join sker på exakt UTC-kvart.
* Priser i EUR/MWh (spot-CSV:ns ``EUR_per_kWh`` × 1000). Energi i MWh.
* Månadsbucketing i svensk lokaltid (CET/CEST), konsekvent med resten av
  projektet (``local_year_month``). Dygnsformen i proxy (b) beräknas
  också på lokal kvart-på-dygnet (solen följer lokal tid).
* D-1 i proxy (a) tas som t − 24 h UTC; över DST-omställningen skiftar
  det en timme mot lokal walltime två dygn per år — försumbart.

Täckning och trösklar
---------------------
``coverage_pct`` = utvärderade kvartar / kalenderkvartar i månaden
(DST-exakta: 92/96/100 kvartar per dygn). Månader med < 10 % täckning
utelämnas ur resultatet. 12-månadersaggregat kräver ≥ 50 % täckning per
ingående månad; €/MWh-nyckeltal är volymviktade (Σ kostnad / Σ MWh).

Kända förenklingar
------------------
* ``effective_power_mw`` (mätare, annars inverter) är avräkningsproxyn;
  vid mätarbortfall skiljer den något från faktiskt avräknad volym.
* Persistensen nomineras "kl 00:00 D-1" snarare än vid spotauktionens
  deadline (D-1 ca 12:00) — skillnaden är noll för persistens per
  definition (värdet är känt) men modellen ignorerar möjlig intradags-
  handel, dvs. detta är obalanskostnad UTAN intradagsjustering.
* Budgetproxyn använder månadens egen genomsnittsform (facit i efterhand
  för formen) — den är avsiktligt en mild variant, ändå typiskt dyrare än
  persistens eftersom den missar allt dag-till-dag-väder.

API
===
* ``build_obalans_data(months_back=24)`` → dict med per-park-månader,
  12-mån-aggregat och portföljtotal.
* ``build_obalans_insights(data)`` → klartextinsikter [{"text","tone"}].
* Rena hjälpfunktioner (``interval_cost``, ``persistence_forecast``,
  ``budget_shape_forecast``, ``settle_monthly``) för enhetstestning.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from ..config import (
    ESETT_DATA_DIR,
    PARK_ZONES,
    QUARTERLY_DIR,
    SWEDEN_TZ,
    UTC_TZ,
    parse_iso,
)
from ..operations_dashboard_data import load_park_15min
from ..park_config import get_budget

QUARTER_HOURS = 0.25
QUARTER_SECONDS = 900

# Månader med lägre täckning än så utelämnas helt.
MIN_MONTH_COVERAGE_PCT = 10.0
# Månader som får ingå i 12-mån-aggregatet.
MIN_AGG_COVERAGE_PCT = 50.0


# ---------------------------------------------------------------------------
# Dataladdning
# ---------------------------------------------------------------------------

# Nattvakt: inverter-rapporterad effekt med POA under den här nivån är
# fysiskt omöjlig för sol och behandlas som sensorfel (stuck value).
NIGHT_POA_WM2 = 5.0
MIN_REAL_POWER_MW = 0.01


def energies_from_records(records: List[dict]) -> Dict[datetime, float]:
    """Faktisk energi (MWh) per UTC-kvart ur ``load_park_15min``-records.

    Datakvalitetsvakt utöver ``load_park_15min``:s heldygnsdetektor:
    kvartar där effekten kommer från inverter-fallback (mätare saknas),
    POA-instrålningen är ≤ ``NIGHT_POA_WM2`` W/m² och effekten ändå är
    > ``MIN_REAL_POWER_MW`` nollställs — solproduktion utan ljus är ett
    fastnat sensorvärde (observerat: björke 2025-03-22, ActivePower fast
    på 4,28 MW hela natten med POA = 0). Utan vakten möter sådana kvartar
    ibland extrema obalanspriser (±10 000 €/MWh) och dominerar månader.
    Mätarsignalen litas alltid på; saknas POA-data släpps värdet igenom.
    """
    out: Dict[datetime, float] = {}
    for rec in records:
        effective = rec["effective_power_mw"]
        poa = rec.get("irradiance_poa")
        if (
            effective > MIN_REAL_POWER_MW
            and rec.get("power_mw", 0) <= 0
            and poa is not None
            and poa <= NIGHT_POA_WM2
        ):
            effective = 0.0
        out[rec["timestamp_utc"]] = effective * QUARTER_HOURS
    return out


def load_park_energies(park_key: str) -> Dict[datetime, float]:
    """Faktisk energi (MWh) per UTC-kvart för en park.

    Bygger på ``effective_power_mw`` (mätare → inverter-fallback med
    stuck-value-sanering) från ``load_park_15min``, plus nattvakten i
    ``energies_from_records``.
    """
    return energies_from_records(load_park_15min(park_key))


def load_spot_quarters(zone: str) -> Dict[datetime, float]:
    """Spotpris (EUR/MWh) per UTC-kvart ur quarterly-CSV:erna."""
    out: Dict[datetime, float] = {}
    zone_dir = QUARTERLY_DIR / zone
    if not zone_dir.exists():
        return out
    for csv_file in sorted(zone_dir.glob("*.csv")):
        with open(csv_file, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    price = float(row["EUR_per_kWh"]) * 1000.0
                except (KeyError, TypeError, ValueError):
                    continue
                ts = parse_iso(row["time_start"]).astimezone(UTC_TZ)
                out[ts] = price
    return out


def load_imbalance_prices(zone: str) -> Dict[datetime, Tuple[float, float]]:
    """(sales, purchase) i EUR/MWh per UTC-kvart ur eSett-CSV:erna."""
    out: Dict[datetime, Tuple[float, float]] = {}
    zone_dir = ESETT_DATA_DIR / "imbalance" / zone
    if not zone_dir.exists():
        return out
    for csv_file in sorted(zone_dir.glob("*.csv")):
        with open(csv_file, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    sales = float(row["imbl_sales_price_eur_mwh"])
                    purchase = float(row["imbl_purchase_price_eur_mwh"])
                except (KeyError, TypeError, ValueError):
                    continue
                ts = parse_iso(row["time_start"]).astimezone(UTC_TZ)
                out[ts] = (sales, purchase)
    return out


# ---------------------------------------------------------------------------
# Beräkningskärna (ren — enhetstestas)
# ---------------------------------------------------------------------------

def interval_cost(diff_mwh: float, spot: float,
                  sales: float, purchase: float) -> float:
    """Obalanskostnad (EUR) för en kvart, relativt perfekt prognos.

    Positiv diff (överskott) säljs till ``sales``; negativ diff
    (underskott) köps till ``purchase``. Negativt resultat = vinst.
    """
    if diff_mwh >= 0:
        return diff_mwh * (spot - sales)
    return (-diff_mwh) * (purchase - spot)


def persistence_forecast(
    energies: Dict[datetime, float],
) -> Dict[datetime, float]:
    """Proxy (a): prognos(t) = faktisk energi samma kvart föregående dygn."""
    day = timedelta(days=1)
    return {
        ts: energies[ts - day]
        for ts in energies
        if (ts - day) in energies
    }


def _local_month_key(ts_utc: datetime) -> str:
    local = ts_utc.astimezone(SWEDEN_TZ)
    return f"{local.year:04d}-{local.month:02d}"


def _local_qod(ts_utc: datetime) -> int:
    """Kvart-på-dygnet (0–95) i svensk lokaltid."""
    local = ts_utc.astimezone(SWEDEN_TZ)
    return local.hour * 4 + local.minute // 15


def budget_shape_forecast(
    energies: Dict[datetime, float],
    budget_mwh_by_month: Dict[str, float],
) -> Dict[datetime, float]:
    """Proxy (b): månadsbudget fördelad enligt månadens snittdygnsform.

    Args:
        energies: faktisk energi (MWh) per UTC-kvart.
        budget_mwh_by_month: {"YYYY-MM" (lokal månad): budgetenergi MWh}.

    Returns:
        Prognosenergi per UTC-kvart. Månader utan budget eller utan
        positiv form (t.ex. helt datalös månad) utelämnas.
    """
    by_month: Dict[str, List[datetime]] = defaultdict(list)
    for ts in energies:
        by_month[_local_month_key(ts)].append(ts)

    forecast: Dict[datetime, float] = {}
    for month_key, ts_list in by_month.items():
        budget = budget_mwh_by_month.get(month_key)
        if not budget or budget <= 0:
            continue

        # Medelenergi per lokal kvart-på-dygnet över månadens dagar.
        acc: Dict[int, List[float]] = defaultdict(lambda: [0.0, 0])
        for ts in ts_list:
            slot = acc[_local_qod(ts)]
            slot[0] += energies[ts]
            slot[1] += 1
        mean_shape = {q: s / n for q, (s, n) in acc.items() if n > 0}

        # Normalisera: prognosens summa över månadens kvartar == budget.
        shape_total = sum(mean_shape[_local_qod(ts)] for ts in ts_list)
        if shape_total <= 0:
            continue
        scale = budget / shape_total
        for ts in ts_list:
            forecast[ts] = mean_shape[_local_qod(ts)] * scale
    return forecast


def _month_calendar_quarters(month_key: str) -> int:
    """Antal 15-min-kvartar i en lokal kalendermånad (DST-exakt)."""
    year, month = int(month_key[:4]), int(month_key[5:7])
    start = datetime(year, month, 1, tzinfo=SWEDEN_TZ)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=SWEDEN_TZ)
    else:
        end = datetime(year, month + 1, 1, tzinfo=SWEDEN_TZ)
    return int((end - start).total_seconds() // QUARTER_SECONDS)


def settle_monthly(
    energies: Dict[datetime, float],
    forecast_a: Dict[datetime, float],
    forecast_b: Dict[datetime, float],
    spot: Dict[datetime, float],
    prices: Dict[datetime, Tuple[float, float]],
) -> List[dict]:
    """Avräkna båda prognosproxies mot obalanspriserna, per lokal månad.

    Endast kvartar där ALLA fem serier finns utvärderas (samma mängd för
    a och b, så skillnaden mäter prognoskvalitet — inte datatäckning).

    Returns:
        Sorterad lista av månadsrader med netto (``cost_eur_*``), brutto
        (``gross_*``), volym, €/MWh, täckning och enprisandel.
    """
    acc: Dict[str, dict] = defaultdict(lambda: {
        "cost_a": 0.0, "cost_b": 0.0, "gross_a": 0.0, "gross_b": 0.0,
        "volume": 0.0, "n": 0, "single_price": 0,
    })

    for ts, actual in energies.items():
        fa = forecast_a.get(ts)
        fb = forecast_b.get(ts)
        if fa is None or fb is None:
            continue
        s = spot.get(ts)
        pr = prices.get(ts)
        if s is None or pr is None:
            continue
        sales, purchase = pr

        ca = interval_cost(actual - fa, s, sales, purchase)
        cb = interval_cost(actual - fb, s, sales, purchase)

        a = acc[_local_month_key(ts)]
        a["cost_a"] += ca
        a["cost_b"] += cb
        a["gross_a"] += abs(ca)
        a["gross_b"] += abs(cb)
        a["volume"] += actual
        a["n"] += 1
        if sales == purchase:
            a["single_price"] += 1

    out: List[dict] = []
    for month_key in sorted(acc):
        a = acc[month_key]
        n = a["n"]
        if n == 0:
            continue
        vol = a["volume"]
        cal_quarters = _month_calendar_quarters(month_key)
        out.append({
            "month": month_key,
            "cost_eur_a": round(a["cost_a"], 2),
            "cost_eur_b": round(a["cost_b"], 2),
            "gross_a": round(a["gross_a"], 2),
            "gross_b": round(a["gross_b"], 2),
            "volume_mwh": round(vol, 3),
            "cost_per_mwh_a": round(a["cost_a"] / vol, 3) if vol > 0 else None,
            "cost_per_mwh_b": round(a["cost_b"] / vol, 3) if vol > 0 else None,
            "coverage_pct": round(100.0 * n / cal_quarters, 2),
            "single_price_share_pct": round(100.0 * a["single_price"] / n, 1),
            "n": n,
        })
    return out


# ---------------------------------------------------------------------------
# Aggregat + orkestrering
# ---------------------------------------------------------------------------

def _aggregate_months(monthly: List[dict]) -> Optional[dict]:
    """Volymviktat aggregat över givna månadsrader (netto/brutto/€/MWh)."""
    rows = [m for m in monthly if m["coverage_pct"] >= MIN_AGG_COVERAGE_PCT]
    if not rows:
        return None
    vol = sum(m["volume_mwh"] for m in rows)
    n = sum(m["n"] for m in rows)
    cost_a = sum(m["cost_eur_a"] for m in rows)
    cost_b = sum(m["cost_eur_b"] for m in rows)
    return {
        "cost_eur_a": round(cost_a, 0),
        "cost_eur_b": round(cost_b, 0),
        "gross_a": round(sum(m["gross_a"] for m in rows), 0),
        "gross_b": round(sum(m["gross_b"] for m in rows), 0),
        "volume_mwh": round(vol, 1),
        "cost_per_mwh_a": round(cost_a / vol, 2) if vol > 0 else None,
        "cost_per_mwh_b": round(cost_b / vol, 2) if vol > 0 else None,
        "single_price_share_pct": round(
            sum(m["single_price_share_pct"] * m["n"] for m in rows) / n, 1
        ) if n else None,
        "months": len(rows),
        "from_month": rows[0]["month"],
        "to_month": rows[-1]["month"],
    }


def build_obalans_data(months_back: int = 24) -> dict:
    """Bygg obalanskostnadsdata för alla parker.

    Args:
        months_back: max antal månader (bakåt från senaste datamånad)
            per park.

    Returns:
        {"parks": {park: {"zone", "monthly": [...], "last12": {...}}},
         "portfolio": {"last12": {...}},
         "method": {...kort metodreferens...}}
    """
    spot_cache: Dict[str, Dict[datetime, float]] = {}
    price_cache: Dict[str, Dict[datetime, Tuple[float, float]]] = {}
    parks_out: Dict[str, dict] = {}

    for park, zone in sorted(PARK_ZONES.items()):
        energies = load_park_energies(park)
        if not energies:
            continue

        if zone not in spot_cache:
            spot_cache[zone] = load_spot_quarters(zone)
            price_cache[zone] = load_imbalance_prices(zone)

        # Budget per lokal månad som förekommer i parkdatat.
        month_keys = {_local_month_key(ts) for ts in energies}
        budgets: Dict[str, float] = {}
        for mk in month_keys:
            try:
                b = get_budget(park, int(mk[:4]), int(mk[5:7]))
            except (ValueError, FileNotFoundError):
                continue
            if b and b.get("energy_mwh"):
                budgets[mk] = float(b["energy_mwh"])

        fc_a = persistence_forecast(energies)
        fc_b = budget_shape_forecast(energies, budgets)
        monthly = settle_monthly(
            energies, fc_a, fc_b, spot_cache[zone], price_cache[zone]
        )
        monthly = [
            m for m in monthly if m["coverage_pct"] >= MIN_MONTH_COVERAGE_PCT
        ][-months_back:]
        if not monthly:
            continue

        parks_out[park] = {
            "zone": zone,
            "monthly": monthly,
            "last12": _aggregate_months(monthly[-12:]),
        }

    # Portföljtotal: summera parkernas senaste-12-aggregat.
    park_aggs = [
        p["last12"] for p in parks_out.values() if p["last12"] is not None
    ]
    portfolio = None
    if park_aggs:
        vol = sum(a["volume_mwh"] for a in park_aggs)
        cost_a = sum(a["cost_eur_a"] for a in park_aggs)
        cost_b = sum(a["cost_eur_b"] for a in park_aggs)
        portfolio = {
            "cost_eur_a": round(cost_a, 0),
            "cost_eur_b": round(cost_b, 0),
            "volume_mwh": round(vol, 1),
            "cost_per_mwh_a": round(cost_a / vol, 2) if vol > 0 else None,
            "cost_per_mwh_b": round(cost_b / vol, 2) if vol > 0 else None,
            "park_count": len(park_aggs),
        }

    return {
        "parks": parks_out,
        "portfolio": {"last12": portfolio},
        "method": {
            "proxy_a": "Persistens: prognos(t) = faktisk produktion samma "
                       "kvart föregående dygn (D-1).",
            "proxy_b": "Budgetform: PVsyst-månadsbudget fördelad enligt "
                       "månadens genomsnittliga faktiska dygnsform.",
            "cost_definition": "Σ diff⁺×(spot−sales) + |diff⁻|×(purchase−spot)"
                               " per 15-min-kvart; negativ kostnad = vinst.",
        },
    }


# ---------------------------------------------------------------------------
# Klartextinsikter
# ---------------------------------------------------------------------------

def _fmt(v: float, dec: int = 1) -> str:
    s = f"{v:,.{dec}f}" if dec else f"{v:,.0f}"
    return s.replace(",", " ").replace(".", ",")


def build_obalans_insights(data: dict) -> List[dict]:
    """Generera klartext-slutsatser (svenska) ur obalansdatat.

    Returns:
        [{"text": str, "tone": "pos"|"neg"|"neutral"}, ...]
    """
    insights: List[dict] = []
    parks = data.get("parks", {})
    port = (data.get("portfolio") or {}).get("last12")

    if port and port.get("cost_per_mwh_a") is not None:
        lo_tot = min(port["cost_eur_a"], port["cost_eur_b"]) / 1000.0
        hi_tot = max(port["cost_eur_a"], port["cost_eur_b"]) / 1000.0
        lo = min(port["cost_per_mwh_a"], port["cost_per_mwh_b"])
        hi = max(port["cost_per_mwh_a"], port["cost_per_mwh_b"])
        insights.append({
            "text": (
                f"Simulerad obalanskostnad för portföljen senaste 12 mån: "
                f"{_fmt(lo_tot, 0)}–{_fmt(hi_tot, 0)} k€ netto "
                f"({_fmt(lo, 1)}–{_fmt(hi, 1)} €/MWh producerad) beroende på "
                f"prognoskvalitet — spannet går från naiv D-1-persistens till "
                f"ren budgetform utan väderinformation."
            ),
            "tone": "neg" if lo > 4.0 else "neutral",
        })

    # Park som sticker ut: högst €/MWh (persistens) bland parker med aggregat.
    ranked = sorted(
        (
            (park, p["zone"], p["last12"])
            for park, p in parks.items()
            if p.get("last12") and p["last12"].get("cost_per_mwh_a") is not None
        ),
        key=lambda t: t[2]["cost_per_mwh_a"],
        reverse=True,
    )
    if len(ranked) >= 2 and port and port.get("cost_per_mwh_a"):
        top_park, top_zone, top = ranked[0]
        if top["cost_per_mwh_a"] > 1.5 * port["cost_per_mwh_a"]:
            insights.append({
                "text": (
                    f"{top_park.capitalize()} ({top_zone}) sticker ut med "
                    f"{_fmt(top['cost_per_mwh_a'], 1)} €/MWh i simulerad "
                    f"obalanskostnad (persistens), mot portföljens "
                    f"{_fmt(port['cost_per_mwh_a'], 1)} €/MWh — värd en titt "
                    f"på produktionens dag-till-dag-variabilitet."
                ),
                "tone": "neg",
            })
        best_park, best_zone, best = ranked[-1]
        if best["cost_per_mwh_a"] < 0:
            insights.append({
                "text": (
                    f"{best_park.capitalize()} ({best_zone}) landar på netto "
                    f"VINST ({_fmt(best['cost_per_mwh_a'], 1)} €/MWh): "
                    f"obalansen har oftare legat i systemets hjälpriktning — "
                    f"tur i enprismodellen, inget att bygga strategi på."
                ),
                "tone": "pos",
            })

    # Enprisverifiering (viktad över parkerna).
    shares = [
        p["last12"]["single_price_share_pct"]
        for p in parks.values()
        if p.get("last12") and p["last12"].get("single_price_share_pct")
        is not None
    ]
    if shares:
        avg_share = sum(shares) / len(shares)
        insights.append({
            "text": (
                f"Enprismodellen (säljpris = köppris) gäller i "
                f"{_fmt(avg_share, 1)} % av kvartarna — prognosfel i rätt "
                f"riktning belönas, vilket gör nettokostnaden lägre än "
                f"bruttofriktionen."
            ),
            "tone": "neutral",
        })

    return insights
