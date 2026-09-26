#!/usr/bin/env python3
"""Bygg fristående HTML som förklarar juni-budgetgapet (orsaksnedbrytning)."""
import io
import json
import os
import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

g = json.load(open(sys.argv[1], encoding="utf-8"))
out = sys.argv[2]
P = g["portfolio"]
data_js = json.dumps(g, ensure_ascii=False)

html = f"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Varför juni ligger efter budget</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
:root {{
  --font-body:'Sora',system-ui,sans-serif; --font-mono:'IBM Plex Mono',Consolas,monospace;
  --bg:#0c1014; --surface:#141a21; --surface-elevated:#1a2129;
  --border:rgba(255,255,255,0.07); --border-bright:rgba(255,255,255,0.14);
  --text:#e8eef2; --text-dim:#8a98a5;
  --sun:#f4b942; --sun-dim:rgba(244,185,66,.14);
  --perf:#34d399; --perf-dim:rgba(52,211,153,.14);
  --avail:#60a5fa; --avail-dim:rgba(96,165,250,.14);
  --budget:#6b7785; --actual:#f4b942; --red:#f87171;
}}
@media (prefers-color-scheme: light) {{
  :root {{ --bg:#f6f4ee; --surface:#fff; --surface-elevated:#fff;
    --border:rgba(0,0,0,.08); --border-bright:rgba(0,0,0,.16); --text:#1b2127; --text-dim:#5d6b78;
    --sun:#c8861a; --sun-dim:rgba(200,134,26,.12); --perf:#0f9d6b; --perf-dim:rgba(15,157,107,.12);
    --avail:#2563eb; --avail-dim:rgba(37,99,235,.1); --budget:#8a96a3; --actual:#c8861a; --red:#d4493f; }}
}}
*{{box-sizing:border-box}}
body{{margin:0;padding:40px 28px 64px;color:var(--text);font-family:var(--font-body);
  background:var(--bg);background-image:radial-gradient(ellipse at 50% -10%,var(--sun-dim) 0%,transparent 55%);
  overflow-wrap:break-word}}
.wrap{{max-width:1080px;margin:0 auto}}
.eyebrow{{font-family:var(--font-mono);font-size:12px;letter-spacing:2px;text-transform:uppercase;color:var(--sun);margin:0 0 8px}}
h1{{font-size:clamp(26px,3.6vw,38px);font-weight:700;letter-spacing:-1px;margin:0 0 10px;max-width:22ch}}
.sub{{color:var(--text-dim);font-size:15px;max-width:75ch;line-height:1.6}}
.sub b{{color:var(--text);font-weight:600}}
.verdict{{display:flex;flex-wrap:wrap;gap:14px;margin:26px 0}}
.vcard{{flex:1;min-width:220px;background:var(--surface-elevated);border:1px solid var(--border);
  border-radius:14px;padding:20px 22px;position:relative;overflow:hidden;
  animation:fadeScale .4s ease-out both;animation-delay:calc(var(--i,0)*.08s)}}
.vcard::before{{content:'';position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--c,var(--sun))}}
.vcard .lab{{font-family:var(--font-mono);font-size:10.5px;font-weight:600;letter-spacing:1.4px;text-transform:uppercase;color:var(--text-dim);margin-bottom:9px}}
.vcard .val{{font-size:30px;font-weight:700;letter-spacing:-1px;line-height:1;font-variant-numeric:tabular-nums}}
.vcard .val small{{font-size:14px;color:var(--text-dim);font-weight:500}}
.vcard .desc{{font-size:12.5px;color:var(--text-dim);margin-top:9px;line-height:1.5}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:8px 0 18px}}
@media(max-width:860px){{.grid2{{grid-template-columns:1fr}}}}
.card{{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:20px 22px 16px}}
.card h2{{font-size:15px;font-weight:600;margin:0 0 2px}}
.card .hint{{font-family:var(--font-mono);font-size:11px;color:var(--text-dim);margin:0 0 14px}}
canvas{{max-height:330px}}
.legend{{display:flex;gap:18px;flex-wrap:wrap;font-family:var(--font-mono);font-size:11.5px;color:var(--text-dim);margin-top:10px}}
.legend span{{display:inline-flex;align-items:center;gap:6px}}
.dot{{width:11px;height:11px;border-radius:3px;display:inline-block}}
.note{{color:var(--text-dim);font-size:12.5px;line-height:1.65;margin-top:22px;border-top:1px solid var(--border);padding-top:16px}}
.note b{{color:var(--text)}}
.price-row{{display:flex;gap:14px;flex-wrap:wrap;margin-top:4px}}
@keyframes fadeScale{{from{{opacity:0;transform:scale(.96)}}to{{opacity:1;transform:scale(1)}}}}
@media(prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
</style>
</head>
<body>
<div class="wrap">
<p class="eyebrow">Orsaksanalys · juni 2026 MTD (1–25 juni)</p>
<h1>Vad driver budgetgapet?</h1>
<p class="sub">Budgeten är satt i <b>MWh (PVsyst TMY)</b>, så gapet är en <b>produktionsmiss</b> — inte en prismiss.
Gapet på <b>{P['gap_mwh']:,.0f} MWh</b> (vi ligger på {P['vs_budget_pct']:.0f}% av budget) bryts ned i tre orsaker.
Slutsatsen är entydig: <b>solen</b>.</p>

<div class="verdict">
  <div class="vcard" style="--i:0;--c:var(--sun)">
    <div class="lab">☀ Instrålning (solen)</div>
    <div class="val">{P['irr_pct_of_gap']:.0f}<small> % av gapet</small></div>
    <div class="desc">−{P['irr_shortfall_mwh']:,.0f} MWh. Instrålningen ligger ~13–18 % under TMY-normalen i alla parker.</div>
  </div>
  <div class="vcard" style="--i:1;--c:var(--avail)">
    <div class="lab">⚙ Tillgänglighet</div>
    <div class="val">{P['avail_pct_of_gap']:.0f}<small> % av gapet</small></div>
    <div class="desc">{P['avail_loss_mwh']:,.0f} MWh. Inga driftstopp av betydelse — anläggningarna har varit uppe.</div>
  </div>
  <div class="vcard" style="--i:2;--c:var(--perf)">
    <div class="lab">↑ Prestanda (PR)</div>
    <div class="val">{P['perf_pct_of_gap']:+.0f}<small> % av gapet</small></div>
    <div class="desc">+{abs(P['unexplained_mwh']):,.0f} MWh <b>tillbaka</b>. Parkerna omvandlade solen bättre än budget-PR — mildrar gapet.</div>
  </div>
</div>

<div class="grid2">
  <div class="card">
    <h2>Vattenfall: budget → faktisk</h2>
    <p class="hint">MWh · vad som tar oss från pro-ratad budget ned till faktisk</p>
    <canvas id="wf"></canvas>
  </div>
  <div class="card">
    <h2>Per park — gapets orsaker</h2>
    <p class="hint">MWh · solen dominerar i alla parker</p>
    <canvas id="parks" height="150"></canvas>
    <div class="legend">
      <span><i class="dot" style="background:var(--sun)"></i>Instrålning</span>
      <span><i class="dot" style="background:var(--avail)"></i>Tillgänglighet</span>
      <span><i class="dot" style="background:var(--perf)"></i>Prestanda (+ = hjälper)</span>
    </div>
  </div>
</div>

<p class="note">
<b>Om elpriserna.</b> Priser påverkar <b>inte</b> MWh-budgetgapet — budgeten är ren volym. På intäktssidan finns ingen prisbudget i modellen,
men i absoluta tal är junipriserna höga: baseload ligger runt <b>85–95 €/MWh</b> medan portföljens capture landar på <b>~58–66 €/MWh</b>.
Den negativa capture-premien (−11 % till −31 %) är <b>strukturell för sol</b> — produktionen ligger i soltunga middagstimmar då priset pressas — och är väntad, inte en avvikelse.
Sammanfattat: vi ligger efter på grund av <b>mindre sol än ett normalår</b>, inte sämre drift och inte priser.
<br><br>
<b>Ett undantag att hålla koll på:</b> Hörby är den enda parken med ett genuint prestandaproblem — PR 79 % mot budget 85 %, vilket bidrar med ~137 MWh av Hörbys gap utöver solen.
Övriga parker presterar i nivå med eller över budget-PR (Hova 102 %, Skäkelbacken 92 %).
</p>
</div>

<script>
const G={data_js};
const isDark=matchMedia('(prefers-color-scheme: dark)').matches;
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const grid=isDark?'rgba(255,255,255,.05)':'rgba(0,0,0,.06)';
const fam=css('--font-mono')||'monospace';
Chart.defaults.color=css('--text-dim');Chart.defaults.font.family=fam;Chart.defaults.font.size=11;
const C={{sun:css('--sun'),perf:css('--perf'),avail:css('--avail'),budget:css('--budget'),actual:css('--actual')}};
const fmt=v=>Math.round(v).toLocaleString('sv-SE');
const P=G.portfolio;

// Vattenfall via floating bars
const bStart=P.prorated_budget_mwh;
const afterIrr=bStart - P.irr_shortfall_mwh;
const afterAvail=afterIrr - P.avail_loss_mwh;
const actual=P.actual_mwh;
new Chart(document.getElementById('wf'),{{
  type:'bar',
  data:{{labels:['Budget\\n(pro-ratad)','− Instrålning','− Tillgänglighet','+ Prestanda','Faktisk'],
    datasets:[{{
      data:[[0,bStart],[afterIrr,bStart],[afterAvail,afterIrr],[afterAvail,actual],[0,actual]],
      backgroundColor:[C.budget,C.sun,C.avail,C.perf,C.actual],
      borderRadius:4,barPercentage:.72
    }}]}},
  options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}},
    tooltip:{{callbacks:{{label:c=>{{const v=c.raw;return fmt(Math.abs(v[1]-v[0]))+' MWh';}}}}}}}},
    scales:{{x:{{grid:{{display:false}},ticks:{{font:{{size:10}}}}}},
      y:{{grid:{{color:grid}},ticks:{{callback:fmt}},beginAtZero:false,min:8000}}}}}}
}});

// Per park stacked
const labels=G.parks.map(p=>p.park);
new Chart(document.getElementById('parks'),{{
  type:'bar',
  data:{{labels,datasets:[
    {{label:'Instrålning',data:G.parks.map(p=>p.irr_shortfall_mwh),backgroundColor:C.sun,borderRadius:3,stack:'s'}},
    {{label:'Tillgänglighet',data:G.parks.map(p=>p.avail_loss_mwh),backgroundColor:C.avail,borderRadius:3,stack:'s'}},
    {{label:'Prestanda',data:G.parks.map(p=>p.unexplained_mwh),backgroundColor:C.perf,borderRadius:3,stack:'s'}},
  ]}},
  options:{{responsive:true,maintainAspectRatio:false,indexAxis:'y',
    plugins:{{legend:{{display:false}},
      tooltip:{{callbacks:{{label:c=>c.dataset.label+': '+fmt(c.parsed.x)+' MWh'}}}}}},
    scales:{{x:{{stacked:true,grid:{{color:grid}},ticks:{{callback:fmt}}}},
      y:{{stacked:true,grid:{{display:false}}}}}}}}
}});
</script>
</body>
</html>
"""
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print("Skrev", out, f"({len(html):,} tecken)")
