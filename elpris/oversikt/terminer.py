"""Terminer: områdespris (SYS + EPAD) för SE3/SE4 och hur det rört sig.

Definitioner (samma som visas på sidan):

* **Områdespris** — systempris (SYS) + områdestillägg (EPAD) för samma
  kontrakt och samma handelsdag. Saknas ett ben finns inget områdespris.
* **Förändring** — dagens områdespris minus senaste notering *på eller
  före* samma datum 1 vecka / 1 månad / 3 / 12 månader tidigare. Ligger den
  noteringen mer än ``STALE_DAYS`` dagar före måldatumet (lucka i datat)
  märks jämförelsen.
* **Vad marknaden trodde** — sista områdespriset före leveransstart mot
  det faktiska tidsviktade spotpriset under kvartalet.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from ..futures_zonal import (
    EPAD_FILES,
    SYS_FILE,
    _read_settlements,
    load_zonal_forward_history,
    parse_contract_label,
)
from ..config import NASDAQ_DATA_DIR
from .common import CAL, QUARTER_S, month_bounds, quarter_prices

ZONES = ("SE3", "SE4")
CHANGE_WINDOWS = (("1v", 7), ("1m", 30), ("3m", 91), ("12m", 365))
STALE_DAYS = 10
GAP_DAYS = 20          # längre period utan noteringar = lucka
UPCOMING_QUARTERS = 2
UPCOMING_YEARS = 3
FRESH_DAYS = 14        # kontrakt måste ha noterats inom så här många dagar

_SV_MONTHS = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]


def delivery_label(meta: Dict[str, str]) -> str:
    start = date.fromisoformat(meta["delivery_start"])
    end = date.fromisoformat(meta["delivery_end"])
    if meta["kind"] == "YR":
        return f"helår {start.year}"
    if meta["kind"] == "Q":
        return f"{_SV_MONTHS[start.month - 1]}–{_SV_MONTHS[end.month - 1]} {start.year}"
    return f"{_SV_MONTHS[start.month - 1]} {start.year}"


def _on_or_before(series: List[Tuple], target: str) -> Optional[Tuple]:
    best = None
    for obs in series:
        if obs[0] <= target:
            best = obs
        else:
            break
    return best


def _days(a: str, b: str) -> int:
    return (date.fromisoformat(a) - date.fromisoformat(b)).days


def _realized(zone: str, start: str, end_incl: str, data_end: int) -> Tuple[Optional[float], Optional[str]]:
    prices = quarter_prices(zone)
    s, _ = month_bounds(start[:7])
    _, e = month_bounds(end_incl[:7])
    e = min(e, data_end)
    vals = [prices[q] for q in range(s, e, QUARTER_S) if q in prices]
    if not vals:
        return None, None
    partial = CAL.day(e - 1) if e < month_bounds(end_incl[:7])[1] else None
    return sum(vals) / len(vals), partial


def build_terminer_data(data_end: int) -> Dict[str, Any]:
    fwd = load_zonal_forward_history(zones=ZONES)
    contracts = fwd["contracts"]
    zones = [z for z in ZONES if fwd["zones"].get(z)]
    if not zones:
        return {}
    sys_series = _read_settlements(NASDAQ_DATA_DIR / SYS_FILE)

    all_dates = sorted({obs[0] for z in zones for s in fwd["zones"][z].values() for obs in s})
    latest = all_dates[-1]

    # Kontrakt i tabellen: närmaste kvartal och år som ännu inte börjat levereras
    # och som noterats nyligen.
    def fresh(label: str) -> bool:
        last = max((fwd["zones"][z].get(label, [("0000-00-00",)])[-1][0] for z in zones))
        return _days(latest, last) <= FRESH_DAYS

    upcoming = [(lbl, m) for lbl, m in contracts.items() if m["delivery_start"] > latest and fresh(lbl)]
    quarters = [lbl for lbl, m in upcoming if m["kind"] == "Q"][:UPCOMING_QUARTERS]
    years = [lbl for lbl, m in upcoming if m["kind"] == "YR"][:UPCOMING_YEARS]
    table_contracts = quarters + years

    table: Dict[str, Dict[str, Any]] = {}
    for z in zones:
        table[z] = {}
        for label in table_contracts:
            series = fwd["zones"][z].get(label)
            if not series:
                continue
            last = series[-1]
            changes = {}
            for key, days in CHANGE_WINDOWS:
                target = (date.fromisoformat(latest) - timedelta(days=days)).isoformat()
                ref = _on_or_before(series, target)
                if ref is None:
                    changes[key] = None
                    continue
                changes[key] = {
                    "delta": round(last[1] - ref[1], 2),
                    "ref_value": ref[1],
                    "ref_date": ref[0],
                    "stale": _days(target, ref[0]) > STALE_DAYS,
                }
            table[z][label] = {"value": last[1], "date": last[0], "sys": last[2], "epad": last[3],
                               "changes": changes}

    # Luckor: perioder utan någon notering alls.
    gaps = []
    for a, b in zip(all_dates, all_dates[1:]):
        if _days(b, a) > GAP_DAYS:
            gaps.append({"from": (date.fromisoformat(a) + timedelta(days=1)).isoformat(),
                         "to": (date.fromisoformat(b) - timedelta(days=1)).isoformat()})

    # Historik för diagrammet (samma kontrakt som tabellen).
    history = {}
    for label in table_contracts:
        dates = sorted({obs[0] for z in zones for obs in fwd["zones"][z].get(label, [])}
                       | set(sys_series.get(label, {})))
        # Lägg in en tom punkt i varje lucka så att linjen bryts.
        for g in gaps:
            if dates and dates[0] < g["from"] < dates[-1]:
                dates.append(g["from"])
        dates = sorted(set(dates))
        by_zone = {z: dict((o[0], o[1]) for o in fwd["zones"][z].get(label, [])) for z in zones}
        sys_map = sys_series.get(label, {})
        history[label] = {"dates": dates, "SYS": [sys_map.get(d) for d in dates]}
        for z in zones:
            history[label][z] = [by_zone[z].get(d) for d in dates]

    # Vad marknaden trodde: levererade kvartal.
    data_end_day = CAL.day(data_end - 1)
    convergence = []
    for label, meta in contracts.items():
        if meta["kind"] != "Q" or meta["delivery_start"] > data_end_day or meta["delivery_start"] < "2024-01-01":
            continue
        row: Dict[str, Any] = {"label": label, "delivery": delivery_label(meta), "partial": None}
        any_fwd = False
        for z in zones:
            series = fwd["zones"][z].get(label, [])
            before = [o for o in series if o[0] < meta["delivery_start"]]
            realized, partial = _realized(z, meta["delivery_start"], meta["delivery_end"], data_end)
            row["partial"] = row["partial"] or partial
            if before:
                any_fwd = True
                f = before[-1]
                row[z] = {"forward": f[1], "forward_date": f[0],
                          "realized": round(realized, 2) if realized is not None else None,
                          "diff": round(realized - f[1], 2) if realized is not None else None}
            else:
                row[z] = {"forward": None, "forward_date": None,
                          "realized": round(realized, 2) if realized is not None else None, "diff": None}
        if any_fwd:
            convergence.append(row)
    convergence.sort(key=lambda r: contracts[r["label"]]["delivery_start"], reverse=True)
    convergence = convergence[:8]

    # Klartext.
    lede = None
    front = years[0] if years else (table_contracts[0] if table_contracts else None)
    if front:
        parts = []
        for z in zones:
            r = table[z].get(front)
            if not r:
                continue
            ch = r["changes"].get("3m")
            s = f"<b>{_fmt(r['value'])} €/MWh</b> i {z}"
            if ch and ch["delta"] is not None:
                s += f" ({_signed(ch['delta'])} sedan {_fmt_day(ch['ref_date'])})"
            parts.append(s)
        lede = (f"Terminen för {delivery_label(contracts[front])} ({front}) kostar nu " + " och ".join(parts) + ".")
        full = [r for r in convergence if not r.get("partial")][:3]
        if full:
            per_zone = []
            diffs = []
            for z in zones:
                d = [r[z]["diff"] for r in full if r.get(z) and r[z].get("diff") is not None]
                if d:
                    diffs.extend(d)
                    per_zone.append(f"{z} {_signed(sum(d) / len(d))}")
            if per_zone:
                word = "dyrare" if sum(diffs) > 0 else "billigare"
                if len(full) == 1:
                    head = f" Under {full[0]['label']} blev spotpriset {word} än terminen strax före leverans: "
                else:
                    head = (f" De senaste {len(full)} levererade kvartalen blev spotpriset i snitt {word} "
                            "än terminen strax före leverans: ")
                lede += head + ", ".join(per_zone) + " €/MWh."

    recent = [d for d in all_dates if _days(latest, d) < 30]
    flags = []
    for g in gaps:
        if g["from"] >= "2026-01-01":
            flags.append(f"Inga terminsnoteringar {_fmt_day(g['from'])}–{_fmt_day(g['to'])}. Förändringar som "
                         "jämför över luckan använder senaste noteringen före (märkt †).")
    if len(recent) < 15:
        flags.append(f"Bara {len(recent)} handelsdagar med noteringar de senaste 30 dagarna. Sedan flytten till "
                     "Euronext sparas priset bara de dagar hämtningen körs. Det dagliga hämtjobbet "
                     "(scripts/README.md) fyller i framåt.")

    return {
        "latest_date": latest,
        "zones": zones,
        "contracts": [{"label": c, "delivery": delivery_label(contracts[c])} for c in table_contracts],
        "contract_meta": {c: {"delivery": delivery_label(contracts[c])} for c in table_contracts},
        "default_contract": years[0] if years else (table_contracts[0] if table_contracts else None),
        "table": table,
        "history": history,
        "gaps": gaps,
        "convergence": convergence,
        "lede": lede,
        "flags": flags,
        "obs_last_30d": len(recent),
    }


def _fmt(v: float, d: int = 1) -> str:
    return f"{v:,.{d}f}".replace(",", " ").replace(".", ",")


def _signed(v: float) -> str:
    return ("+" if v > 0 else "−" if v < 0 else "") + _fmt(abs(v))


def _fmt_day(day: str) -> str:
    d = date.fromisoformat(day)
    return f"{d.day} {_SV_MONTHS[d.month - 1]} {d.year}"
