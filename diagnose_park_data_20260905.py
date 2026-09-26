import pandas as pd
from pathlib import Path
from elpris.config import PARK_CAPACITY_KWP, PARK_ZONES, PARKS_PROFILE_DIR, RAW_DIR
OUT=Path('Resultat/rapporter/park_analysis_20260905')
rows=[]; price_rows=[]; signals=[]
for park,cap in PARK_CAPACITY_KWP.items():
 d=pd.read_csv(PARKS_PROFILE_DIR/f'{park}_{PARK_ZONES[park]}.csv')
 d['ts']=pd.to_datetime(d.timestamp,utc=True);d=d[d.timestamp>='2026-03-01'].copy();d['day']=d.timestamp.str[:10];d['month']=d.day.str[:7]
 # Stale is a data-quality flag, never evidence of plant downtime.
 groups=d.groupby('day')
 stale=groups.active_power_mw.nunique().le(1)&groups.active_power_mw.max().gt(.001)
 for label,g in d.groupby('month'):
  night=pd.to_datetime(g.ts).dt.tz_convert('Europe/Stockholm').dt.hour.isin([0,1,2,3])
  rows.append(dict(park=park,month=label,grid_coverage=g.power_mw.notna().mean()*100,ap_coverage=g.active_power_mw.notna().mean()*100,
    grid_mwh=g.power_mw.sum()*.25,ap_mwh=g.active_power_mw.sum()*.25,
    poa_over1500_hours=(g.irradiance_poa>1500).sum()*.25,night_poa_median=g.loc[night,'irradiance_poa'].median(),
    night_ap_mwh=g.loc[night,'active_power_mw'].sum()*.25,availability_n=g.availability.count(),
    stale_days=int(stale[stale.index.str.startswith(label)].sum())))
 if park in ['horby','fjallskar','bjorke','agerum']:
  print('\nSIGNALS',park)
  for col in ['power_mw','active_power_mw','irradiance_poa']:
   valid=d[d[col].notna()]; print(col,'last',valid.timestamp.iloc[-1], 'max',valid[col].max())
  print('stale days',list(stale[stale].index))
  if park=='bjorke':
   print(groups.agg(grid_n=('power_mw','count'),ap_n=('active_power_mw','nunique'),peak=('power_mw','max')).tail(25).to_string())
 # Compare spot only where raw grid is observed. No settlement/PPA claim.
 price=pd.read_csv(RAW_DIR/PARK_ZONES[park]/'2026.csv');price['ts']=pd.to_datetime(price.time_start,utc=True)
 merged=d.merge(price[['ts','EUR_per_kWh']],on='ts',how='left',validate='one_to_one')
 for month,g in merged.groupby('month'):
  valid=g.power_mw.notna()&g.EUR_per_kWh.notna();neg=valid&(g.EUR_per_kWh<0)&(g.power_mw>0)
  price_rows.append(dict(park=park,month=month,matched_grid_intervals=int(valid.sum()),n=len(g),
    negative_export_mwh=g.loc[neg,'power_mw'].sum()*.25,negative_spot_eur=(g.loc[neg,'power_mw']*g.loc[neg,'EUR_per_kWh']*250).sum(),
    positive_export_mwh=g.loc[valid,'power_mw'].clip(lower=0).sum()*.25,
    spot_value_eur=(g.loc[valid,'power_mw'].clip(lower=0)*g.loc[valid,'EUR_per_kWh']*250).sum()))
pd.DataFrame(rows).round(3).to_csv(OUT/'signal_quality.csv',index=False)
pd.DataFrame(price_rows).round(3).to_csv(OUT/'observed_grid_spot.csv',index=False)
print('\nQUALITY');print(pd.DataFrame(rows).query("month >= '2026-07'").round(1).to_string(index=False))
print('\nSPOT');print(pd.DataFrame(price_rows).query("month == '2026-08'").round(1).to_string(index=False))
