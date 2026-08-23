"""Investeringskalkyl för BESS ovanpå revenue stacking-modellen.

Dashboardens BESS-flik har hittills räknat NPV/payback i webbläsaren mot
ren arbitrageintäkt (CAPEX 280 000 EUR/MWh, OPEX 8 000 EUR/MW·år, 15 års
livslängd, 6 % diskonto). Den här modulen flyttar kalkylen till Python,
matar den med den STACKADE intäkten ur ``elpris.insikt.bess_stack`` och
lägger till IRR — så att business caset kan läsas per zon × duration ×
budacceptans i stället för bara som en NPV-siffra i en zon.

Antaganden (och vad de betyder)
===============================
* **Intäktsbasen är ett tak.** ``build_stack_data`` kör en DP med perfekt
  prisframsyn inom dygnet och modellerar reserverna som ren
  kapacitetsmarknad utan aktivering. Intäkten i kalkylen är alltså det
  teoretiska optimat för det året — inte en prognos. Acceptance-nivåerna
  (1,0 / 0,7 / 0,4) är det närmaste vi kommer en osäkerhetsspann.
* **Senaste HELA året.** Kalkylen använder det senaste kalenderåret med
  ≥ ``MIN_DAYS_COMPLETE_YEAR`` dygn i stack_data — aldrig innevarande
  YTD-år (som annars skulle jämföras med en helårs-CAPEX). Saknas ett
  helt år används det senaste tillgängliga och ``year_complete`` sätts
  False.
* **Ingen intäktsdegradering över livslängden** (``revenue_decay_pct_per_yr``
  default 0). Det är ett MEDVETET optimistiskt val: intäkten från år 1
  antas upprepas i 15 år. Verkligheten talar för fallande reala intäkter
  — mer batterier i budkurvan pressar kapacitetspriserna, och cellernas
  kapacitetsfade minskar möjlig genomströmning. Ett konservativare
  antagande är −1 till −2 %/år; kör kalkylen med
  ``revenue_decay_pct_per_yr=1.5`` för att se känsligheten. Decayen
  verkar från år 2 (år 1 = det observerade året).
* **CAPEX skalar med energi, OPEX med effekt.** CAPEX =
  ``capex_eur_per_mwh`` × duration (MWh per MW, C-rate 1 i stack-modellen);
  OPEX = ``opex_eur_per_mw_yr`` per år för 1 MW. Alla belopp är därför
  **per MW installerad effekt**. Ingen augmentation/replacement-CAPEX,
  inget restvärde, ingen nätanslutningsavgift, ingen skatt och inga
  finansieringskostnader — cykelkostnaden (8 EUR/MWh genomströmning) är
  redan avdragen inne i DP:n, så den ska inte dras igen här.
* **Payback är enkel (odiskonterad)** och interpolerad inom året. Utan
  decay ger den exakt CAPEX / årligt netto.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from ..rework_portfolio import fmt_num
from .bess_stack import build_stack_data

# Minsta antal dygn för att ett år ska räknas som "helt" (tolererar
# enstaka saknade dygn i spot-serien; 2026 med ~200 dygn faller bort).
MIN_DAYS_COMPLETE_YEAR = 360

# Defaults speglar dashboardens klientside-kalkylator.
DEFAULT_CAPEX_EUR_PER_MWH = 280_000.0
DEFAULT_OPEX_EUR_PER_MW_YR = 8_000.0
DEFAULT_LIFETIME_YR = 15
DEFAULT_DISCOUNT = 0.06

# IRR-sökrymd: −99 % till +1000 % årlig avkastning.
_IRR_LO = -0.99
_IRR_HI = 10.0
_EPS = 1e-12


# ---------------------------------------------------------------------------
# Finansiella primitiver
# ---------------------------------------------------------------------------

def npv(rate: float, cashflows: Sequence[float]) -> float:
    """Nuvärde av ``cashflows`` (index 0 = år 0, odiskonterat).

    Args:
        rate: Diskonteringsränta per period (0,06 = 6 %).
        cashflows: Kassaflöden, ett per period med start år 0.

    Returns:
        Summan av ``cf_t / (1 + rate) ** t``. Vid ``rate <= -1`` (odefinierad
        diskontering) returneras ``float("inf")`` med tecken efter det
        första kassaflödet efter år 0, så att bisektionen i :func:`irr`
        aldrig får en ZeroDivisionError.
    """
    if not cashflows:
        return 0.0
    if rate <= -1.0 + _EPS:
        tail = [cf for cf in cashflows[1:] if cf]
        sign = 1.0 if (tail and tail[0] > 0) else -1.0
        return sign * float("inf")
    total = 0.0
    factor = 1.0
    one_plus = 1.0 + rate
    for cf in cashflows:
        total += cf / factor
        factor *= one_plus
    return total


def irr(cashflows: List[float]) -> Optional[float]:
    """Internränta: den ränta där :func:`npv` blir noll.

    Metod: Newton-Raphson från 10 % (max 100 iterationer, tolerans 1e-10
    relativt investeringens storlek). Newton avbryts om derivatan är ~0,
    om steget ger en ränta utanför sökrymden ``[-0.99, 10]`` eller om den
    inte konvergerat — då tar bisektion över på samma intervall (~200
    halveringar, exakt till maskinprecision). Bisektionen kräver
    teckenväxling i ``npv`` mellan intervallets ändpunkter.

    Args:
        cashflows: Kassaflöden, index 0 = år 0 (normalt negativ CAPEX).

    Returns:
        Internräntan som andel (0,184 = 18,4 %), eller ``None`` när ingen
        rot finns i sökrymden: tomma/triviala serier, serier utan
        teckenväxling (alla in- eller alla utbetalningar) eller en IRR
        under −99 % / över +1000 %.
    """
    cf = [float(c) for c in cashflows]
    if len(cf) < 2:
        return None
    has_pos = any(c > 0 for c in cf)
    has_neg = any(c < 0 for c in cf)
    if not (has_pos and has_neg):
        return None

    scale = max(abs(c) for c in cf) or 1.0
    tol = 1e-10 * scale

    # --- Newton-Raphson ---
    rate = 0.10
    for _ in range(100):
        f = npv(rate, cf)
        if f in (float("inf"), float("-inf")):
            break
        if abs(f) < tol:
            return rate
        # d/dr Σ cf_t (1+r)^-t = Σ -t·cf_t (1+r)^-(t+1)
        deriv = 0.0
        one_plus = 1.0 + rate
        factor = one_plus  # (1+r)^(t+1) för t = 0
        for t, c in enumerate(cf):
            if t:
                deriv -= t * c / factor
            factor *= one_plus
        if abs(deriv) < 1e-14:
            break
        step = f / deriv
        new_rate = rate - step
        if not (_IRR_LO < new_rate < _IRR_HI):
            break
        if abs(new_rate - rate) < 1e-14:
            rate = new_rate
            if abs(npv(rate, cf)) < tol * 1e4:
                return rate
            break
        rate = new_rate

    # --- Bisektion som fallback ---
    lo, hi = _IRR_LO, _IRR_HI
    f_lo, f_hi = npv(lo, cf), npv(hi, cf)
    if f_lo == 0.0:
        return lo
    if f_hi == 0.0:
        return hi
    if (f_lo > 0) == (f_hi > 0):
        return None
    for _ in range(300):
        mid = (lo + hi) / 2.0
        f_mid = npv(mid, cf)
        if f_mid == 0.0 or (hi - lo) < 1e-13:
            return mid
        if (f_mid > 0) == (f_lo > 0):
            lo, f_lo = mid, f_mid
        else:
            hi, f_hi = mid, f_mid
    return (lo + hi) / 2.0


# ---------------------------------------------------------------------------
# Kalkyl per fall
# ---------------------------------------------------------------------------

def _simple_payback(
    capex: float,
    annual_net: Sequence[float],
) -> Optional[float]:
    """Enkel (odiskonterad) payback i år, interpolerad inom året.

    Utan intäktsdegradering blir resultatet exakt ``capex / netto``. Med
    degradering ackumuleras de faktiska årsflödena; räcker inte
    livslängden extrapoleras sista årets netto framåt (så länge det är
    positivt). ``None`` när nettot aldrig kan täcka CAPEX.
    """
    if capex <= 0:
        return 0.0
    cum = 0.0
    for i, net in enumerate(annual_net):
        if net <= 0:
            continue
        if cum + net >= capex:
            return i + (capex - cum) / net
        cum += net
    if not annual_net:
        return None
    tail = annual_net[-1]
    if tail <= 0:
        return None
    return len(annual_net) + (capex - cum) / tail


def _case(
    annual_gross: float,
    capex: float,
    opex: float,
    lifetime_yr: int,
    discount: float,
    decay: float,
) -> dict:
    """Ett investeringsfall (en zon × duration × acceptansnivå)."""
    nets = [
        annual_gross * (1.0 - decay) ** (t - 1) - opex
        for t in range(1, lifetime_yr + 1)
    ]
    cashflows = [-capex] + nets
    r = irr(cashflows)
    payback = _simple_payback(capex, nets)

    # Break-even: hur stor andel av årsintäkten som behövs för NPV = 0.
    # NPV(k) = −capex − opex·A + k·gross·B är linjär i k, där
    # A = Σ (1+disc)^−t och B = Σ (1−decay)^(t−1)·(1+disc)^−t.
    a_fac = sum(1.0 / (1.0 + discount) ** t for t in range(1, lifetime_yr + 1))
    b_fac = sum(
        (1.0 - decay) ** (t - 1) / (1.0 + discount) ** t
        for t in range(1, lifetime_yr + 1)
    )
    breakeven_pct = (
        100.0 * (capex + opex * a_fac) / (annual_gross * b_fac)
        if annual_gross > 0 and b_fac > 0 else None
    )

    return {
        "annual_gross_eur": round(annual_gross, 2),
        "annual_net_eur": round(nets[0], 2) if nets else round(-opex, 2),
        "capex_eur": round(capex, 2),
        "npv_eur": round(npv(discount, cashflows), 2),
        "irr_pct": round(r * 100.0, 4) if r is not None else None,
        "payback_yr": round(payback, 2) if payback is not None else None,
        "viable": bool(r is not None and r > discount),
        # Andel av årsintäkten som krävs för att precis nå
        # avkastningskravet — marginalen mot prisfall i EN siffra.
        # 20 % betyder "caset tål att intäkten faller 80 %".
        "breakeven_revenue_pct": (
            round(breakeven_pct, 1) if breakeven_pct is not None else None
        ),
    }


def _pick_year(yearly: Sequence[dict]) -> Optional[dict]:
    """Senaste HELA året ur en yearly-lista; fallback = senaste året."""
    if not yearly:
        return None
    rows = sorted(yearly, key=lambda r: r.get("year", 0))
    complete = [
        r for r in rows
        if (r.get("days") or 0) >= MIN_DAYS_COMPLETE_YEAR
    ]
    return complete[-1] if complete else rows[-1]


# ---------------------------------------------------------------------------
# build_kalkyl_data — huvud-API
# ---------------------------------------------------------------------------

def build_kalkyl_data(
    stack_data: Optional[dict] = None,
    capex_eur_per_mwh: float = DEFAULT_CAPEX_EUR_PER_MWH,
    opex_eur_per_mw_yr: float = DEFAULT_OPEX_EUR_PER_MW_YR,
    lifetime_yr: int = DEFAULT_LIFETIME_YR,
    discount: float = DEFAULT_DISCOUNT,
    revenue_decay_pct_per_yr: float = 0.0,
) -> dict:
    """IRR/NPV/payback per zon × duration × budacceptans.

    Intäktsbasen är den STACKADE årsintäkten (arbitrage + stödtjänster i
    samma optimering) för senaste hela året i ``stack_data``, per
    acceptansnivå ur årsradens ``acceptance_sensitivity``. Alla belopp är
    per MW installerad effekt; CAPEX skalar med duration (MWh/MW).

    Args:
        stack_data: Output från ``bess_stack.build_stack_data``. ``None``
            → körs här (tar minuter; skicka in cachad data i pipelines).
        capex_eur_per_mwh: Investering per MWh lagerkapacitet.
        opex_eur_per_mw_yr: Fast årlig driftkostnad per MW.
        lifetime_yr: Kalkylperiod i år.
        discount: Diskonteringsränta (0,06 = 6 %); även tröskeln för
            ``viable``.
        revenue_decay_pct_per_yr: Real intäktsminskning per år i procent,
            verkande från år 2 (0 = ingen degradering, se modulens
            antagandelista).

    Returns:
        {"params": {...},
         "zones": {zon: {"2h": {year, year_days, year_complete, capex_eur,
                                stacked_year_eur, acceptance:
                                {"1.0": {irr_pct, npv_eur, payback_yr,
                                         annual_gross_eur, annual_net_eur,
                                         capex_eur, viable,
                                         breakeven_revenue_pct}, ...}}}},
         "best": {zone, duration_h, acceptance, irr_pct, npv_eur, ...} |
                 None}

        ``best`` är fallet med högst IRR på huvudacceptansnivån (högsta
        nivån i datat, normalt 1,0).
    """
    if stack_data is None:
        stack_data = build_stack_data()

    decay = max(0.0, revenue_decay_pct_per_yr) / 100.0
    lifetime = max(1, int(lifetime_yr))

    zones_out: Dict[str, dict] = {}
    best: Optional[dict] = None

    for zone in sorted(stack_data.get("zones", {})):
        durs = stack_data["zones"][zone]
        zone_out: Dict[str, dict] = {}
        for dur_key in sorted(durs, key=lambda k: _duration_hours(k) or 0):
            hours = _duration_hours(dur_key)
            if hours is None:
                continue
            yrow = _pick_year(durs[dur_key].get("yearly", []))
            if yrow is None:
                continue

            capex = capex_eur_per_mwh * hours
            sens = yrow.get("acceptance_sensitivity") or {
                "1.0": yrow.get("stacked_eur", 0.0)
            }

            acc_out: Dict[str, dict] = {}
            for acc_key in sorted(sens, key=_safe_float, reverse=True):
                gross = float(sens[acc_key] or 0.0)
                acc_out[acc_key] = _case(
                    gross, capex, opex_eur_per_mw_yr, lifetime,
                    discount, decay,
                )

            main_key = max(sens, key=_safe_float) if sens else None
            block = {
                "year": yrow.get("year"),
                "year_days": yrow.get("days"),
                "year_complete": (
                    (yrow.get("days") or 0) >= MIN_DAYS_COMPLETE_YEAR
                ),
                "duration_h": hours,
                "capex_eur": round(capex, 2),
                "stacked_year_eur": yrow.get("stacked_eur"),
                "arb_only_year_eur": yrow.get("arb_only_eur"),
                "best_ancillary_only_eur": yrow.get("best_ancillary_only_eur"),
                "acceptance": acc_out,
            }
            zone_out[dur_key] = block

            if main_key is not None:
                cand = acc_out[main_key]
                if cand["irr_pct"] is not None and (
                    best is None or cand["irr_pct"] > best["irr_pct"]
                ):
                    best = {
                        "zone": zone,
                        "duration_h": hours,
                        "duration_key": dur_key,
                        "acceptance": main_key,
                        "year": yrow.get("year"),
                        **cand,
                    }

        if zone_out:
            zones_out[zone] = zone_out

    return {
        "params": {
            "capex_eur_per_mwh": capex_eur_per_mwh,
            "opex_eur_per_mw_yr": opex_eur_per_mw_yr,
            "lifetime_yr": lifetime,
            "discount": discount,
            "revenue_decay_pct_per_yr": revenue_decay_pct_per_yr,
            "power_mw": (stack_data.get("params") or {}).get("power_mw", 1.0),
            "revenue_basis": (
                "stacked_eur (arbitrage + stödtjänster, perfect foresight) "
                "för senaste hela året"
            ),
            "min_days_complete_year": MIN_DAYS_COMPLETE_YEAR,
        },
        "zones": zones_out,
        "best": best,
    }


def _duration_hours(dur_key: str) -> Optional[int]:
    """'2h' → 2. Okänt format → None."""
    try:
        return int(str(dur_key).rstrip("h"))
    except (TypeError, ValueError):
        return None


def _safe_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return -1.0


# ---------------------------------------------------------------------------
# Insikter
# ---------------------------------------------------------------------------

def build_kalkyl_insights(data: dict) -> List[dict]:
    """Klartext-slutsatser ({"text","tone"}) ur ``build_kalkyl_data``.

    Tre budskap: (1) bästa business caset (zon/duration/IRR/payback),
    (2) IRR-spannet över acceptansnivåerna, (3) den ärliga brasklappen om
    att intäkten är ett perfect foresight-tak från ett enskilt år.
    """
    insights: List[dict] = []
    params = data.get("params", {})
    zones = data.get("zones", {})
    best = data.get("best")
    disc_pct = float(params.get("discount", DEFAULT_DISCOUNT)) * 100.0

    if best:
        payback_txt = (
            f"{fmt_num(best['payback_yr'], 1)} års enkel payback"
            if best.get("payback_yr") is not None
            else "ingen payback inom livslängden"
        )
        insights.append({
            "text": (
                f"Bästa business caset är {best['zone']} med "
                f"{best['duration_h']}h-batteri: IRR "
                f"{fmt_num(best['irr_pct'], 1)} % och NPV "
                f"{fmt_num(best['npv_eur'])} EUR/MW mot CAPEX "
                f"{fmt_num(best['capex_eur'])} EUR/MW "
                f"({fmt_num(params.get('capex_eur_per_mwh'))} EUR/MWh × "
                f"{best['duration_h']} h) — {payback_txt}, räknat på "
                f"{best['year']} års stackade intäkt."
            ),
            "tone": "pos" if best.get("viable") else "neg",
        })

    # IRR-spann över acceptansnivåerna för bästa zonen/durationen.
    if best:
        block = zones.get(best["zone"], {}).get(best["duration_key"], {})
        acc = block.get("acceptance", {})
        vals = [
            (k, v["irr_pct"]) for k, v in acc.items()
            if v.get("irr_pct") is not None
        ]
        if len(vals) > 1:
            vals.sort(key=lambda kv: kv[1])
            lo_key, lo_irr = vals[0]
            hi_key, hi_irr = vals[-1]
            non_viable = [k for k, v in acc.items() if not v.get("viable")]
            lo_pct = fmt_num(_safe_float(lo_key) * 100.0, 0)
            hi_pct = fmt_num(_safe_float(hi_key) * 100.0, 0)
            tail = (
                f" Vid {lo_pct} % acceptans faller caset under "
                f"avkastningskravet ({fmt_num(disc_pct, 0)} %)."
                if lo_key in non_viable else
                f" Även vid {lo_pct} % acceptans ligger caset över "
                f"avkastningskravet ({fmt_num(disc_pct, 0)} %)."
            )
            insights.append({
                "text": (
                    f"IRR {fmt_num(lo_irr, 0)}–{fmt_num(hi_irr, 0)} % "
                    f"beroende på bid-acceptans ({lo_pct}–{hi_pct} % av "
                    f"budad kapacitet antagen).{tail}"
                ),
                "tone": "neutral",
            })

    # Marginal mot prisfall: hur mycket får intäkten kollapsa?
    if best and best.get("breakeven_revenue_pct") is not None:
        be = best["breakeven_revenue_pct"]
        insights.append({
            "text": (
                f"Marginalen är stor men bygger på ett enda år: "
                f"{best['zone']} {best['duration_h']}h når "
                f"avkastningskravet redan vid {fmt_num(be, 0)} % av "
                f"{best['year']} års intäkt — caset tål alltså att den "
                f"stackade intäkten faller {fmt_num(100 - be, 0)} %. "
                "Det är marginalen mot att nya batterier pressar ned "
                "kapacitetspriserna, inte ett löfte om att de håller."
            ),
            "tone": "neutral",
        })

    # Hur många fall klarar avkastningskravet på huvudnivån?
    viable_n = 0
    total_n = 0
    for zone_block in zones.values():
        for block in zone_block.values():
            acc = block.get("acceptance", {})
            if not acc:
                continue
            main = max(acc, key=_safe_float)
            total_n += 1
            if acc[main].get("viable"):
                viable_n += 1
    if total_n:
        insights.append({
            "text": (
                f"{viable_n} av {total_n} kombinationer zon × duration "
                f"klarar avkastningskravet {fmt_num(disc_pct, 0)} % på "
                f"högsta acceptansnivån."
            ),
            "tone": "pos" if viable_n == total_n else (
                "neutral" if viable_n else "neg"
            ),
        })

    year_txt = f" ({best['year']})" if best and best.get("year") else ""
    decay = params.get("revenue_decay_pct_per_yr", 0.0) or 0.0
    decay_txt = (
        "Ingen intäktsdegradering är antagen — år 1:s intäkt upprepas "
        f"i {params.get('lifetime_yr', DEFAULT_LIFETIME_YR)} år, vilket "
        "är optimistiskt när fler batterier kommer in i budkurvan."
        if decay <= 0 else
        f"Intäkten antas falla {fmt_num(decay, 1)} %/år över livslängden."
    )
    insights.append({
        "text": (
            "Läs IRR:en som ett tak, inte som ett bud: intäkten kommer "
            "från en DP med perfect foresight inom dygnet, stödtjänsterna "
            "modelleras som ren kapacitetsmarknad utan aktivering, och "
            f"hela kalkylen vilar på ETT år av priser{year_txt} — ett "
            "ovanligt starkt mFRR-CM-år. "
            + decay_txt
        ),
        "tone": "neg",
    })

    return insights
