"""Nordic area futures and auditable, duration-weighted historical prices.

All joins use UTC quarter-hours; reporting periods use Europe/Stockholm.
Missing prices/production are never replaced by zero or another bidding zone.
"""
from __future__ import annotations

import calendar
import csv
import html
import json
import math
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from .config import PROJECT_ROOT, RESULTAT_DIR

ZONES = ['SE1', 'SE2', 'SE3', 'SE4', 'DK1', 'DK2']
PRODUCTS = {'SYS': 'NS', 'SE1': 'LL', 'SE2': 'SU', 'SE3': 'ST', 'SE4': 'MA', 'DK1': 'AR', 'DK2': 'CP'}
CACHE = RESULTAT_DIR / 'marknadsdata' / 'nordic_market'
TZ = ZoneInfo('Europe/Stockholm')
UTC = timezone.utc
FIRST_YEAR = 2024
EURONEXT = 'https://live.euronext.com/en'


def _save(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    tmp.replace(path)


def _text(value):
    return html.unescape(re.sub(r'<[^>]+>', '', value)).replace('\xa0', ' ').strip()


def _number(value):
    try:
        n = float(str(value).replace(',', ''))
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None


def period_bounds(kind: str, year: int, number: int = 1):
    month = 1 if kind == 'year' else ((number - 1) * 3 + 1 if kind == 'quarter' else number)
    span = {'year': 12, 'quarter': 3, 'month': 1}[kind]
    end_month = month + span
    return date(year, month, 1), date(year + (end_month - 1) // 12, (end_month - 1) % 12 + 1, 1)


def period_id(kind, year, number=1):
    return str(year) if kind == 'year' else (f'{year}-Q{number}' if kind == 'quarter' else f'{year}-{number:02d}')


def parse_settlements(source: str, kind: str, settlement_date: str):
    """Parse the dated settlement table, not the undated intraday snapshot."""
    heading = datetime.fromisoformat(settlement_date).strftime('%d %B %Y').lstrip('0')
    if heading not in _text(source):
        raise ValueError('Euronext response does not contain the requested settlement date')
    result = []
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>', source, re.S):
        cells = [_text(c) for c in re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)]
        if len(cells) != 9 or cells[0] == 'Total':
            continue
        label = cells[0]
        if kind == 'year':
            match = re.fullmatch(r'(20\d\d)', label)
            if not match:
                continue
            year, number = int(match[1]), 1
        elif kind == 'quarter':
            match = re.fullmatch(r'Q([1-4])\s+(20\d\d)', label)
            if not match:
                continue
            number, year = int(match[1]), int(match[2])
        else:
            parsed = None
            for fmt in ('%b %Y', '%B %Y'):
                try:
                    parsed = datetime.strptime(label, fmt)
                    break
                except ValueError:
                    pass
            if parsed is None:
                continue
            year, number = parsed.year, parsed.month
        start, end = period_bounds(kind, year, number)
        result.append({'id': period_id(kind, year, number), 'kind': kind, 'year': year,
                       'number': number, 'label': label, 'start': start.isoformat(),
                       'end': end.isoformat(), 'settlement_date': settlement_date,
                       'price': _number(cells[6]), 'volume': _number(cells[7]),
                       'open_interest': _number(cells[8])})
    if not result:
        raise ValueError(f'No {kind} settlements parsed')
    return result


def download_futures(cache=CACHE, today=None):
    today = today or datetime.now(TZ).date()
    session = requests.Session()
    url = f'{EURONEXT}/product/commodities-futures/NSBY-DAMS/settlement-prices'
    page = session.get(url, timeout=45)
    page.raise_for_status()
    select = re.search(r'<select[^>]*id="tradingFilter".*?</select>', page.text, re.S)
    dates = [datetime.strptime(v, '%m-%d-%Y').date() for v in re.findall(r'value="([\d-]+)"', select[0])]
    settlement = max(d for d in dates if d < today)

    def fetch(item):
        zone, prefix, kind, suffix = item
        code = prefix + 'B' + suffix
        source_url = f'{EURONEXT}/product/commodities-futures/{code}-DAMS/settlement-prices'
        # All valid maturity end dates; the exchange returns only listed series.
        data = [('mt', suffix), ('td', settlement.strftime('%m-%d-%Y'))]
        for year in range(today.year, today.year + 11):
            for month in ([12] if kind == 'year' else [3, 6, 9, 12] if kind == 'quarter' else range(1, 13)):
                data.append(('md[]', f'{month:02d}-{calendar.monthrange(year, month)[1]:02d}-{year}'))
        last_error = None
        for attempt in range(3):
            try:
                response = requests.post(f'{EURONEXT}/ajax/getTabPrices/{code}-DAMS/futures', data=data, timeout=45)
                response.raise_for_status()
                rows = parse_settlements(response.text, kind, settlement.isoformat())
                (cache / f'{code}_{settlement}.html').write_text(response.text, encoding='utf-8')
                for row in rows:
                    row.update(zone=zone, code=code, source_url=source_url)
                return rows
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                time.sleep(attempt + 1)
        raise RuntimeError(f'{code}: {last_error}')

    cache.mkdir(parents=True, exist_ok=True)
    items = [(z, p, k, s) for z, p in PRODUCTS.items() for k, s in [('year', 'Y'), ('quarter', 'Q'), ('month', 'M')]]
    rows = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        for part in pool.map(fetch, items):
            rows.extend(part)
    snapshot = {'settlement_date': settlement.isoformat(), 'retrieved_at': datetime.now(UTC).isoformat(), 'rows': rows}
    _save(cache / f'futures_{settlement}.json', snapshot)
    _save(cache / 'futures_latest.json', snapshot)
    return snapshot


def fetch_energinet(dataset, start, end, cache=CACHE):
    path = cache / f'{dataset}_{start}_{end}.json'
    if path.exists():
        return
    params = {'start': start, 'end': end, 'filter': json.dumps({'PriceArea': ['DK1', 'DK2', 'SE3', 'SE4']}), 'limit': 0}
    if dataset == 'ProductionConsumptionSettlement':
        params['filter'] = json.dumps({'PriceArea': ['DK1', 'DK2']})
        params['columns'] = 'HourUTC,PriceArea,SolarPowerLt10kW_MWh,SolarPowerGe10Lt40kW_MWh,SolarPowerGe40kW_MWh'
    response = requests.get('https://api.energidataservice.dk/dataset/' + dataset, params=params, timeout=120)
    response.raise_for_status()
    data = response.json()
    if not data.get('records'):
        raise ValueError(f'Empty Energinet dataset: {dataset}')
    _save(path, {'url': response.url, 'data': data, 'retrieved_at': datetime.now(UTC).isoformat()})


def refresh_inputs(cache=CACHE, today=None):
    today = today or datetime.now(TZ).date()
    cache.mkdir(parents=True, exist_ok=True)
    # Reuse the already verified source extracts when available.
    prior = RESULTAT_DIR / 'rapporter' / 'underlag_terminer_20260921'
    for name in ['Elspotprices_2024-01-01_2025-10-01.json', 'DayAheadPrices_2025-10-01_2026-09-21.json']:
        if (prior / name).exists() and not (cache / name).exists():
            _save(cache / name, json.loads((prior / name).read_text(encoding='utf-8')))
    fetch_energinet('Elspotprices', '2024-01-01', '2025-10-01', cache)
    fetch_energinet('DayAheadPrices', '2025-10-01', today.isoformat(), cache)
    # Settlement production is revised; a new dated extract is fetched each run date.
    fetch_energinet('ProductionConsumptionSettlement', '2024-01-01', today.isoformat(), cache)
    for zone in ['SE1', 'SE2']:
        existing = load_spot(zone, cache)
        last = datetime.fromtimestamp(max(existing), UTC).astimezone(TZ).date() if existing else date(FIRST_YEAR, 1, 1)
        day = last  # Refresh the last partial day as well.
        while day < today:
            path = cache / 'spot' / zone / f'{day}.json'
            if not path.exists():
                response = requests.get(f'https://www.elprisetjustnu.se/api/v1/prices/{day.year}/{day:%m-%d}_{zone}.json', timeout=40)
                response.raise_for_status()
                rows = response.json()
                if not rows:
                    raise ValueError(f'Empty price data for {zone} {day}')
                _save(path, rows)
                time.sleep(0.15)
            day += timedelta(days=1)
    return download_futures(cache, today)


def stamp(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp())


def _expand(target, timestamp, value, minutes):
    if value is None or not math.isfinite(value):
        return
    for offset in range(0, int(minutes) * 60, 900):
        target[timestamp + offset] = value


def load_spot(zone, cache=CACHE):
    points = {}
    folder = RESULTAT_DIR / 'marknadsdata' / 'spotpriser' / zone
    files = sorted(folder.glob('*.csv')) if folder.exists() else []
    for path in files:
        if not path.stem.isdigit() or int(path.stem) < FIRST_YEAR:
            continue
        with path.open(encoding='utf-8') as f:
            for row in csv.DictReader(f):
                # Market resolution, independent of malformed legacy time_end at DST.
                start = row['time_start']
                resolution = 15 if start[:10] >= '2025-10-01' else 60
                value = _number(row.get('EUR_per_kWh'))
                _expand(points, stamp(start), value * 1000 if value is not None else None, resolution)
    if zone in ('DK1', 'DK2', 'SE3', 'SE4'):
        for pattern, key, price, duration in [('Elspotprices_*.json', 'HourUTC', 'SpotPriceEUR', 60), ('DayAheadPrices_*.json', 'TimeUTC', 'DayAheadPriceEUR', 15)]:
            for path in sorted(cache.glob(pattern)):
                for row in json.loads(path.read_text(encoding='utf-8'))['data']['records']:
                    if row['PriceArea'] == zone:
                        _expand(points, stamp(row[key]), _number(row[price]), duration)
    for path in sorted((cache / 'spot' / zone).glob('*.json')):
        for row in json.loads(path.read_text(encoding='utf-8')):
            duration = 15 if row['time_start'][:10] >= '2025-10-01' else 60
            _expand(points, stamp(row['time_start']), float(row['EUR_per_kWh']) * 1000, duration)
    return points


def load_production(zone, cache=CACHE):
    points = {}
    if zone.startswith('SE'):
        for path in sorted((RESULTAT_DIR / 'marknadsdata' / 'entsoe' / 'generation' / zone).glob('solar_*.csv')):
            if int(path.stem[-4:]) < FIRST_YEAR - 1:
                continue
            with path.open(encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    value = _number(row.get('generation_mw'))
                    if value is not None and value >= 0:
                        _expand(points, stamp(row['time_start']), value, int(row['resolution_minutes']))
    else:
        for path in sorted(cache.glob('ProductionConsumptionSettlement*.json')):
            for row in json.loads(path.read_text(encoding='utf-8'))['data']['records']:
                if row['PriceArea'] != zone:
                    continue
                values = [_number(row.get(k)) for k in ('SolarPowerLt10kW_MWh', 'SolarPowerGe10Lt40kW_MWh', 'SolarPowerGe40kW_MWh')]
                if all(v is not None and v >= 0 for v in values):
                    # Hourly MWh / 1 h = average MW; excludes self-consumption.
                    _expand(points, stamp(row['HourUTC']), sum(values), 60)
    return points


def aggregate_history(prices, production, profile, cutoff, first_year=FIRST_YEAR):
    buckets = defaultdict(lambda: {'count': 0, 'sum': 0., 'ref_energy': 0., 'ref_revenue': 0., 'ref_count': 0,
                                    'actual_count': 0, 'actual_energy': 0., 'actual_revenue': 0., 'actual_spot': 0., 'actual_last': None})
    cutoff_ts = int(datetime.combine(cutoff, datetime.min.time(), TZ).timestamp())
    for timestamp, price in sorted(prices.items()):
        local = datetime.fromtimestamp(timestamp, UTC).astimezone(TZ)
        if local.year < first_year or timestamp >= cutoff_ts:
            continue
        # PVsyst TMY uses local standard time (CET), not a DST-shifting clock.
        standard = datetime.fromtimestamp(timestamp, timezone(timedelta(hours=1)))
        day = 28 if standard.month == 2 and standard.day == 29 else standard.day
        weight = profile.get((standard.month, day, standard.hour))
        mw = production.get(timestamp)
        for kind, number in [('year', 1), ('quarter', (local.month - 1) // 3 + 1), ('month', local.month)]:
            b = buckets[(kind, local.year, number)]
            b['count'] += 1
            b['sum'] += price
            if weight is not None:
                b['ref_count'] += 1
                b['ref_energy'] += weight * .25
                b['ref_revenue'] += weight * .25 * price
            if mw is not None and mw >= 0:
                b['actual_count'] += 1
                b['actual_energy'] += mw * .25
                b['actual_revenue'] += mw * .25 * price
                b['actual_spot'] += price
                b['actual_last'] = local.date().isoformat()
    result = []
    for (kind, year, number), b in sorted(buckets.items()):
        start, end = period_bounds(kind, year, number)
        effective_end = min(end, cutoff)
        expected = (datetime.combine(effective_end, datetime.min.time(), TZ).timestamp() - datetime.combine(start, datetime.min.time(), TZ).timestamp()) / 900
        coverage = b['count'] / expected if expected else 0
        actual_coverage = b['actual_count'] / expected if expected else 0
        base = b['sum'] / b['count']
        ref = b['ref_revenue'] / b['ref_energy'] if b['ref_energy'] > 0 and b['ref_count'] == b['count'] else None
        actual = b['actual_revenue'] / b['actual_energy'] if b['actual_energy'] > 0 else None
        matched_base = b['actual_spot'] / b['actual_count'] if b['actual_count'] else None
        # Sparse national reporting must not appear as a representative period price.
        if actual_coverage < .90:
            actual = None
        result.append({'id': period_id(kind, year, number), 'kind': kind, 'year': year, 'number': number,
                       'start': start.isoformat(), 'end': effective_end.isoformat(), 'period_end': end.isoformat(),
                       'partial': effective_end < end, 'coverage_pct': round(coverage * 100, 2),
                       'baseload': round(base, 8) if coverage >= .99 else None,
                       'capture_reference': round(ref, 8) if ref is not None and coverage >= .99 else None,
                       'capture_actual': round(actual, 8) if actual is not None else None,
                       'actual_coverage_pct': round(actual_coverage * 100, 2), 'actual_through': b['actual_last'],
                       'actual_matched_baseload': round(matched_base, 4) if matched_base is not None else None,
                       'hours': b['count'] / 4})
    return result


def build_futures(snapshot):
    groups = {}
    for row in snapshot.get('rows', []):
        key = row['id']
        groups.setdefault(key, {k: row[k] for k in ('id', 'kind', 'year', 'number', 'label', 'start', 'end')})
        groups[key].setdefault('components', {})[row['zone']] = row
    result = []
    for contract in groups.values():
        components = contract['components']
        system = components.get('SYS')
        contract['areas'] = {}
        for zone in ZONES:
            epad = components.get(zone)
            valid = (system is not None and epad is not None and system['price'] is not None and epad['price'] is not None
                     and system['settlement_date'] == epad['settlement_date'])
            contract['areas'][zone] = {'price': round(system['price'] + epad['price'], 2) if valid else None,
                                       'epad': epad['price'] if epad else None,
                                       'volume': epad.get('volume') if epad else None,
                                       'open_interest': epad.get('open_interest') if epad else None,
                                       'status': 'priced' if valid else 'missing'}
        contract['system'] = system['price'] if system else None
        result.append(contract)
    return sorted(result, key=lambda r: (r['start'], r['kind']))


def build_nordic_market_data(cache=CACHE, cutoff=None):
    cutoff = cutoff or datetime.now(TZ).date()
    path = cache / 'futures_latest.json'
    snapshot = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    profile = {}
    with (RESULTAT_DIR / 'profiler' / 'beraknade' / 'south_lundby.csv').open(encoding='utf-8') as f:
        for row in csv.DictReader(f):
            profile[(int(row['month']), int(row['day']), int(row['hour']))] = float(row['power_mw'])
    history, production_through = {}, {}
    for zone in ZONES:
        prices, production = load_spot(zone, cache), load_production(zone, cache)
        history[zone] = aggregate_history(prices, production, profile, cutoff)
        production_through[zone] = datetime.fromtimestamp(max(production), UTC).astimezone(TZ).date().isoformat() if production else None
    return {'generated': datetime.now(TZ).isoformat(timespec='seconds'), 'through': (cutoff - timedelta(days=1)).isoformat(),
            'settlement_date': snapshot.get('settlement_date'), 'zones': ZONES,
            'futures': build_futures(snapshot), 'history': history, 'production_through': production_through,
            'reference_profile': 'PVsyst Lundby, sydvänd TMY · samma profil i alla områden · fast CET',
            'sources': {'futures': f'{EURONEXT}/products/commodities/power-derivatives/contracts-list',
                        'spot_dk': 'https://www.energidataservice.dk/tso-electricity/DayAheadPrices',
                        'spot_se': 'https://www.elprisetjustnu.se/elpris-api',
                        'solar_se': 'https://transparency.entsoe.eu/generation/r2/actualGenerationPerProductionType/show',
                        'solar_dk': 'https://www.energidataservice.dk/tso-electricity/ProductionConsumptionSettlement'}}
