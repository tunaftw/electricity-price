from datetime import datetime, timezone
import pytest
from elpris.intelligence_data import (effective_observation, quarter_prices,
    expected_quarters, aggregate_park, latest_on_or_before, load_production)

def row(start,end,value='0.01'):
    return dict(time_start=start,time_end=end,EUR_per_kWh=value,SEK_per_kWh='0.1',EXR='10')

def test_meter_zero_is_not_missing():
    r=effective_observation({'power_mw':'0','active_power_mw':'1'},2)
    assert r['effective_power_mw']==0
    assert r['energy_source']=='meter'
    fallback=effective_observation({'power_mw':'','active_power_mw':'1'},2)
    assert fallback['effective_power_mw']==1
    assert fallback['energy_source']=='inverter_estimate'
    assert effective_observation({},2)['effective_power_mw'] is None

def test_bad_meter_can_use_valid_inverter_and_retains_original():
    r=effective_observation({'power_mw':'99','active_power_mw':'1'},2)
    assert r['effective_power_mw']==1 and r['meter_mw']==99
    assert effective_observation({'power_mw':'nan','active_power_mw':'inf'},2)['effective_power_mw'] is None

def test_autumn_source_end_overlap_is_normalized_by_next_observation():
    p=quarter_prices([row('2024-10-27T02:00:00+02:00','2024-10-27T03:00:00+01:00'),row('2024-10-27T02:00:00+01:00','2024-10-27T03:00:00+01:00','0.03')])
    assert len(p)==8
    assert sum(x['eur']*.25 for x in p.values())==40
    assert sum(x['end_adjusted'] for x in p.values())==4
    assert expected_quarters(2024,3)==31*96-4
    assert expected_quarters(2024,10)==31*96+4

def test_arbitrary_bad_durations_rejected():
    with pytest.raises(ValueError): quarter_prices([row('2024-06-01T00:00:00Z','2024-06-01T02:00:00Z')])

def test_conflicting_prices_rejected():
    with pytest.raises(ValueError):quarter_prices([row('2024-06-01T00:00:00Z','2024-06-01T01:00:00Z'),row('2024-06-01T00:00:00Z','2024-06-01T01:00:00Z','0.02')])

def test_pr_uses_identical_intervals_and_missing_price_is_not_zero():
    a=datetime(2024,6,1,12,tzinfo=timezone.utc);b=datetime(2024,6,1,13,tzinfo=timezone.utc)
    data={a:effective_observation({'power_mw':'1','irradiance_poa':'1000'},2),b:effective_observation({'power_mw':'1'},2)}
    result=aggregate_park(data,{a:{'eur':40,'fx':None}},1000,{'share_pct':70,'price_sek_mwh':500})
    assert result['pr']==100
    assert result['energy_mwh']==.5
    assert result['capture']==40 and result['price_coverage']==50
    assert result['ppa_model_eur'] is None

def test_asof_never_looks_forward():
    rows=[['2024-06-03',42],['2024-06-05',99]]
    assert latest_on_or_before(rows,'2024-06-04')==rows[0]
    assert latest_on_or_before(rows,'2024-06-02') is None
    assert latest_on_or_before(rows,'2024-06-20') is None

def test_stuck_estimates_are_missing_and_net_import_remains_signed():
    from datetime import timedelta
    begin=datetime(2024,6,1,0,tzinfo=timezone.utc)
    rows=[{'timestamp':(begin+timedelta(minutes=15*i)).isoformat(),'active_power_mw':'1'} for i in range(8)]
    data=load_production(rows,2)
    assert all(r['effective_power_mw'] is None and r['energy_source']=='stuck' for r in data.values())
    imported={begin:effective_observation({'power_mw':'-0.1'},2)}
    a=aggregate_park(imported,{begin:{'eur':50,'fx':10}},2000)
    assert a['energy_mwh']==-.025 and a['export_mwh']==0 and a['capture'] is None

def test_failed_export_preserves_index_and_success_uses_immutable_snapshot(tmp_path,monkeypatch):
    import elpris.intelligence_data as module
    def good(stage):
        module.write_json(stage/'futures'/'demo.json',[['2024-01-01',50]])
        return {'dataset_version':'abc','generated':'now'}
    monkeypatch.setattr(module,'_build_intelligence_data',good)
    result=module.build_intelligence_data(tmp_path)
    assert result['data_path']=='/data/snapshots/abc'
    assert (tmp_path/'snapshots/abc/futures/demo.json').is_file()
    before=(tmp_path/'summary.json').read_bytes()
    def broken(stage):
        module.write_json(stage/'futures'/'demo.json',[])
        raise ValueError('source conflict')
    monkeypatch.setattr(module,'_build_intelligence_data',broken)
    with pytest.raises(ValueError):module.build_intelligence_data(tmp_path)
    assert (tmp_path/'summary.json').read_bytes()==before
    assert not list(tmp_path.glob('.building-*'))
