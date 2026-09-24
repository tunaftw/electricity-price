"""Versioned, read-only data export for the new Elpris analysis application.

No dashboard/report imports. Raw CSV inputs are normalized once, with UTC
interval keys and Swedish business periods. Existing source files are untouched.
"""
from __future__ import annotations

import calendar
import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from .bazefield import parse_bazefield_ts
from .config import (RAW_DIR, PARKS_PROFILE_DIR, NASDAQ_DATA_DIR, PROJECT_ROOT,
                     PARK_CAPACITY_KWP, PARK_ZONES, SWEDEN_TZ, parse_iso)
from .park_config import get_budget, get_park_metadata, get_ppa

METRIC_VERSION = "intelligence-1.0"
UTC = timezone.utc


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def quarter_prices(rows):
    """Normalize 15/60-minute observations, rejecting overlaps and bad durations.

    The original resolution is kept; expanding an hour never adds information.
    """
    out = {}
    ordered = sorted(rows, key=lambda r: parse_iso(r['time_start']).astimezone(UTC))
    for index, row in enumerate(ordered):
        start = parse_iso(row["time_start"]).astimezone(UTC)
        end = parse_iso(row["time_end"]).astimezone(UTC)
        adjusted = False
        # Some source rows cross the autumn offset change with an erroneous
        # end, while the repeated hour is supplied as its own observation.
        # Only shorten that specific overlap when the next start proves it.
        if index + 1 < len(ordered):
            nxt = parse_iso(ordered[index+1]['time_start']).astimezone(UTC)
            changed_offset = parse_iso(row['time_start']).utcoffset() != parse_iso(row['time_end']).utcoffset()
            if changed_offset and start < nxt < end and (nxt-start).total_seconds() in (900,3600):
                end, adjusted = nxt, True
        minutes = int((end - start).total_seconds() / 60)
        if (end-start).total_seconds() not in (900, 3600):
            raise ValueError(f"Unsupported spot interval {start}: {end-start}")
        eur, sek, fx = (number(row.get(k)) for k in ("EUR_per_kWh", "SEK_per_kWh", "EXR"))
        if eur is None:
            continue
        for offset in range(0, minutes, 15):
            ts = start + timedelta(minutes=offset)
            val = {"eur": eur*1000, "sek": sek*1000 if sek is not None else None,
                   "fx": fx if fx and fx > 0 else None, "native_minutes": minutes,
                   "end_adjusted": adjusted}
            if ts in out and out[ts] != val:
                raise ValueError(f"Conflicting price observations: {ts}")
            out[ts] = val
    return out


def effective_observation(row, capacity_mw):
    """A valid zero meter stays zero. Missing/invalid grid may use inverter.

    Inverter substitution is an estimate of net delivery, not revenue-grade
    metering. Invalid/stuck inputs never become a fictitious zero observation.
    """
    meter = number(row.get("power_mw"))
    inverter = number(row.get("active_power_mw"))
    meter_ok = meter is not None and -capacity_mw <= meter <= capacity_mw
    inverter_ok = inverter is not None and 0 <= inverter <= capacity_mw
    if meter_ok:
        power, source = meter, "meter"
    elif inverter_ok:
        power, source = inverter, "inverter_estimate"
    else:
        power, source = None, "missing"
    poa = number(row.get("irradiance_poa"))
    if poa is not None and not 0 <= poa <= 1600:
        poa = None
    availability = number(row.get("availability"))
    if availability is not None and not 0 <= availability <= 1:
        availability = None
    return {"effective_power_mw": power, "energy_source": source,
            "meter_mw": meter, "inverter_mw": inverter,
            "poa": poa, "availability": availability}


def load_production(rows, capacity_mw):
    out = {}
    for row in rows:
        ts = parse_bazefield_ts(row["timestamp"]).astimezone(UTC)
        value = effective_observation(row, capacity_mw)
        if ts in out and out[ts] != value:
            raise ValueError(f"Conflicting park observations: {ts}")
        out[ts] = value
    days = defaultdict(list)
    for ts, val in out.items():
        days[ts.astimezone(SWEDEN_TZ).date()].append(val)
    for values in days.values():
        estimates = [v for v in values if v["energy_source"] == "inverter_estimate"]
        distinct = {v["effective_power_mw"] for v in estimates}
        if len(estimates) == len(values) and len(values) >= 8 and len(distinct) == 1 and next(iter(distinct)) > 0:
            for v in values:
                v.update(effective_power_mw=None, energy_source="stuck")
    return out


def expected_quarters(year, month):
    a = datetime(year, month, 1, tzinfo=SWEDEN_TZ).astimezone(UTC)
    b = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=SWEDEN_TZ).astimezone(UTC)
    return int((b-a).total_seconds()/900)


def aggregate_park(observations, prices, capacity_kwp, ppa=None):
    valid = [(ts,r) for ts,r in observations.items() if r["effective_power_mw"] is not None]
    exported = [(ts,max(0,r["effective_power_mw"])*.25,r) for ts,r in valid]
    net = sum(r["effective_power_mw"]*.25 for _,r in valid)
    volume = sum(e for _,e,_ in exported)
    joined = [(ts,e,r,prices[ts]) for ts,e,r in exported if ts in prices]
    priced = sum(e for _,e,_,_ in joined)
    revenue = sum(e*p["eur"] for _,e,_,p in joined)
    baseline = sum(p["eur"] for _,_,_,p in joined)/len(joined) if joined else None
    pairs = [(r["effective_power_mw"]*.25,r["poa"]) for _,r in valid if r["poa"] is not None]
    poa = sum(h*.25/1000 for _,h in pairs)
    paired_energy = sum(e for e,_ in pairs)
    pr = paired_energy/(capacity_kwp/1000*poa)*100 if poa > 0 else None
    estimated = sum(e for _,e,r in exported if r["energy_source"]=="inverter_estimate")
    avail = [r["availability"] for _,r in valid if r["availability"] is not None]
    ppa_revenue = None
    if ppa and joined and all(p["fx"] for _,e,_,p in joined if e>0):
        share = ppa["share_pct"]/100
        ppa_revenue = sum(e*(share*ppa["price_sek_mwh"]/p["fx"]+(1-share)*p["eur"])
                          for _,e,_,p in joined if e>0)
    return {"energy_mwh": net if valid else None, "export_mwh": volume if valid else None,
            "priced_mwh": priced, "spot_value_eur": revenue if joined else None,
            "capture": revenue/priced if priced>0 else None,
            "matched_baseload_eur": baseline,
            "capture_rate": revenue/priced/baseline*100 if priced>0 and baseline is not None and baseline>1 else None,
            "estimated_mwh": estimated, "valid_intervals": len(valid),
            "poa_intervals": len(pairs), "poa_kwh_m2": poa,
            "pr_paired_energy_mwh": paired_energy, "pr": pr,
            "availability": sum(avail)/len(avail)*100 if avail else None,
            "availability_intervals": len(avail),
            "price_coverage": priced/volume*100 if volume>0 else None,
            "negative_mwh": sum(e for _,e,_,p in joined if p["eur"]<0),
            "negative_value_eur": sum(e*p["eur"] for _,e,_,p in joined if p["eur"]<0),
            "ppa_model_eur": ppa_revenue}


def contract_period(symbol):
    m = re.search(r"(YR|Q([1-4]))-(\d{2})$", symbol)
    if not m:
        return None
    year = 2000+int(m[3])
    first = 1 if m[1]=="YR" else (int(m[2])-1)*3+1
    last = 12 if m[1]=="YR" else first+2
    return {"label": f"{m[1]}-{m[3]}", "start": f"{year}-{first:02d}-01",
            "end": f"{year}-{last:02d}-{calendar.monthrange(year,last)[1]}",
            "year": year}


def latest_on_or_before(rows, day, max_age_days=7):
    eligible = [r for r in rows if r[0] <= day]
    if not eligible:
        return None
    row = max(eligible, key=lambda r:r[0])
    age = (datetime.fromisoformat(day)-datetime.fromisoformat(row[0])).days
    return row if age <= max_age_days else None


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",",":"),
                               allow_nan=False), encoding="utf-8")


def _build_intelligence_data(output_dir):
    output_dir = Path(output_dir)
    sources = []
    def source(path, rows, key):
        times = [r[key] for r in rows if r.get(key)]
        sources.append({"path": str(path.resolve().relative_to(PROJECT_ROOT)),
            "rows": len(rows), "first": min(times) if times else None,
            "last": max(times) if times else None,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    # Version also changes when metric logic, budgets or capacities change.
    for path in [Path(__file__), PROJECT_ROOT/'elpris/park_config.py',
                 PROJECT_ROOT/'elpris/config.py', PROJECT_ROOT/'elpris/park_product_data.py']:
        sources.append({"path": str(path.relative_to(PROJECT_ROOT)), "rows": 0,
            "first": None,"last": None,"sha256":hashlib.sha256(path.read_bytes()).hexdigest()})
    prices = {}
    market = {}
    for zone in ["SE1","SE2","SE3","SE4"]:
        all_rows = []
        for path in sorted((RAW_DIR/zone).glob('*.csv')):
            rows = read_rows(path); source(path, rows, 'time_start'); all_rows.extend(rows)
        data = quarter_prices(all_rows)
        prices[zone] = data
        monthly, yearly = defaultdict(dict), defaultdict(list)
        for ts,r in sorted(data.items()):
            local = ts.astimezone(SWEDEN_TZ)
            monthly[local.strftime('%Y-%m')][ts] = r
            yearly[str(local.year)].append([local.isoformat(),r['eur'],r['sek'],r['native_minutes']])
        market[zone] = []
        for ym, group in sorted(monthly.items()):
            y,m = map(int,ym.split('-')); vals=[r['eur'] for r in group.values()]
            market[zone].append({'month':ym,'baseload':sum(vals)/len(vals),
                'negative_hours':sum(v<0 for v in vals)*.25,
                'coverage':len(vals)/expected_quarters(y,m)*100,'hours':len(vals)*.25,
                'min':min(vals),'max':max(vals)})
        for year, rows in yearly.items(): write_json(output_dir/'spot'/f'{zone}-{year}.json',rows)
    parks = {}
    for park,capacity in PARK_CAPACITY_KWP.items():
        zone=PARK_ZONES[park]; path=PARKS_PROFILE_DIR/f'{park}_{zone}.csv'
        rows=read_rows(path); source(path,rows,'timestamp')
        data=load_production(rows,capacity/1000)
        months=defaultdict(dict)
        for ts,r in sorted(data.items()): months[ts.astimezone(SWEDEN_TZ).strftime('%Y-%m')][ts]=r
        ppa=get_ppa(park)
        meta=get_park_metadata(park)
        parks[park]={'name':meta['display_name'],'zone':zone,'capacity_kwp':capacity,
                    'ppa':ppa,'months':[], 'latest':max(data).astimezone(SWEDEN_TZ).isoformat() if data else None}
        for ym,group in sorted(months.items()):
            year,month=map(int,ym.split('-')); expected=expected_quarters(year,month)
            values=aggregate_park(group,prices[zone],capacity,ppa)
            budget=get_budget(park,year,month)
            values.update(month=ym,budget_mwh=budget['energy_mwh'],budget_pr=budget['pr_pct'],
                coverage=values['valid_intervals']/expected*100,
                poa_coverage=values['poa_intervals']/expected*100,
                availability_coverage=values['availability_intervals']/expected*100,
                expected_intervals=expected)
            values['pr_quality']='insufficient' if values['poa_coverage']<95 else ('review' if values['pr'] is not None and values['pr']>100 else 'provisional')
            values['complete']=len(group)>=expected and values['coverage']>=99.9
            parks[park]['months'].append(values)
            days=defaultdict(dict); details=[]
            for ts,r in sorted(group.items()):
                local=ts.astimezone(SWEDEN_TZ); days[local.strftime('%Y-%m-%d')][ts]=r
                p=prices[zone].get(ts)
                details.append([local.isoformat(),r['effective_power_mw'],r['meter_mw'],
                    r['inverter_mw'],r['poa'],p['eur'] if p else None,r['energy_source']])
            daily=[]
            for day,records in sorted(days.items()):
                v=aggregate_park(records,prices[zone],capacity,ppa)
                daily.append({'date':day,**v})
            write_json(output_dir/'parks'/park/f'{ym}.json',{'daily':daily,'intervals':details})
    futures=[]
    for path in sorted(NASDAQ_DATA_DIR.glob('*.csv')):
        rows=read_rows(path); source(path,rows,'date'); groups=defaultdict(dict)
        for r in rows:
            price=number(r.get('daily_fix_eur'))
            if price is not None:
                observation=[r['date'],price,number(r.get('open_interest'))]
                previous=groups[r['contract']].get(r['date'])
                if previous is not None and previous != observation:
                    raise ValueError(f"Conflicting futures observations: {r['contract']} {r['date']}")
                groups[r['contract']][r['date']]=observation
        for symbol,by_date in sorted(groups.items()):
            period=contract_period(symbol)
            if not period: continue
            series=sorted(by_date.values()); market_name='SYS' if path.stem=='sys_baseload' else path.stem.split('_')[1].upper()
            futures.append({'symbol':symbol,'market':market_name,**period,'first':series[0][0],
                'last':series[-1][0],'points':len(series),'source_file':path.name})
            write_json(output_dir/'futures'/f'{symbol}.json',series)
    digest=hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest()[:16]
    result={'generated':datetime.now(UTC).isoformat(),'dataset_version':digest,
            'metric_version':METRIC_VERSION,'sources':sources,'parks':parks,
            'market':market,'futures':futures,
            'spot_end_adjusted_quarters':sum(v['end_adjusted'] for d in prices.values() for v in d.values()),
            'notes':['Nätleverans använder giltig grid-mätare, annars märkt inverterestimat.',
                'PR är preliminär och räknas på matchade energi-/POA-intervall. Under 95 % POA-täckning visas inget huvudvärde.',
                'Capture rate använder tidsviktat områdespris på samma prismatchade energiintervall. Vid baseload ≤ 1 EUR/MWh visas ingen kvot.',
                'Vissa höst-DST-rader har korrigerad sluttid där nästa observation belägger ett överlapp. Originalfilerna är oförändrade.',
                'PPA är en modell med dagens fasta andel/pris utan historiska avtalsperioder.',
                'Futures saknar handlad volym och verifierad enhet/källa per OI-observation.']}
    write_json(output_dir/'summary.json',result)
    return result


def build_intelligence_data(output_dir):
    """Publish a complete immutable snapshot, then atomically replace its index.

    A failed export leaves the previous summary and snapshots usable. Readers
    use the versioned data_path, so open analyses never mix two generations.
    """
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".building-", dir=root) as tmp:
        stage = Path(tmp)
        result = _build_intelligence_data(stage)
        result["data_path"] = "/data/snapshots/" + result["dataset_version"]
        write_json(stage/"summary.json", result)
        target = root/"snapshots"/result["dataset_version"]
        target.parent.mkdir(exist_ok=True)
        if not target.exists():
            stage.rename(target)
        index = root/".summary-next.json"
        write_json(index, result)
        index.replace(root/"summary.json")
        return result
