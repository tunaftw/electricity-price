from pathlib import Path
import pandas as pd
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from elpris.config import PARKS_PROFILE_DIR, PARK_ZONES
OUT=Path('Resultat/rapporter/park_analysis_20260905')
days=pd.date_range('2026-06-01','2026-09-04').strftime('%Y-%m-%d')
matrix=[];align=[]
names=['Hörby','Fjällskär','Björke','Agerum','Hova','Skäkelbacken','Stenstorp','Tången']
for park,zone in PARK_ZONES.items():
 d=pd.read_csv(PARKS_PROFILE_DIR/f'{park}_{zone}.csv')
 d['ts']=pd.to_datetime(d.timestamp,utc=True); d['day']=d.timestamp.str[:10]
 coverage=d.groupby('day').power_mw.count()/96*100
 matrix.append(coverage.reindex(days).to_numpy())
 g=d[(d.day>='2026-08-01')&(d.day<='2026-08-31')].set_index('ts').asfreq('15min')
 v=g.power_mw.clip(lower=0);irr=g.irradiance_poa.where(g.irradiance_poa.between(0,1300))
 cs={lag:v.corr(irr.shift(lag)) for lag in range(-16,17)};best=max(cs,key=cs.get)
 align.append(dict(park=park,period='2026-08',poa_shift_hours=best/4,correlation_original=cs[0],correlation_shifted=cs[best]))
pd.DataFrame(align).round(4).to_csv(OUT/'poa_alignment_screen.csv',index=False)
img=Image.new('RGB',(1480,650),'#fafaf7');draw=ImageDraw.Draw(img)
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22)
small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
title=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',30)
draw.text((35,25),'Nätmätarens datatäckning',font=title,fill='#172f38')
draw.text((35,68),'1 juni–4 september 2026 · andel kvartsvärden med registrerad nätmätning',font=font,fill='#42545c')
left=190;top=125;cw=13;rh=44
for i,row in enumerate(matrix):
 draw.text((25,top+i*rh+8),names[i],font=font,fill='#172f38')
 for j,v in enumerate(row):
  t=max(0,min(1,float(v)/100)) if not np.isnan(v) else 0
  lo=(191,70,61);hi=(40,139,111)
  color=tuple(round(lo[k]*(1-t)+hi[k]*t) for k in range(3))
  draw.rectangle((left+j*cw,top+i*rh,left+(j+1)*cw-1,top+(i+1)*rh-4),fill=color)
for j,label in [(0,'1 juni'),(30,'1 juli'),(61,'1 augusti'),(92,'1 sep')]:
 draw.text((left+j*cw-5,top+8*rh+8),label,font=small,fill='#172f38')
draw.rectangle((35,545,60,570),fill=(191,70,61));draw.text((70,545),'0 %',font=font,fill='#172f38')
draw.rectangle((155,545,180,570),fill=(40,139,111));draw.text((190,545),'100 %',font=font,fill='#172f38')
draw.text((35,590),'Täckning visar om ett värde finns, inte om det är korrekt. Rött betyder saknad data, inte bevisat driftstopp.',font=small,fill='#42545c')
img.save(OUT/'meter_coverage.png')
