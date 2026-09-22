"""Datastatus: hur färsk varje källa är och kända problem i underlaget."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .common import CAL, park_records, available_zones, solar_quarters, spot_end_epoch

# Instrålning i planet (POA) över detta är fysiskt orimligt i Sverige.
POA_MAX_PLAUSIBLE = 1500.0
POA_SHIFT_WARN_MIN = 45
STALE_DAYS_WARN = 3


def _status(last_day: Optional[str], ref_day: str, warn_days: int = STALE_DAYS_WARN) -> str:
    if not last_day:
        return "saknas"
    lag = (datetime.fromisoformat(ref_day) - datetime.fromisoformat(last_day)).days
    return "ok" if lag <= warn_days else "gammal"


def poa_issues(park: str, since_days: int = 60) -> Optional[Dict[str, Any]]:
    """Kontrollera instrålningsgivaren (POA) de senaste ``since_days`` dygnen.

    Två fel letas efter:
    * orimliga värden (> POA_MAX_PLAUSIBLE W/m²) — trasig givare/sentinel,
    * tidsförskjutning: dygnets tyngdpunkt för POA jämfört med produktionens
      tyngdpunkt. Produktionen ligger rätt mot solens middag; ligger POA mer än
      POA_SHIFT_WARN_MIN minuter fel går POA inte att para ihop kvart för kvart.
    """
    recs = park_records(park)
    if not recs:
        return None
    cutoff = recs[-1]["timestamp_utc"] - timedelta(days=since_days)
    too_high = 0
    first_bad = None
    p_sum = p_mom = e_sum = e_mom = 0.0
    for r in recs:
        if r["timestamp_utc"] < cutoff:
            continue
        minute = r["timestamp_utc"].hour * 60 + r["timestamp_utc"].minute
        if r.get("energy_source") in ("meter", "inverter") and r["effective_power_mw"] > 0:
            e_sum += r["effective_power_mw"]
            e_mom += r["effective_power_mw"] * minute
        poa = r.get("irradiance_poa")
        if poa is None:
            continue
        if poa > POA_MAX_PLAUSIBLE:
            too_high += 1
            if first_bad is None:
                first_bad = r["timestamp_utc"]
        elif poa > 0:
            p_sum += poa
            p_mom += poa * minute
    shift = None
    if p_sum > 0 and e_sum > 0:
        shift = p_mom / p_sum - e_mom / e_sum
    out = {
        "too_high": too_high,
        "first_bad": CAL.day(int(first_bad.timestamp())) if first_bad else None,
        "shift_min": round(shift) if shift is not None else None,
    }
    if too_high >= 8 or (shift is not None and abs(shift) > POA_SHIFT_WARN_MIN):
        return out
    return None


def build_datastatus(ref_day: str, portfolj: Dict[str, Any],
                     terminer: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    sources: List[Dict[str, Any]] = []
    for z in available_zones():
        end = spot_end_epoch(z)
        last = CAL.day(end - 1) if end else None
        sources.append({"group": "Spotpriser", "name": f"Spotpris {z}",
                        "source": "elprisetjustnu.se" if z.startswith("SE") else "ENTSO-E",
                        "last": last, "status": _status(last, ref_day)})
    for z in available_zones():
        sq = solar_quarters(z)
        last = CAL.day(max(sq)) if sq else None
        sources.append({"group": "Solproduktion per zon", "name": f"Sol {z}", "source": "ENTSO-E",
                        "last": last, "status": _status(last, ref_day)})
    if terminer:
        last = terminer.get("latest_date")
        sources.append({"group": "Terminer", "name": "SYS + EPAD (SE1–SE4)",
                        "source": "Nasdaq t.o.m. 29 apr 2026, därefter Euronext",
                        "last": last, "status": _status(last, ref_day, warn_days=4)})

    issues: List[Dict[str, str]] = []
    shifted: List[tuple] = []
    parks_status = []
    for key, p in portfolj["parks"].items():
        info = p["info"]
        last_obs = p["last_observed"]
        last_meter = p["last_meter"]
        parks_status.append({
            "park": info["name"], "zone": info["zone"],
            "last_observed": last_obs, "last_meter": last_meter,
            "status": _status(last_meter, ref_day),
        })
        if last_meter and _status(last_meter, ref_day) != "ok":
            issues.append({
                "park": info["name"],
                "text": f"Elmätaren har inte rapporterat sedan {_fmt_day(last_meter)}. "
                        "Invertervärdena efter det är fastfrusna och räknas inte som produktion.",
            })
        poa = poa_issues(key)
        if poa and poa["too_high"] >= 8:
            issues.append({
                "park": info["name"],
                "text": f"Instrålningsgivaren visar orimliga värden (över {POA_MAX_PLAUSIBLE:.0f} W/m²) "
                        f"sedan {_fmt_day(poa['first_bad'])}. Produktionen påverkas inte, men PR och "
                        "väderförklaringar i månadsrapporterna går inte att lita på.",
            })
        if poa and poa["shift_min"] is not None and abs(poa["shift_min"]) > POA_SHIFT_WARN_MIN:
            shifted.append((info["name"], poa["shift_min"]))
        low = [mk for mk, m in p["months"].items()
               if m["coverage"] is not None and m["coverage"] < 0.8 and mk >= f"{ref_day[:4]}-01"]
        if low:
            issues.append({
                "park": info["name"],
                "text": "Mätdata saknas för mer än 20 % av dagsljuset i "
                        + ", ".join(_fmt_month(mk) for mk in low)
                        + " — ingen budgetjämförelse för de månaderna.",
            })
    if shifted:
        mean_shift = sum(m for _, m in shifted) / len(shifted)
        issues.insert(0, {
            "park": "Alla parker" if len(shifted) == len(portfolj["parks"]) else ", ".join(n for n, _ in shifted),
            "text": f"Instrålningsdatan (POA) ligger i snitt {abs(mean_shift) / 60:.1f} timmar "
                    f"{'efter' if mean_shift > 0 else 'före'} produktionen de senaste 60 dygnen, "
                    "fast båda borde toppa vid solens middag. Produktionens tidsstämplar stämmer, så den här "
                    "sidans siffror påverkas inte. Allt som parar ihop instrålning och produktion timme för "
                    "timme (PR på giltiga intervall, dagsvisa väderförklaringar) blir fel; månadssummor "
                    "av instrålning påverkas knappt.",
        })
    # En rad per park: slå ihop parkens problem.
    merged: Dict[str, List[str]] = {}
    for i in issues:
        merged.setdefault(i["park"], []).append(i["text"])
    issues = [{"park": k, "text": " ".join(v)} for k, v in merged.items()]
    return {"ref_day": ref_day, "sources": sources, "parks": parks_status, "issues": issues}


_MONTHS = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]


def _fmt_day(day: Optional[str]) -> str:
    if not day:
        return "okänt datum"
    d = datetime.fromisoformat(day)
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year}"


def _fmt_month(mk: str) -> str:
    return f"{_MONTHS[int(mk[5:]) - 1]} {mk[:4]}"
