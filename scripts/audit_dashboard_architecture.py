"""Read-only input audit for the September 2026 dashboard architecture review.

No downloads, mutations to source data, or monkey-patching of the application.
Writes JSON only to the explicit output path. Preview aggregates use existing
effective_power_mw, local Swedish month boundaries and exact timestamp joins.
These aggregates are diagnostic, not approved financial or performance KPIs.
"""
from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elpris.config import (PARK_CAPACITY_KWP, PARK_ZONES, PROJECT_ROOT,
                           RAW_DIR, QUARTERLY_DIR, NASDAQ_DATA_DIR,
                           PARKS_PROFILE_DIR, SWEDEN_TZ, parse_iso)
from elpris.operations_dashboard_data import load_park_15min
from elpris.bazefield import parse_bazefield_ts
from elpris.park_config import get_budget, get_park_metadata


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def manifest(path, rows, time_key):
    keys = [r[time_key] for r in rows if r.get(time_key)]
    return {"path": str(path.relative_to(PROJECT_ROOT)), "rows": len(rows),
            "first": min(keys) if keys else None,
            "last": max(keys) if keys else None,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def expected_intervals(year, month):
    start = datetime(year, month, 1, tzinfo=SWEDEN_TZ)
    end = datetime(year + (month == 12), 1 if month == 12 else month + 1,
                   1, tzinfo=SWEDEN_TZ)
    return int((end.astimezone(timezone.utc) - start.astimezone(timezone.utc))
               .total_seconds() / 900)


def audit():
    result = {"audited_at": datetime.now(timezone.utc).isoformat(),
              "method": "Diagnostic preview; effective_power_mw per existing loader; "
                        "local months; exact spot joins; missing price is not zero.",
              "files": [], "spot": {}, "futures": {}, "parks": {}}
    spots = {}
    for zone in ("SE1", "SE2", "SE3", "SE4"):
        prices = {}
        for path in sorted((RAW_DIR / zone).glob("*.csv")):
            rows = read_csv(path)
            result["files"].append(manifest(path, rows, "time_start"))
            for r in rows:
                ts = parse_iso(r["time_start"]).astimezone(timezone.utc)
                end = parse_iso(r["time_end"]).astimezone(timezone.utc)
                prices[ts] = (float(r["EUR_per_kWh"]) * 1000,
                              (end - ts).total_seconds() / 3600)
        # Raw historical hour data remain hourly for correct duration weighting.
        monthly = defaultdict(list)
        for ts, (price, duration) in sorted(prices.items()):
            local = ts.astimezone(SWEDEN_TZ)
            monthly[local.strftime("%Y-%m")].append((ts, price, duration))
        result["spot"][zone] = []
        for ym, items in sorted(monthly.items()):
            year, month = map(int, ym.split("-"))
            hours = sum(d for _, _, d in items)
            expected_h = expected_intervals(year, month) / 4
            result["spot"][zone].append({
                "month": ym, "baseload": sum(p*d for _, p, d in items)/hours,
                "negative_hours": sum(d for _, p, d in items if p < 0),
                "hours": hours, "expected_hours": expected_h,
                "coverage_pct": hours / expected_h * 100,
                "daily": [[day, sum(p*d for t,p,d in items
                           if t.astimezone(SWEDEN_TZ).day == day) /
                           sum(d for t,p,d in items
                           if t.astimezone(SWEDEN_TZ).day == day)]
                          for day in sorted({t.astimezone(SWEDEN_TZ).day for t,_,_ in items})],
            })
        # Use processed input for park joins to expose actual dependency staleness.
        processed = {}
        for path in sorted((QUARTERLY_DIR / zone).glob("*.csv")):
            rows = read_csv(path)
            result["files"].append(manifest(path, rows, "time_start"))
            for r in rows:
                ts = parse_iso(r["time_start"]).astimezone(timezone.utc)
                processed[ts] = float(r["EUR_per_kWh"]) * 1000
        spots[zone] = processed

    for path in sorted(NASDAQ_DATA_DIR.glob("*.csv")):
        rows = read_csv(path)
        item = manifest(path, rows, "date")
        item["columns"] = list(rows[0]) if rows else []
        result["files"].append(item)
        by_contract = defaultdict(list)
        for r in rows:
            if not r.get("daily_fix_eur"):
                continue
            by_contract[r["contract"]].append({"date": r["date"],
                "settlement": float(r["daily_fix_eur"]),
                "open_interest_raw": r.get("open_interest") or None})
        result["futures"][path.stem] = {
            k: sorted(v, key=lambda r: r["date"]) for k,v in by_contract.items()}

    for park, capacity in PARK_CAPACITY_KWP.items():
        zone = PARK_ZONES[park]
        path = PARKS_PROFILE_DIR / f"{park}_{zone}.csv"
        raw = read_csv(path)
        result["files"].append(manifest(path, raw, "timestamp"))
        raw_by_ts = {parse_bazefield_ts(r["timestamp"]).astimezone(timezone.utc): r for r in raw}
        grouped = defaultdict(dict)
        for r in load_park_15min(park):
            ts = r["timestamp_utc"]
            grouped[ts.astimezone(SWEDEN_TZ).strftime("%Y-%m")][ts] = r
        summaries = []
        for ym, unique in sorted(grouped.items()):
            if ym < "2026-01":
                continue
            year, month = map(int, ym.split("-"))
            expected = expected_intervals(year, month)
            records = list(unique.values())
            energy = sum(r["effective_power_mw"] * .25 for r in records)
            positive = [(r["timestamp_utc"], r["effective_power_mw"] * .25)
                        for r in records if r["effective_power_mw"] > 0]
            matched = [(e, spots[zone][ts]) for ts,e in positive if ts in spots[zone]]
            priced_energy = sum(e for e,p in matched)
            poa_records = [r for r in records if r.get("irradiance_poa") is not None]
            # Pair both sides of PR on the same valid POA observation set.
            irradiation = sum(max(0, r["irradiance_poa"]) * .25/1000 for r in poa_records)
            paired_energy = sum(r["effective_power_mw"] * .25 for r in poa_records)
            fallback_positive = [r for r in records if r["power_mw"] <= 0
                                 and r["effective_power_mw"] > 0]
            present_zero = sum(raw_by_ts[r["timestamp_utc"]].get("power_mw", "") not in ("", None)
                               for r in fallback_positive)
            budget = get_budget(park, year, month)
            summaries.append({"month": ym, "energy_mwh": energy,
                "budget_mwh": budget["energy_mwh"], "budget_pr_pct": budget["pr_pct"],
                "vs_budget_pct": (energy / budget["energy_mwh"] - 1)*100
                                  if budget["energy_mwh"] else None,
                "yield_kwh_kwp": energy / (capacity/1000),
                "pr_paired_pct": paired_energy / (capacity/1000 * irradiation) *100
                                 if irradiation > 0 else None,
                "coverage_pct": len(unique)/expected*100,
                "poa_coverage_pct": len(poa_records)/expected*100,
                "priced_energy_mwh": priced_energy,
                "capture_eur_mwh": sum(e*p for e,p in matched)/priced_energy
                                   if priced_energy else None,
                "price_energy_coverage_pct": priced_energy / sum(e for _,e in positive)*100
                    if positive else None,
                "fallback_positive_intervals": len(fallback_positive),
                "fallback_present_meter_intervals": present_zero,
                "daily_energy": [[d, sum(r["effective_power_mw"]*.25 for r in records
                                      if r["timestamp_utc"].astimezone(SWEDEN_TZ).day==d)]
                    for d in range(1, calendar.monthrange(year, month)[1]+1)],
            })
        result["parks"][park] = {"name": get_park_metadata(park)["display_name"],
            "zone": zone, "capacity_kwp": capacity, "months": summaries}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2,
                                     allow_nan=False) + "\n", encoding="utf-8")
    print(f"Audited {len(data['files'])} inputs → {args.output}")
