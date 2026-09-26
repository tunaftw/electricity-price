"""Det som förs över från Track C till huvudversionen (Electricity Price).

Inga nya beräkningar: modulen anropar samma funktioner som Track C
(``dashboard_v2_data``, ``ancillary_dashboard_data``, ``nordic_market_data``
och ``unified_dashboard_data._park_facts``) och plockar ut det som visas.
Därför blir talen desamma som i Track C för samma data. Motiveringen per del
står i vaultens 01-produktversion.md, avsnitt 4.

* **Capture per panelutformning** — spotpriset viktat med PVsyst-typårsprofiler
  (syd, öst–väst, tracker). En modell, inte uppmätt produktion: nivån ligger
  5–8 procentenheter för högt (se Översikts definitioner), så sidan visar den
  som jämförelse mellan utformningar.
* **Spotpris per timme × månad** — medelpris per cell. Timmen är UTC-timme,
  som i Track C (``_calculate_hour_month_heatmap``).
* **Stödtjänster** — kapacitetsintäkt per MW och månad vid 100 % tillgänglighet
  och accepterade bud. ``last_12m`` räknas som Track C:s ``ancLast12mRevenue``.
* **Nordiska terminer** — hela ``build_nordic_market_data``: kontrakt för sex
  zoner och historisk baseload.
* **Parkfakta** — metadata, ingen beräkning.
"""

from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional

PROFILE_KEYS = ("sol_syd", "sol_ov", "sol_tracker")
ANC_KEYS = ("anc_fcr_n", "anc_fcr_d_up", "anc_fcr_d_down", "anc_afrr_up", "anc_afrr_down",
            "anc_mfrr_cm_up", "anc_mfrr_cm_down")


def _warn(what: str, exc: Exception) -> None:
    print(f"  [tillägg] {what} misslyckades: {exc}", file=sys.stderr)


def build_profile_capture(zones: List[str]) -> Dict[str, Any]:
    """Capture per panelutformning (PVsyst) och heatmap per zon."""
    from ..dashboard_v2_data import (
        STANDARD_SOLAR_PROFILES,
        _aggregate_to_monthly,
        _aggregate_to_yearly,
        _calculate_hour_month_heatmap,
        _calculate_profile_capture,
        load_pvsyst_profile,
        load_spot_prices,
    )
    profiles = {k: load_pvsyst_profile(STANDARD_SOLAR_PROFILES[k][0]) for k in PROFILE_KEYS}
    capture: Dict[str, Any] = {}
    heatmap: Dict[str, Any] = {}
    for zone in zones:
        spot = load_spot_prices(zone)
        if not spot:
            continue
        capture[zone] = {}
        for key, prof in profiles.items():
            if not prof:
                continue
            daily = _calculate_profile_capture(spot, prof)
            capture[zone][key] = {"monthly": _aggregate_to_monthly(daily),
                                  "yearly": _aggregate_to_yearly(daily)}
        years = sorted({int(k[:4]) for k in spot})
        heatmap[zone] = {"all": _calculate_hour_month_heatmap(spot),
                         "by_year": {str(y): _calculate_hour_month_heatmap(spot, year=y) for y in years},
                         "years": years}
    return {"capture": capture, "heatmap": heatmap}


def anc_last_12m(monthly: List[Dict[str, Any]]) -> Optional[float]:
    """Samma regel som Track C (``ancLast12mRevenue``): summan av de 12 sista
    månaderna; färre än 12 (men minst 6) skalas upp till ett år."""
    if not monthly:
        return None
    tail = monthly[-12:]
    if len(tail) < 6:
        return None
    vals = [r["baseload"] if r.get("baseload") is not None else r.get("capture") for r in tail]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    total = sum(vals)
    return total if len(tail) == 12 else total / len(tail) * 12


def build_ancillary(zones: List[str]) -> Dict[str, Any]:
    from ..ancillary_dashboard_data import calculate_ancillary_data
    res = calculate_ancillary_data(zones)
    out: Dict[str, Any] = {}
    for zone, series in res["data"].items():
        out[zone] = {}
        for key in ANC_KEYS:
            s = series.get(key)
            if not s or not s.get("monthly"):
                continue
            monthly = [{"month": f"{r['year']}-{r['month']:02d}",
                        "eur_mw": r["baseload"] if r.get("baseload") is not None else r.get("capture")}
                       for r in s["monthly"]]
            out[zone][key] = {"monthly": monthly, "last_12m": anc_last_12m(s["monthly"]),
                              "last_12m_from": monthly[-12:][0]["month"], "last_12m_to": monthly[-1]["month"]}
    return out


def build_park_facts(parks: List[str]) -> Dict[str, Any]:
    from ..unified_dashboard_data import _park_facts
    facts = {}
    for p in parks:
        f = _park_facts(p) or {}
        f.pop("expected_pr_pct", None)   # PR visas inte (POA-förskjutningen)
        facts[p] = f
    return facts


def build_tillagg_data(parks: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    zones = ["SE1", "SE2", "SE3", "SE4"]
    for key, fn in (("profiles", lambda: build_profile_capture(zones)),
                    ("ancillary", lambda: build_ancillary(zones)),
                    ("park_facts", lambda: build_park_facts(parks))):
        try:
            out[key] = fn()
        except Exception as exc:  # en saknad del ska inte stoppa sidan
            _warn(key, exc)
            out[key] = None
    try:
        from ..nordic_market_data import build_nordic_market_data
        out["nordic"] = build_nordic_market_data()
    except Exception as exc:
        _warn("nordic", exc)
        out["nordic"] = None
    return out
