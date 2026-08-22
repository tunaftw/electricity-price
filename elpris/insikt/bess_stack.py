"""Revenue stacking för BESS — arbitrage OCH stödtjänster i samma optimering.

Dashboarden visar idag två SEPARATA teoretiska tak för ett 1 MW-batteri:
(i) spotarbitrage (``bess_dashboard_data.optimize_hourly_arbitrage``) och
(ii) stödtjänstintäkt vid 100 % tillgänglighet
(``ancillary_dashboard_data``). Ett verkligt batteri kan inte få båda
samtidigt — varje timme är antingen en arbitragetimme eller en reservtimme.
Den här modulen kör en gemensam timvis DP där batteriet varje timme väljer
det mest lönsamma av charge / discharge / idle / commit till EN
reservprodukt, och kvantifierar hur mycket stackingen ger UTÖVER den bästa
enskilda intäktsströmmen.

Komplett antagandelista (v1)
============================
* **Perfect foresight**: DP:n ser hela dygnets spot- och reservpriser i
  förväg. Verklig budgivning sker under osäkerhet → siffrorna är ett tak,
  inte en prognos.
* **Kapacitetsmarknad utan aktivering**: reservintäkt = kapacitetspris
  (EUR/MW·h) × acceptance_rate; SoC antas OFÖRÄNDRAD under reservtimmen.
  Energiaktivering (FCR-insatser, aFRR/mFRR-energi) modelleras inte —
  varken dess intäkt eller dess SoC-slitage.
* **En produkt per timme, hela MW:n**: ingen partiell split av effekten
  mellan produkter eller mellan reserv och arbitrage. Detta underskattar
  optimum något (verkliga aktörer delar bud), men stacking-vinsten över
  bästa singelström fångas ändå.
* **Dygnsvis reset**: DP:n körs per komplett UTC-dygn med start-SoC = 0
  och fritt slut-SoC (kvarvarande energi värderas till 0), precis som
  ``optimize_hourly_arbitrage``. Värde av att bära SoC över dygnsgränsen
  ignoreras.
* **C-rate 1**: 1 MW / D MWh, D ∈ {1, 2, 4} h. Ladd-/urladdningssteget är
  1 timme × 1 MW → SoC-nivåerna diskretiseras i steg om ``power_mw`` MWh
  (heltals-MWh vid 1 MW). Konsekvens: FCR-N (kräver BÅDE energi ≥ 0,34
  och headroom ≥ 0,34 MWh/MW) är OGÖRLIG för 1h-batteriet i den här
  diskretiseringen — SoC 0 saknar energi, SoC 1 saknar headroom. Med
  kontinuerlig SoC hade 0,5 MWh fungerat; artefakten försvinner för
  D ≥ 2. Dokumenterad medvetet i stället för att finfördela gridet.
* **acceptance_rate**: andel av budad kapacitet som antas bli antagen
  (default 1,0 = dashboardens "100 % availability"-antagande). Skalar
  bara reservintäkten; känslighet för 0,7 och 0,4 beräknas på årsnivå
  genom att köra om hela DP:n (optimum skiftar mot arbitrage när
  reserven blir mindre värd).
* **Cykelkostnad**: ``CYCLE_COST_EUR_PER_MWH`` × genomströmning dras i
  målfunktionen vid varje urladdning. Genomströmning = energi som lämnar
  lagret (SoC-minskningen, före verkningsgradsförlust). Reservtimmar ger
  ingen genomströmning (ingen aktivering modelleras).
* **Verkningsgrad**: hela round-trip-verkningsgraden (0,88) läggs på
  urladdningen, som i ``optimize_hourly_arbitrage``.
* **SoC-krav för reserv** (grova defaults efter Svk:s uthållighetskrav —
  LER-resurser i FCR ska klara ~20 min ≈ 0,34 MWh/MW; aFRR/mFRR kräver
  längre uthållighet, här satt till 1 MWh/MW): uppreglering kräver
  energiinnehåll, nedreglering kräver headroom, FCR-N (symmetrisk)
  kräver båda. Konstanterna är parametrar, inte sanningar.
* **Mimer-data**: naiva tidsstämplar tolkas som svensk lokaltid
  (verifierat: 23 rader vårdygnet, 25 höstdygnet) och konverteras till
  UTC för join mot spotdygnen. Vid höstomställningen kollapsar de två
  lokala 02-timmarna till en (sista raden vinner i loadern) → en
  UTC-timme/år saknar reservpris och blir "produkt otillgänglig".
  Timmar utan pris i källdatat är otillgängliga (inte pris 0).
* **Tre DP-varianter** för sanity-invarianten
  ``stacked ≥ max(arb_only, best_ancillary_only) − ε``:
  (1) *stacked* — alla aktioner; (2) *arb_only* — reservprodukter
  avstängda; (3) *ancillary_only per produkt* — bara EN produkt
  tillgänglig OCH arbitrageintäkten avstängd (urladdning ger 0 EUR men
  kostar cykelkostnad; laddning kostar fortfarande spot). Varje variant
  är en strikt delmängd/försvagning av stacked-aktionsrummet, så
  invarianten håller per konstruktion — testerna verifierar att koden
  inte bryter den.
* **BTM-delen** (``build_btm_real_data``) återanvänder
  ``optimize_btm_hourly``-semantiken: batteriet laddar från ALL sol (inte
  bara exportgräns-överskott) och kan inte ladda från nätet. Skillnaden
  mot dashboardens sol_bess är att den körs på parkens FAKTISKA
  15-min-produktion (``effective_power_mw`` → timenergi) och verklig
  zon-spot, med batteristorlek 0,25 MW per MWp (parameter) i stället
  för dashboardens 1 MW batteri per 1 MW TMY-profil. TMY-jämförelsen
  görs därför internt: samma dagar, samma batteri, sol_syd-profilen
  skalad till samma årsenergi som parken — så att skillnaden isolerar
  PROFILFORMEN, inte volymen eller batteridimensioneringen.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Dict, List, Optional, Sequence, Tuple

from ..ancillary_dashboard_data import (
    load_afrr_data,
    load_fcr_data,
    load_mfrr_cm_data,
)
from ..bess_dashboard_data import (
    ROUND_TRIP_EFFICIENCY,
    _build_daily_prices,
    optimize_btm_hourly,
)
from ..config import (
    PARK_CAPACITY_KWP,
    PARK_ZONES,
    SWEDEN_TZ,
    UTC_TZ,
    ZONES,
)
from ..dashboard_v2_data import load_spot_prices
from ..operations_dashboard_data import load_park_15min
from ..rework_portfolio import fmt_num
from ..solar_profile import load_pvsyst_profile

# ---------------------------------------------------------------------------
# Konstanter (justerbara parametrar, inte sanningar)
# ---------------------------------------------------------------------------

# Energikrav (MWh per MW budad kapacitet) för UPP-produkter: batteriet
# måste ha minst så mycket energi i lagret under reservtimmen.
RESERVE_ENERGY_REQ_MWH_PER_MW: Dict[str, float] = {
    "fcr_d_up": 0.34,
    "fcr_n": 0.34,
    "afrr_up": 1.0,
    "mfrr_cm_up": 1.0,
}

# Headroom-krav (MWh per MW) för NED-produkter: batteriet måste ha minst
# så mycket ledig kapacitet (kapacitet − SoC) under reservtimmen.
RESERVE_HEADROOM_REQ: Dict[str, float] = {
    "fcr_d_down": 0.34,
    "afrr_down": 1.0,
    "mfrr_cm_down": 1.0,
}

# FCR-N är symmetrisk: kräver energi (ovan) OCH headroom.
FCR_N_HEADROOM_MWH_PER_MW = 0.34

ALL_RESERVE_PRODUCTS: Tuple[str, ...] = (
    "fcr_n",
    "fcr_d_up",
    "fcr_d_down",
    "afrr_up",
    "afrr_down",
    "mfrr_cm_up",
    "mfrr_cm_down",
)

PRODUCT_LABELS: Dict[str, str] = {
    "fcr_n": "FCR-N",
    "fcr_d_up": "FCR-D upp",
    "fcr_d_down": "FCR-D ned",
    "afrr_up": "aFRR upp",
    "afrr_down": "aFRR ned",
    "mfrr_cm_up": "mFRR-CM upp",
    "mfrr_cm_down": "mFRR-CM ned",
}

# Degraderingskostnad per MWh genomströmning (energi som lämnar lagret).
CYCLE_COST_EUR_PER_MWH = 8.0

# Acceptansnivåer som alltid beräknas som känslighet på årsnivå.
ACCEPTANCE_SENSITIVITY: Tuple[float, ...] = (0.7, 0.4)

DEFAULT_DURATIONS: Tuple[int, ...] = (1, 2, 4)

_EPS = 1e-6


# ---------------------------------------------------------------------------
# Feasibility
# ---------------------------------------------------------------------------

def reserve_feasible(
    product: str,
    soc_mwh: float,
    capacity_mwh: float,
    power_mw: float = 1.0,
) -> bool:
    """Kan batteriet committa ``power_mw`` MW till *product* vid given SoC?

    Uppreglering kräver energiinnehåll ≥ krav × power_mw, nedreglering
    kräver headroom ≥ krav × power_mw, FCR-N kräver båda. Okänd produkt →
    False (hellre utesluta än att bjuda in en icke-modellerad marknad).
    """
    headroom = capacity_mwh - soc_mwh
    if product in RESERVE_ENERGY_REQ_MWH_PER_MW:
        if soc_mwh + _EPS < RESERVE_ENERGY_REQ_MWH_PER_MW[product] * power_mw:
            return False
        if product == "fcr_n" and headroom + _EPS < (
            FCR_N_HEADROOM_MWH_PER_MW * power_mw
        ):
            return False
        return True
    if product in RESERVE_HEADROOM_REQ:
        return headroom + _EPS >= RESERVE_HEADROOM_REQ[product] * power_mw
    return False


# ---------------------------------------------------------------------------
# Kärnan: timvis DP med reservprodukter som alternativ
# ---------------------------------------------------------------------------

def optimize_stack_day(
    prices: Sequence[float],
    reserve_prices: Optional[Dict[str, Sequence[Optional[float]]]] = None,
    capacity_mwh: float = 2.0,
    power_mw: float = 1.0,
    efficiency: float = ROUND_TRIP_EFFICIENCY,
    cycle_cost_eur_per_mwh: float = CYCLE_COST_EUR_PER_MWH,
    acceptance_rate: float = 1.0,
    arbitrage_revenue: bool = True,
    products: Optional[Sequence[str]] = None,
    initial_soc_mwh: float = 0.0,
) -> dict:
    """Optimalt dygn för 1 batteri: arbitrage + reservprodukter i samma DP.

    Backward-DP över samma SoC-diskretisering som
    ``optimize_hourly_arbitrage`` (steg = ``power_mw`` MWh, C-rate 1).
    Per timme väljs ETT av:

    * **idle** — SoC oförändrad, 0 EUR.
    * **charge** — SoC +steg; kostnad = spot × steg.
    * **discharge** — SoC −steg; intäkt = spot × steg × efficiency
      (0 om ``arbitrage_revenue=False``) − cykelkostnad × steg.
    * **reserv p** — SoC oförändrad; intäkt = pris_p × power_mw ×
      acceptance_rate; kräver ``reserve_feasible(p, soc, ...)`` och att
      produkten har pris (inte None) den timmen.

    Args:
        prices: Spotpriser EUR/MWh, en per timme.
        reserve_prices: ``{produkt: [pris_h0..h23]}`` i EUR/MW·h; ``None``
            i listan = produkten otillgänglig den timmen.
        capacity_mwh: Batteriets energikapacitet (MWh).
        power_mw: Märkeffekt (MW). Även SoC-stegets storlek i MWh.
        efficiency: Round-trip-verkningsgrad, läggs på urladdning.
        cycle_cost_eur_per_mwh: Degraderingskostnad per MWh genomströmning.
        acceptance_rate: Andel av reservbudet som antas antaget (0–1).
        arbitrage_revenue: ``False`` → urladdning ger 0 EUR spotintäkt
            (men kostar fortfarande cykelkostnad). Används för
            ancillary-only-varianten så att den blir en strikt
            försvagning av stacked (invariantgaranti).
        products: Tillåtna reservprodukter. ``None`` = alla i
            ``reserve_prices``; tom sekvens = ren arbitrage.
        initial_soc_mwh: Start-SoC (avrundas till närmaste SoC-nivå).
            Default 0 = dygnsreset som befintlig kod.

    Returns:
        dict med ``revenue_eur`` (DP-optimum, avrundat 2 dec),
        ``arbitrage_eur``, ``reserve_eur``, ``cycles``,
        ``throughput_mwh``, ``hours_by_product``, ``hours_charge``,
        ``hours_discharge``, ``hours_idle``.
    """
    n = len(prices)
    empty = {
        "revenue_eur": 0.0,
        "arbitrage_eur": 0.0,
        "reserve_eur": 0.0,
        "cycles": 0.0,
        "throughput_mwh": 0.0,
        "hours_by_product": {},
        "hours_charge": 0,
        "hours_discharge": 0,
        "hours_idle": n,
    }
    if n == 0 or capacity_mwh <= 0 or power_mw <= 0:
        return empty

    if reserve_prices is None:
        reserve_prices = {}
    if products is None:
        active_products = [p for p in ALL_RESERVE_PRODUCTS if p in reserve_prices]
    else:
        active_products = [p for p in products if p in reserve_prices]

    energy_step = power_mw  # MWh per timme vid märkeffekt
    n_levels = int(round(capacity_mwh / energy_step)) + 1
    soc_levels = [i * energy_step for i in range(n_levels)]

    # Reservaktionens värde per (produkt, timme); förberäkna feasibility
    # per (produkt, SoC-nivå) — den beror inte på tid.
    feas: Dict[str, List[bool]] = {
        p: [reserve_feasible(p, soc_levels[s], capacity_mwh, power_mw)
            for s in range(n_levels)]
        for p in active_products
    }

    cycle_cost_step = cycle_cost_eur_per_mwh * energy_step

    # dp[t][s] = max intäkt från timme t till dygnets slut givet SoC-nivå s.
    dp = [[0.0] * n_levels for _ in range(n + 1)]

    # --- backward pass ---
    for t in range(n - 1, -1, -1):
        price = prices[t]
        charge_cost = price * energy_step
        if arbitrage_revenue:
            discharge_rev = price * energy_step * efficiency - cycle_cost_step
        else:
            discharge_rev = -cycle_cost_step
        # Reservvärden denna timme
        hour_reserves: List[Tuple[str, float]] = []
        for p in active_products:
            series = reserve_prices[p]
            rp = series[t] if t < len(series) else None
            if rp is not None:
                hour_reserves.append((p, rp * power_mw * acceptance_rate))

        nxt = dp[t + 1]
        row = dp[t]
        for s in range(n_levels):
            best = nxt[s]  # idle
            if s + 1 < n_levels:
                val = -charge_cost + nxt[s + 1]
                if val > best:
                    best = val
            if s - 1 >= 0:
                val = discharge_rev + nxt[s - 1]
                if val > best:
                    best = val
            for p, rev in hour_reserves:
                if feas[p][s]:
                    val = rev + nxt[s]
                    if val > best:
                        best = val
            row[s] = best

    s0 = min(n_levels - 1, max(0, int(round(initial_soc_mwh / energy_step))))
    optimal = dp[0][s0]

    # --- forward pass: rekonstruera schema och komponenter ---
    s = s0
    arb_eur = 0.0
    res_eur = 0.0
    throughput = 0.0
    hours_by_product: Dict[str, int] = defaultdict(int)
    hours_charge = 0
    hours_discharge = 0
    hours_idle = 0

    for t in range(n):
        price = prices[t]
        charge_cost = price * energy_step
        if arbitrage_revenue:
            discharge_rev = price * energy_step * efficiency - cycle_cost_step
        else:
            discharge_rev = -cycle_cost_step

        nxt = dp[t + 1]
        best_val = nxt[s]
        best_action = "idle"

        if s + 1 < n_levels:
            val = -charge_cost + nxt[s + 1]
            if val > best_val + 1e-9:
                best_val = val
                best_action = "charge"

        if s - 1 >= 0:
            val = discharge_rev + nxt[s - 1]
            if val > best_val + 1e-9:
                best_val = val
                best_action = "discharge"

        for p in active_products:
            series = reserve_prices[p]
            rp = series[t] if t < len(series) else None
            if rp is None or not feas[p][s]:
                continue
            val = rp * power_mw * acceptance_rate + nxt[s]
            if val > best_val + 1e-9:
                best_val = val
                best_action = ("reserve", p)

        if best_action == "charge":
            arb_eur -= charge_cost
            hours_charge += 1
            s += 1
        elif best_action == "discharge":
            arb_eur += discharge_rev
            throughput += energy_step
            hours_discharge += 1
            s -= 1
        elif best_action == "idle":
            hours_idle += 1
        else:
            p = best_action[1]
            rp = reserve_prices[p][t]
            res_eur += rp * power_mw * acceptance_rate
            hours_by_product[p] += 1

    return {
        "revenue_eur": round(optimal, 2),
        "arbitrage_eur": round(arb_eur, 2),
        "reserve_eur": round(res_eur, 2),
        "cycles": round(throughput / capacity_mwh, 4) if capacity_mwh > 0 else 0.0,
        "throughput_mwh": round(throughput, 4),
        "hours_by_product": dict(hours_by_product),
        "hours_charge": hours_charge,
        "hours_discharge": hours_discharge,
        "hours_idle": hours_idle,
    }


# ---------------------------------------------------------------------------
# Mimer-priser → per UTC-dygn/timme
# ---------------------------------------------------------------------------

def _ts_to_utc_day_hour(ts_str: str) -> Optional[Tuple[str, int]]:
    """Naiv Mimer-tidsstämpel (svensk lokaltid) → (UTC-datumnyckel, UTC-timme).

    Redan tz-medvetna strängar respekteras. Vid höstomställningens tvetydiga
    02-timme väljs första förekomsten (fold=0, CEST) — källdatat har ändå
    kollapsat dubbletten (dict nycklad på strängen).
    """
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=SWEDEN_TZ)
    ts_utc = ts.astimezone(UTC_TZ)
    return (ts_utc.strftime("%Y-%m-%d"), ts_utc.hour)


def _build_reserve_by_day(
    zone: str,
    fcr: Optional[Dict[str, Dict[str, float]]] = None,
    afrr: Optional[Dict[str, Dict[str, Dict[str, float]]]] = None,
    mfrr_cm: Optional[Dict[str, Dict[str, Dict[str, float]]]] = None,
) -> Dict[str, Dict[str, List[Optional[float]]]]:
    """Bygg ``{date_key: {produkt: [pris_h0..h23]}}`` för en zon (UTC-dygn).

    FCR är nationell; aFRR och mFRR-CM per zon. Timmar utan pris = None
    (produkt otillgänglig). Loaders kan skickas in för att undvika
    dubbelinläsning över zoner.
    """
    if fcr is None:
        fcr = load_fcr_data()
    if afrr is None:
        afrr = load_afrr_data()
    if mfrr_cm is None:
        mfrr_cm = load_mfrr_cm_data()

    streams: Dict[str, Dict[str, float]] = {
        "fcr_n": fcr.get("fcr_n", {}),
        "fcr_d_up": fcr.get("fcr_d_up", {}),
        "fcr_d_down": fcr.get("fcr_d_down", {}),
        "afrr_up": afrr.get(zone, {}).get("up", {}),
        "afrr_down": afrr.get(zone, {}).get("down", {}),
        "mfrr_cm_up": mfrr_cm.get(zone, {}).get("up", {}),
        "mfrr_cm_down": mfrr_cm.get(zone, {}).get("down", {}),
    }

    by_day: Dict[str, Dict[str, List[Optional[float]]]] = {}
    for product, series in streams.items():
        for ts_str, price in series.items():
            mapped = _ts_to_utc_day_hour(ts_str)
            if mapped is None:
                continue
            date_key, hour = mapped
            day = by_day.setdefault(date_key, {})
            if product not in day:
                day[product] = [None] * 24
            day[product][hour] = price
    return by_day


# ---------------------------------------------------------------------------
# build_stack_data — huvud-API
# ---------------------------------------------------------------------------

def build_stack_data(
    zones: Optional[Sequence[str]] = None,
    durations: Sequence[int] = DEFAULT_DURATIONS,
    years: Optional[Sequence[int]] = None,
    acceptance_rate: float = 1.0,
    cycle_cost_eur_per_mwh: float = CYCLE_COST_EUR_PER_MWH,
) -> dict:
    """Revenue stacking per zon × duration × månad + årsaggregat.

    Kör tre DP-varianter per dygn (stacked / arb_only / ancillary_only per
    produkt) och aggregerar. Sanity-invarianten
    ``stacked ≥ max(arb_only, best_ancillary_only) − ε`` verifieras och
    rapporteras (``invariant_ok``) på varje månads- och årsrad.

    Args:
        zones: Elområden, default alla (SE1–SE4).
        durations: Batterivaraktigheter i timmar (C-rate 1 → kapacitet
            = duration MWh vid 1 MW).
        years: Begränsa till dessa år (UTC-dygnets år). ``None`` = alla.
        acceptance_rate: Huvudscenariots budacceptans.
        cycle_cost_eur_per_mwh: Degraderingskostnad.

    Returns:
        {"params": {...},
         "zones": {zon: {"1h": {"monthly": [...], "yearly": [...]},...}}}

        Månadsrad: {month, stacked_eur, arb_only_eur,
        best_ancillary_only_eur, best_ancillary_product,
        uplift_vs_best_single_pct, cycles, reserve_share_pct,
        top_product_mix, days, invariant_ok}.
        Årsrad: samma + ancillary_only_by_product_eur och
        acceptance_sensitivity {acc: stacked_eur}.
    """
    zone_list = list(zones) if zones else list(ZONES)
    year_set = set(years) if years else None

    # Ladda Mimer-data EN gång (FCR nationell, aFRR/mFRR-CM alla zoner).
    fcr = load_fcr_data()
    afrr = load_afrr_data()
    mfrr_cm = load_mfrr_cm_data()

    sens_rates = [r for r in ACCEPTANCE_SENSITIVITY
                  if abs(r - acceptance_rate) > 1e-9]

    result_zones: Dict[str, dict] = {}

    for zone in zone_list:
        spot = load_spot_prices(zone)
        if not spot:
            continue
        daily_prices = _build_daily_prices(spot)
        if year_set is not None:
            daily_prices = {
                dk: v for dk, v in daily_prices.items()
                if int(dk[:4]) in year_set
            }
        if not daily_prices:
            continue
        reserve_by_day = _build_reserve_by_day(zone, fcr, afrr, mfrr_cm)

        zone_out: Dict[str, dict] = {}
        for duration in durations:
            capacity_mwh = float(duration)  # 1 MW × D h

            # Ackumulatorer per månad ("YYYY-MM") och år.
            monthly: Dict[str, dict] = defaultdict(lambda: {
                "stacked": 0.0, "arb": 0.0, "cycles": 0.0,
                "reserve_hours": 0, "hours": 0, "days": 0,
                "mix": defaultdict(int),
                "anc": defaultdict(float),
                "sens": defaultdict(float),
            })

            for date_key in sorted(daily_prices):
                prices = daily_prices[date_key]
                reserves = reserve_by_day.get(date_key, {})
                month_key = date_key[:7]
                acc = monthly[month_key]

                stacked = optimize_stack_day(
                    prices, reserves, capacity_mwh,
                    cycle_cost_eur_per_mwh=cycle_cost_eur_per_mwh,
                    acceptance_rate=acceptance_rate,
                )
                arb = optimize_stack_day(
                    prices, reserves, capacity_mwh,
                    cycle_cost_eur_per_mwh=cycle_cost_eur_per_mwh,
                    products=(),
                )
                acc["stacked"] += stacked["revenue_eur"]
                acc["arb"] += arb["revenue_eur"]
                acc["cycles"] += stacked["cycles"]
                acc["reserve_hours"] += sum(
                    stacked["hours_by_product"].values()
                )
                acc["hours"] += len(prices)
                acc["days"] += 1
                for p, h in stacked["hours_by_product"].items():
                    acc["mix"][p] += h

                # Ancillary-only per produkt (bara produkter med data idag)
                for p in ALL_RESERVE_PRODUCTS:
                    series = reserves.get(p)
                    if not series or all(v is None for v in series):
                        continue
                    anc = optimize_stack_day(
                        prices, reserves, capacity_mwh,
                        cycle_cost_eur_per_mwh=cycle_cost_eur_per_mwh,
                        acceptance_rate=acceptance_rate,
                        arbitrage_revenue=False,
                        products=(p,),
                    )
                    acc["anc"][p] += anc["revenue_eur"]

                # Acceptanskänslighet (stacked med lägre acceptans)
                for rate in sens_rates:
                    sens = optimize_stack_day(
                        prices, reserves, capacity_mwh,
                        cycle_cost_eur_per_mwh=cycle_cost_eur_per_mwh,
                        acceptance_rate=rate,
                    )
                    acc["sens"][rate] += sens["revenue_eur"]

            # --- månadsrader ---
            monthly_rows: List[dict] = []
            yearly_acc: Dict[int, dict] = defaultdict(lambda: {
                "stacked": 0.0, "arb": 0.0, "cycles": 0.0,
                "reserve_hours": 0, "hours": 0, "days": 0,
                "mix": defaultdict(int),
                "anc": defaultdict(float),
                "sens": defaultdict(float),
            })

            for month_key in sorted(monthly):
                acc = monthly[month_key]
                row = _finalize_period(acc)
                row["month"] = month_key
                monthly_rows.append(row)

                y = int(month_key[:4])
                ya = yearly_acc[y]
                ya["stacked"] += acc["stacked"]
                ya["arb"] += acc["arb"]
                ya["cycles"] += acc["cycles"]
                ya["reserve_hours"] += acc["reserve_hours"]
                ya["hours"] += acc["hours"]
                ya["days"] += acc["days"]
                for p, h in acc["mix"].items():
                    ya["mix"][p] += h
                for p, v in acc["anc"].items():
                    ya["anc"][p] += v
                for r, v in acc["sens"].items():
                    ya["sens"][r] += v

            yearly_rows: List[dict] = []
            for y in sorted(yearly_acc):
                ya = yearly_acc[y]
                row = _finalize_period(ya)
                row["year"] = y
                row["ancillary_only_by_product_eur"] = {
                    p: round(v, 2) for p, v in sorted(ya["anc"].items())
                }
                sens_out = {f"{acceptance_rate:.1f}": row["stacked_eur"]}
                for r in sens_rates:
                    sens_out[f"{r:.1f}"] = round(ya["sens"][r], 2)
                row["acceptance_sensitivity"] = sens_out
                yearly_rows.append(row)

            zone_out[f"{duration}h"] = {
                "monthly": monthly_rows,
                "yearly": yearly_rows,
            }

        result_zones[zone] = zone_out

    return {
        "params": {
            "power_mw": 1.0,
            "durations_h": list(durations),
            "efficiency": ROUND_TRIP_EFFICIENCY,
            "cycle_cost_eur_per_mwh": cycle_cost_eur_per_mwh,
            "acceptance_rate": acceptance_rate,
            "acceptance_sensitivity": list(ACCEPTANCE_SENSITIVITY),
            "years": sorted(year_set) if year_set else None,
            "reserve_energy_req_mwh_per_mw": dict(RESERVE_ENERGY_REQ_MWH_PER_MW),
            "reserve_headroom_req_mwh_per_mw": dict(RESERVE_HEADROOM_REQ),
            "fcr_n_headroom_mwh_per_mw": FCR_N_HEADROOM_MWH_PER_MW,
        },
        "zones": result_zones,
    }


def _finalize_period(acc: dict) -> dict:
    """Gör om en period-ackumulator till en utdatarad (delad månad/år).

    Invariant-toleransen skalar med antal dagar: varje dygnsresultat är
    avrundat till 2 dec, så summorna kan skilja upp till 0,01 EUR/dag åt
    fel håll utan att DP-garantin (stacked ≥ varianterna, före avrundning)
    är bruten.
    """
    anc = acc["anc"]
    if anc:
        best_product = max(anc, key=lambda p: anc[p])
        best_anc = anc[best_product]
    else:
        best_product = None
        best_anc = 0.0
    best_single = max(acc["arb"], best_anc)
    uplift = (
        (acc["stacked"] / best_single - 1.0) * 100.0
        if best_single > _EPS else None
    )
    return {
        "stacked_eur": round(acc["stacked"], 2),
        "arb_only_eur": round(acc["arb"], 2),
        "best_ancillary_only_eur": round(best_anc, 2),
        "best_ancillary_product": best_product,
        "uplift_vs_best_single_pct": (
            round(uplift, 1) if uplift is not None else None
        ),
        "cycles": round(acc["cycles"], 2),
        "reserve_share_pct": (
            round(100.0 * acc["reserve_hours"] / acc["hours"], 1)
            if acc["hours"] else 0.0
        ),
        "top_product_mix": {
            p: h for p, h in sorted(
                acc["mix"].items(), key=lambda kv: -kv[1]
            )
        },
        "days": acc["days"],
        "invariant_ok": (
            acc["stacked"] >= best_single - (0.01 * max(acc["days"], 1) + _EPS)
        ),
    }


# ---------------------------------------------------------------------------
# Insikter
# ---------------------------------------------------------------------------

def build_stack_insights(
    data: dict,
    btm_data: Optional[dict] = None,
) -> List[dict]:
    """Klartext-slutsatser ({"text","tone"}) ur ``build_stack_data``-output.

    ``btm_data`` (från ``build_btm_real_data``) är valfri — ges den läggs
    en jämförelse verklig parkprofil vs TMY till.
    """
    insights: List[dict] = []
    zones = data.get("zones", {})
    params = data.get("params", {})

    # Hitta bästa (zon, duration, senaste år med flest dagar) på uplift.
    best = None  # (uplift, zone, dur_key, yrow)
    for zone, durs in zones.items():
        for dur_key, blocks in durs.items():
            for yrow in blocks.get("yearly", []):
                up = yrow.get("uplift_vs_best_single_pct")
                if up is None:
                    continue
                if best is None or up > best[0]:
                    best = (up, zone, dur_key, yrow)

    if best is not None:
        up, zone, dur_key, yrow = best
        extra = yrow["stacked_eur"] - max(
            yrow["arb_only_eur"], yrow["best_ancillary_only_eur"]
        )
        base_label = (
            "arbitrage"
            if yrow["arb_only_eur"] >= yrow["best_ancillary_only_eur"]
            else PRODUCT_LABELS.get(
                yrow.get("best_ancillary_product") or "", "stödtjänst"
            )
        )
        insights.append({
            "text": (
                f"Stackingen ger mest i {zone} med {dur_key}-batteri "
                f"{yrow['year']}: {fmt_num(yrow['stacked_eur'])} EUR/MW — "
                f"{fmt_num(up, 1)} % ({fmt_num(extra)} EUR) över bästa "
                f"enskilda strategi ({base_label})."
            ),
            "tone": "pos",
        })

    # Dominerande produktmix (senaste året, alla zoner/durationer summerade).
    mix_total: Dict[str, int] = defaultdict(int)
    reserve_shares: List[float] = []
    for zone, durs in zones.items():
        for dur_key, blocks in durs.items():
            yearly = blocks.get("yearly", [])
            if not yearly:
                continue
            yrow = yearly[-1]
            for p, h in yrow.get("top_product_mix", {}).items():
                mix_total[p] += h
            reserve_shares.append(yrow.get("reserve_share_pct", 0.0))
    if mix_total:
        top_p = max(mix_total, key=lambda p: mix_total[p])
        tot_h = sum(mix_total.values())
        share = 100.0 * mix_total[top_p] / tot_h if tot_h else 0.0
        avg_res = (
            sum(reserve_shares) / len(reserve_shares)
            if reserve_shares else 0.0
        )
        insights.append({
            "text": (
                f"Reservtimmarna domineras av "
                f"{PRODUCT_LABELS.get(top_p, top_p)} "
                f"({fmt_num(share, 0)} % av reservtimmarna); batteriet "
                f"står i reserv ungefär {fmt_num(avg_res, 0)} % av årets "
                f"timmar i det stackade optimat."
            ),
            "tone": "neutral",
        })

    # Acceptanskänslighet (om beräknad) — hur snabbt faller optimat?
    sens_txt = None
    if best is not None:
        sens = best[3].get("acceptance_sensitivity") or {}
        if len(sens) > 1:
            keys = sorted(sens, key=float, reverse=True)
            hi, lo = keys[0], keys[-1]
            if sens[hi] > _EPS:
                drop = (1.0 - sens[lo] / sens[hi]) * 100.0
                sens_txt = (
                    f"Vid {float(lo):.0%} budacceptans i stället för "
                    f"{float(hi):.0%} faller den stackade intäkten med "
                    f"{fmt_num(drop, 0)} % — batteriet flyttar då timmar "
                    f"tillbaka mot arbitrage."
                )
    if sens_txt:
        insights.append({"text": sens_txt, "tone": "neutral"})

    # Ärlig brasklapp.
    insights.append({
        "text": (
            "Siffrorna är ett TAK, inte en prognos: DP:n har perfekt "
            "prisframsyn inom dygnet, reserverna modelleras som ren "
            "kapacitetsmarknad utan aktivering (SoC oförändrad, ingen "
            "aktiveringsintäkt eller -kostnad) och huvudscenariot antar "
            f"{params.get('acceptance_rate', 1.0):.0%} budacceptans. "
            "Verklig intäkt ligger mellan känslighetsscenarierna."
        ),
        "tone": "neg",
    })

    # BTM: verklig profil vs TMY.
    if btm_data and btm_data.get("parks"):
        deltas = []
        for pk, pdata in btm_data["parks"].items():
            tmy = pdata.get("tmy") or {}
            if (
                pdata.get("uplift_eur_mwh") is not None
                and tmy.get("uplift_eur_mwh") is not None
            ):
                deltas.append(
                    pdata["uplift_eur_mwh"] - tmy["uplift_eur_mwh"]
                )
        if deltas:
            avg_delta = sum(deltas) / len(deltas)
            rel = "MER" if avg_delta >= 0 else "MINDRE"
            insights.append({
                "text": (
                    f"Mot parkernas faktiska produktionsprofiler ger "
                    f"BTM-batteriet i snitt "
                    f"{fmt_num(abs(avg_delta), 2)} EUR/MWh {rel} "
                    f"capture-lyft än samma batteri mot TMY-profilen "
                    f"(sol_syd, skalad till samma årsenergi) — verklig "
                    f"molnighet/curtailment {'gynnar' if avg_delta >= 0 else 'missgynnar'} "
                    f"batterinyttan jämfört med typåret."
                ),
                "tone": "pos" if avg_delta >= 0 else "neg",
            })

    return insights


# ---------------------------------------------------------------------------
# BTM mot verkliga parkprofiler
# ---------------------------------------------------------------------------

def _last_complete_month(latest: datetime) -> Tuple[int, int]:
    """(år, månad) för månaden FÖRE ``latest``:s månad (UTC)."""
    y, m = latest.year, latest.month
    if m == 1:
        return (y - 1, 12)
    return (y, m - 1)


def _month_range(end_year: int, end_month: int, n_months: int) -> List[str]:
    """Lista av "YYYY-MM" som slutar med (end_year, end_month), längd n."""
    months: List[str] = []
    y, m = end_year, end_month
    for _ in range(n_months):
        months.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(months))


def build_btm_real_data(
    park_keys: Optional[Sequence[str]] = None,
    duration_h: int = 2,
    battery_mw_per_mwp: float = 0.25,
) -> dict:
    """Sol+batteri behind-the-meter per park med FAKTISK produktionsprofil.

    Kör ``optimize_btm_hourly`` (samma semantik som dashboardens sol_bess:
    batteriet laddar från all sol, aldrig från nätet) men på parkens
    verkliga 15-min ``effective_power_mw`` aggregerad till timenergi, mot
    verklig spot i parkens zon, över de senaste 12 HELA UTC-månaderna med
    parkdata. Batteristorlek: ``battery_mw_per_mwp`` MW per MWp DC
    (default 0,25), kapacitet = effekt × ``duration_h`` (C-rate 1).

    För varje park körs dessutom en TMY-motsvarighet: sol_syd-profilen
    (south_lundby) på SAMMA dagar och priser, skalad så att dess energi
    över fönstret matchar parkens faktiska energi. Skillnaden i
    capture-lyft isolerar därmed profilFORMEN (moln, curtailment,
    orientering) — inte volym eller batteridimensionering. OBS:
    dashboardens sol_bess-siffra använder 1 MW batteri per 1 MW
    TMY-profil (≈ 4× större batteri per MWp än här) och är därför inte
    direkt jämförbar i nivå.

    Returns:
        {"params": {...}, "parks": {park: {zone, mwp, battery_mw,
        battery_mwh, window_months, days_used, energy_mwh,
        capture_no_batt_eur_mwh, capture_with_batt_eur_mwh,
        uplift_eur_mwh, uplift_eur_year, tmy: {...}}}}
    """
    keys = list(park_keys) if park_keys else sorted(PARK_ZONES)
    tmy_profile = None
    try:
        tmy_profile = load_pvsyst_profile("south_lundby")
    except FileNotFoundError:
        tmy_profile = None

    parks_out: Dict[str, dict] = {}
    spot_cache: Dict[str, Dict[str, List[float]]] = {}

    for park in keys:
        zone = PARK_ZONES.get(park)
        if not zone:
            continue
        records = load_park_15min(park)
        if not records:
            continue

        # Senaste 12 hela månader (UTC), räknat från sista datapunkten.
        latest = max(r["timestamp_utc"] for r in records)
        end_y, end_m = _last_complete_month(latest)
        window = set(_month_range(end_y, end_m, 12))

        # 15 min → timenergi (MWh) per (date_key, utc_hour).
        hourly_energy: Dict[Tuple[str, int], float] = defaultdict(float)
        for r in records:
            dk = r["date"]
            if dk[:7] not in window:
                continue
            hourly_energy[(dk, r["timestamp_utc"].hour)] += (
                r["effective_power_mw"] * 0.25
            )

        if not hourly_energy:
            continue

        if zone not in spot_cache:
            spot_cache[zone] = _build_daily_prices(load_spot_prices(zone))
        daily_prices = spot_cache[zone]

        mwp = PARK_CAPACITY_KWP.get(park, 0) / 1000.0
        batt_mw = battery_mw_per_mwp * mwp
        batt_mwh = batt_mw * duration_h

        # Samla dygn (kompletta spotdygn i fönstret) och parkens solserie.
        day_solar: Dict[str, List[float]] = {}
        for date_key, prices in daily_prices.items():
            if date_key[:7] not in window:
                continue
            solar = [hourly_energy.get((date_key, h), 0.0) for h in range(24)]
            day_solar[date_key] = solar

        rev_direct = 0.0
        rev_batt = 0.0
        energy = 0.0
        used_days: List[str] = []
        for date_key in sorted(day_solar):
            solar = day_solar[date_key]
            day_energy = sum(solar)
            if day_energy <= 0:
                continue
            prices = daily_prices[date_key]
            rd, rb = optimize_btm_hourly(
                prices, solar, batt_mwh, power_mw=batt_mw
            )
            rev_direct += rd
            rev_batt += rb
            energy += day_energy
            used_days.append(date_key)
        days_used = len(used_days)

        if energy <= 0:
            continue

        cap_no = rev_direct / energy
        cap_with = rev_batt / energy

        # --- TMY-motsvarighet: EXAKT samma dagar (dagar där parken
        # faktiskt producerade), samma batteri, samma energi. Att köra
        # TMY på hela fönstret skulle ge fel säsongsviktning för parker
        # med datagap (t.ex. Tangen). ---
        tmy_out = None
        if tmy_profile:
            tmy_solar: Dict[str, List[float]] = {}
            tmy_sum = 0.0
            for date_key in used_days:
                d = date.fromisoformat(date_key)
                series = []
                for utc_hour in range(24):
                    local = datetime(
                        d.year, d.month, d.day, utc_hour, tzinfo=UTC_TZ
                    ).astimezone(SWEDEN_TZ)
                    series.append(
                        tmy_profile.get(
                            (local.month, local.day, local.hour), 0.0
                        )
                    )
                tmy_solar[date_key] = series
                tmy_sum += sum(series)
            if tmy_sum > 0:
                scale = energy / tmy_sum
                t_direct = 0.0
                t_batt = 0.0
                t_energy = 0.0
                for date_key, series in tmy_solar.items():
                    solar = [v * scale for v in series]
                    if sum(solar) <= 0:
                        continue
                    prices = daily_prices[date_key]
                    rd, rb = optimize_btm_hourly(
                        prices, solar, batt_mwh, power_mw=batt_mw
                    )
                    t_direct += rd
                    t_batt += rb
                    t_energy += sum(solar)
                if t_energy > 0:
                    tmy_out = {
                        "capture_no_batt_eur_mwh": round(
                            t_direct / t_energy, 2
                        ),
                        "capture_with_batt_eur_mwh": round(
                            t_batt / t_energy, 2
                        ),
                        "uplift_eur_mwh": round(
                            (t_batt - t_direct) / t_energy, 2
                        ),
                        "uplift_eur_year": round(t_batt - t_direct, 2),
                    }

        parks_out[park] = {
            "zone": zone,
            "mwp": round(mwp, 3),
            "battery_mw": round(batt_mw, 3),
            "battery_mwh": round(batt_mwh, 3),
            "window_months": sorted(window),
            "days_used": days_used,
            "energy_mwh": round(energy, 1),
            "capture_no_batt_eur_mwh": round(cap_no, 2),
            "capture_with_batt_eur_mwh": round(cap_with, 2),
            "uplift_eur_mwh": round(cap_with - cap_no, 2),
            "uplift_eur_year": round(rev_batt - rev_direct, 2),
            "tmy": tmy_out,
        }

    return {
        "params": {
            "duration_h": duration_h,
            "battery_mw_per_mwp": battery_mw_per_mwp,
            "efficiency": ROUND_TRIP_EFFICIENCY,
            "charging": "all sol (optimize_btm_hourly-semantik), ej nät",
            "tmy_profile": "south_lundby (sol_syd), skalad till parkens "
                           "fönsterenergi",
        },
        "parks": parks_out,
    }
