from datetime import date, datetime, timedelta, timezone

import pytest

from elpris.nordic_market_data import TZ, aggregate_history, build_futures, parse_settlements, period_bounds


def quarter_prices(start, end, price=10):
    a = int(datetime.combine(start, datetime.min.time(), TZ).timestamp())
    b = int(datetime.combine(end, datetime.min.time(), TZ).timestamp())
    return dict.fromkeys(range(a, b, 900), price)


def test_dst_and_leap_year_are_duration_weighted():
    prices = quarter_prices(date(2024, 1, 1), date(2025, 1, 1))
    rows = aggregate_history(prices, {}, {}, date(2025, 1, 1))
    year = next(r for r in rows if r['kind'] == 'year')
    march = next(r for r in rows if r['kind'] == 'month' and r['number'] == 3)
    october = next(r for r in rows if r['kind'] == 'month' and r['number'] == 10)
    assert year['hours'] == 8784
    assert march['hours'] == 743
    assert october['hours'] == 745
    assert year['coverage_pct'] == 100
    assert year['baseload'] == 10


def test_capture_weights_energy_and_keeps_missing_distinct_from_zero():
    prices = quarter_prices(date(2026, 1, 1), date(2026, 1, 2))
    times = sorted(prices)
    for t in times[48:]:
        prices[t] = 100
    production = {t: 0. if i < 48 else 2. for i, t in enumerate(times)}
    profile = {(1, 1, h): (0. if h < 12 else 2.) for h in range(24)}
    row = next(r for r in aggregate_history(prices, production, profile, date(2026, 1, 2)) if r['kind'] == 'year')
    assert row['baseload'] == 55
    assert row['capture_actual'] == 100
    assert row['capture_reference'] == 100
    assert row['partial'] is True
    assert row['actual_coverage_pct'] == 100
    missing = next(r for r in aggregate_history(prices, {}, profile, date(2026, 1, 2)) if r['kind'] == 'year')
    assert missing['capture_actual'] is None
    assert missing['actual_coverage_pct'] == 0


def test_insufficient_coverage_is_not_published_as_period_average():
    prices = quarter_prices(date(2026, 1, 1), date(2026, 1, 2))
    sparse = dict(list(prices.items())[:60])
    row = next(r for r in aggregate_history(sparse, sparse, {}, date(2026, 1, 2)) if r['kind'] == 'year')
    assert row['baseload'] is None
    assert row['capture_actual'] is None
    assert row['coverage_pct'] == 62.5


@pytest.mark.parametrize('kind,label,expected', [('year','2027','2027'), ('quarter','Q4 2026','2026-Q4'), ('month','Oct 2026','2026-10')])
def test_parse_dated_settlement_with_negative_and_zero_prices(kind, label, expected):
    text = '<h2>Prices - 18 September 2026</h2><table><tr>' + ''.join('<td>'+v+'</td>' for v in [label,'0','0','0','0','N/A','-2.50','0','1,234']) + '</tr></table>'
    rows = parse_settlements(text, kind, '2026-09-18')
    assert rows[0]['id'] == expected
    assert rows[0]['price'] == -2.5
    assert rows[0]['volume'] == 0
    assert rows[0]['open_interest'] == 1234
    with pytest.raises(ValueError):
        parse_settlements(text, kind, '2026-09-17')


def test_system_and_epad_require_same_settlement_date():
    row = {'id':'2027','kind':'year','year':2027,'number':1,'label':'2027','start':'2027-01-01','end':'2028-01-01','settlement_date':'2026-09-18','price':50}
    sys = dict(row, zone='SYS')
    epad = dict(row, zone='SE1', price=0)
    old = dict(row, zone='SE2', price=-10, settlement_date='2026-09-17')
    result = build_futures({'rows':[sys,epad,old]})[0]
    assert result['areas']['SE1']['price'] == 50
    assert result['areas']['SE2']['price'] is None
    assert result['areas']['DK1']['price'] is None


def test_period_end_rollover():
    assert period_bounds('quarter',2026,4)==(date(2026,10,1),date(2027,1,1))
    assert period_bounds('month',2026,12)==(date(2026,12,1),date(2027,1,1))
