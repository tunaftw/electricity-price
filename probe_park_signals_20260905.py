import json
from datetime import date
from pathlib import Path
from elpris.bazefield import fetch_timeseries
from elpris.inverter_registry import get_inverters
out=Path('Resultat/rapporter/park_analysis_20260905')
results=[]
for park in ['fjallskar','bjorke','agerum']:
    invs=get_inverters(park)
    for inv in [invs[0],invs[len(invs)//2],invs[-1]]:
        raw=fetch_timeseries(inv['id'],['ActivePower','TotalEnergyProduced.1h'],date(2026,9,1),date(2026,9,5))
        results.append(dict(park=park,inverter=inv,raw=raw))
        vals=[r['value'] for r in raw.get('ActivePower',[])]
        print(park,inv['name'],'n',len(vals),'unique',len(set(vals)),'max',max(vals) if vals else None,flush=True)
        (out/'inverter_signal_probes.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
