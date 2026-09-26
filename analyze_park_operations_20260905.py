"""Reproducible operational screening; retains raw signal coverage and effective energy."""
import json
import calendar
from pathlib import Path
import pandas as pd
from elpris.config import PARK_CAPACITY_KWP, PARK_ZONES, PARKS_PROFILE_DIR, RAW_DIR
from elpris.operations_dashboard_data import load_park_15min
from elpris.park_config import get_budget

OUT = Path('Resultat/rapporter/park_analysis_20260905')
OUT.mkdir(parents=True, exist_ok=True)
frames = {}; quality = []; summaries = []
for park, cap in PARK_CAPACITY_KWP.items():
    raw = pd.read_csv(PARKS_PROFILE_DIR / f'{park}_{PARK_ZONES[park]}.csv')
    raw['ts'] = pd.to_datetime(raw.timestamp, utc=True)
    duplicates = int(raw.ts.duplicated().sum())
    raw = raw.drop_duplicates('ts').set_index('ts').sort_index()
    eff = pd.DataFrame(load_park_15min(park)).set_index('timestamp_utc')
    raw['effective_power_mw'] = eff.effective_power_mw
    raw['stuck'] = eff.get('_stuck_value', pd.Series(False, index=eff.index)).reindex(raw.index).fillna(False).astype(bool)
    raw['day'] = raw.index.tz_convert('Europe/Stockholm').strftime('%Y-%m-%d')
    raw['month'] = raw.day.str[:7]
    raw['energy'] = raw.effective_power_mw * .25
    raw['poa_energy'] = raw.irradiance_poa.clip(lower=0) * .25 / 1000
    raw['fallback'] = (raw.power_mw.fillna(0) <= 0) & (raw.active_power_mw.fillna(0) > 0) & ~raw.stuck
    raw['fallback_energy'] = raw.energy.where(raw.fallback, 0)
    frames[park] = raw
    quality.append(dict(park=park,first=raw.day.min(),last=raw.day.max(),duplicates=duplicates))

cutoff = min(x.day.max() for x in frames.values())
end = pd.Timestamp(cutoff)
periods = [('last3', str((end-pd.Timedelta(days=2)).date()), cutoff),
           ('last7',str((end-pd.Timedelta(days=6)).date()),cutoff),
           ('prev7',str((end-pd.Timedelta(days=13)).date()),str((end-pd.Timedelta(days=7)).date())),
           ('last28',str((end-pd.Timedelta(days=27)).date()),cutoff)]
for month in range(3,9):
    periods.append((f'2026-{month:02d}', f'2026-{month:02d}-01',f'2026-{month:02d}-{calendar.monthrange(2026,month)[1]}'))

daily=[]
for park, raw in frames.items():
    cap=PARK_CAPACITY_KWP[park]/1000
    for day,g in raw[raw.day>='2026-03-01'].groupby('day'):
        daylight=g.irradiance_poa>=200
        daily.append(dict(park=park,day=day,mwh=g.energy.sum(),yield_kwh_kwp=g.energy.sum()/cap,n=len(g),
            poa=g.poa_energy.sum(),poa_n=int(g.irradiance_poa.notna().sum()),
            pr=g.energy.sum()/cap/g.poa_energy.sum()*100 if g.poa_energy.sum()>0 else None,
            zero_sunny_hours=float(((g.effective_power_mw<cap*.01)&daylight).sum()*.25),
            fallback_mwh=g.fallback_energy.sum(),grid_mwh=g.power_mw.sum()*.25,
            inverter_mwh=g.active_power_mw.sum()*.25))
    for label,start,stop in periods:
        g=raw[(raw.day>=start)&(raw.day<=stop)]
        days=(pd.Timestamp(stop)-pd.Timestamp(start)).days+1
        expected=len(pd.date_range(start, pd.Timestamp(stop)+pd.Timedelta(days=1),freq='15min',tz='Europe/Stockholm',inclusive='left'))
        match=g.power_mw.notna()&g.active_power_mw.notna()&(g.active_power_mw>cap*.02)
        poa=g.poa_energy.sum()
        energy=g.energy.sum()
        budget=get_budget(park,2026,int(label[5:])) if label.startswith('2026') else {}
        sunny=g.irradiance_poa>=200
        row=dict(park=park,period=label,start=start,end=stop,n=len(g),expected=expected,coverage_pct=len(g)/expected*100,
            energy_mwh=energy,yield_kwh_kwp=energy/cap,budget_mwh=budget.get('energy_mwh'),
            budget_pct=energy/budget['energy_mwh']*100 if budget else None,
            poa_kwh_m2=poa,poa_coverage_pct=g.irradiance_poa.notna().sum()/expected*100,
            poa_budget=budget.get('irradiation_kwh_m2'),pr_pct=energy/cap/poa*100 if poa else None,
            budget_pr=budget.get('pr_pct'),grid_coverage_pct=g.power_mw.notna().sum()/expected*100,
            inverter_coverage_pct=g.active_power_mw.notna().sum()/expected*100,
            fallback_mwh=g.fallback_energy.sum(),stuck_hours=float(g.stuck.sum()*.25),
            sunny_zero_hours=float(((g.effective_power_mw<cap*.01)&sunny).sum()*.25),
            meter_gap_pct=(1-g.loc[match,'power_mw'].sum()/g.loc[match,'active_power_mw'].sum())*100 if match.any() else None,
            availability_coverage_pct=g.availability.notna().sum()/expected*100,
            grid_mwh=g.power_mw.sum()*.25)
        summaries.append(row)

pd.DataFrame(summaries).round(4).to_csv(OUT/'period_metrics.csv',index=False)
pd.DataFrame(daily).round(4).to_csv(OUT/'daily_metrics.csv',index=False)
pd.DataFrame(quality).to_csv(OUT/'source_coverage.csv',index=False)
print('CUTOFF',cutoff)
print(pd.DataFrame(quality).to_string(index=False))
s=pd.DataFrame(summaries)
for period in ['2026-06','2026-07','2026-08','last7','prev7']:
    print('\n',period)
    print(s[s.period==period][['park','energy_mwh','budget_pct','yield_kwh_kwp','coverage_pct','pr_pct','poa_coverage_pct','fallback_mwh','meter_gap_pct','sunny_zero_hours']].round(1).to_string(index=False))
