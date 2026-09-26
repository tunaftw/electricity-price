#!/usr/bin/env python3
"""Bygg en fristående HTML-dashboard för juni 2026 MTD vs budget."""
import io
import json
import os
import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

src = sys.argv[1]
out = sys.argv[2]
d = json.load(open(src, encoding="utf-8"))

SV_MONTHS = ["", "januari", "februari", "mars", "april", "maj", "juni",
             "juli", "augusti", "september", "oktober", "november", "december"]
month_name = SV_MONTHS[d["month"]]
data_js = json.dumps(d, ensure_ascii=False)

p = d["portfolio"]
vs = p["vs_budget_pct"]
diff_mwh = round(p["actual_mwh"] - p["prorated_budget_mwh"], 1)
rev_diff = p["rev_spot_eur"] - (p["budget_rev_eur"] or 0)

html = f"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Juni 2026 — Produktion &amp; intäkt mot budget</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
:root {{
  --font-body: 'Sora', system-ui, sans-serif;
  --font-mono: 'IBM Plex Mono', 'SF Mono', Consolas, monospace;
  --bg: #0c1014;
  --surface: #141a21;
  --surface-elevated: #1a2129;
  --border: rgba(255,255,255,0.07);
  --border-bright: rgba(255,255,255,0.14);
  --text: #e8eef2;
  --text-dim: #8a98a5;
  --accent: #f4b942;
  --accent-dim: rgba(244,185,66,0.12);
  --green: #34d399;
  --green-dim: rgba(52,211,153,0.13);
  --red: #f87171;
  --red-dim: rgba(248,113,113,0.13);
  --budget: #6b7785;
  --budget-dim: rgba(107,119,133,0.25);
}}
@media (prefers-color-scheme: light) {{
  :root {{
    --bg: #f6f4ee;
    --surface: #ffffff;
    --surface-elevated: #ffffff;
    --border: rgba(0,0,0,0.08);
    --border-bright: rgba(0,0,0,0.16);
    --text: #1b2127;
    --text-dim: #5d6b78;
    --accent: #c8861a;
    --accent-dim: rgba(200,134,26,0.12);
    --green: #0f9d6b;
    --green-dim: rgba(15,157,107,0.12);
    --red: #d4493f;
    --red-dim: rgba(212,73,63,0.1);
    --budget: #8a96a3;
    --budget-dim: rgba(138,150,163,0.22);
  }}
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; padding: 40px 28px 64px; color: var(--text);
  font-family: var(--font-body);
  background: var(--bg);
  background-image: radial-gradient(ellipse at 50% -10%, var(--accent-dim) 0%, transparent 55%);
  overflow-wrap: break-word;
}}
.wrap {{ max-width: 1160px; margin: 0 auto; }}
header {{ margin-bottom: 28px; }}
.eyebrow {{
  font-family: var(--font-mono); font-size: 12px; letter-spacing: 2px;
  text-transform: uppercase; color: var(--accent); margin: 0 0 8px;
}}
h1 {{ font-size: clamp(28px,4vw,40px); font-weight: 700; letter-spacing: -1px; margin: 0 0 8px; }}
.sub {{ color: var(--text-dim); font-size: 15px; max-width: 70ch; }}
.sub b {{ color: var(--text); font-weight: 600; }}

.kpi-row {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(210px,1fr));
  gap: 16px; margin: 28px 0;
}}
.kpi {{
  background: var(--surface-elevated); border: 1px solid var(--border);
  border-radius: 14px; padding: 22px 22px 20px; position: relative; overflow: hidden;
  animation: fadeScale .4s ease-out both; animation-delay: calc(var(--i,0)*.07s);
}}
.kpi::before {{ content:''; position:absolute; left:0; top:0; bottom:0; width:4px; background: var(--bar,var(--accent)); }}
.kpi__label {{
  font-family: var(--font-mono); font-size: 10.5px; font-weight: 600; letter-spacing: 1.5px;
  text-transform: uppercase; color: var(--text-dim); margin-bottom: 10px;
}}
.kpi__value {{ font-size: 34px; font-weight: 700; letter-spacing: -1px; line-height: 1; font-variant-numeric: tabular-nums; }}
.kpi__value small {{ font-size: 15px; font-weight: 500; color: var(--text-dim); letter-spacing: 0; }}
.kpi__sub {{ font-family: var(--font-mono); font-size: 12px; margin-top: 8px; color: var(--text-dim); }}
.up {{ color: var(--green); }} .down {{ color: var(--red); }}

.grid2 {{ display: grid; grid-template-columns: 1.25fr 1fr; gap: 18px; margin: 18px 0; }}
@media (max-width: 880px) {{ .grid2 {{ grid-template-columns: 1fr; }} }}
.card {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 14px;
  padding: 20px 22px 16px;
}}
.card h2 {{ font-size: 15px; font-weight: 600; margin: 0 0 2px; }}
.card .hint {{ font-family: var(--font-mono); font-size: 11px; color: var(--text-dim); margin: 0 0 14px; }}
.chart-box {{ position: relative; }}
canvas {{ max-height: 340px; }}

.table-wrap {{ background: var(--surface); border: 1px solid var(--border); border-radius: 14px; overflow: hidden; margin-top: 18px; }}
.table-scroll {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
thead th {{
  background: var(--surface-elevated); font-family: var(--font-mono); font-size: 10.5px;
  font-weight: 600; text-transform: uppercase; letter-spacing: .8px; color: var(--text-dim);
  text-align: right; padding: 13px 14px; border-bottom: 2px solid var(--border-bright); white-space: nowrap;
}}
thead th:first-child, tbody td:first-child {{ text-align: left; }}
tbody td {{ padding: 11px 14px; border-bottom: 1px solid var(--border); text-align: right;
  font-variant-numeric: tabular-nums; font-family: var(--font-mono); }}
tbody td:first-child {{ font-family: var(--font-body); font-weight: 500; }}
tbody tr:hover {{ background: var(--accent-dim); }}
tbody tr:last-child td {{ border-bottom: none; }}
tfoot td {{ background: var(--surface-elevated); font-weight: 600; padding: 13px 14px; border-top: 2px solid var(--border-bright);
  text-align: right; font-family: var(--font-mono); font-variant-numeric: tabular-nums; }}
tfoot td:first-child {{ text-align: left; font-family: var(--font-body); }}
.zone {{ font-family: var(--font-mono); font-size: 10px; color: var(--text-dim); }}
.pill {{ display: inline-block; padding: 2px 9px; border-radius: 20px; font-family: var(--font-mono);
  font-size: 11.5px; font-weight: 600; }}
.pill.good {{ background: var(--green-dim); color: var(--green); }}
.pill.mid {{ background: var(--accent-dim); color: var(--accent); }}
.pill.bad {{ background: var(--red-dim); color: var(--red); }}
.note {{ color: var(--text-dim); font-size: 12.5px; line-height: 1.6; margin-top: 22px;
  border-top: 1px solid var(--border); padding-top: 16px; }}
.note b {{ color: var(--text); }}
@keyframes fadeScale {{ from {{opacity:0; transform: scale(.96);}} to {{opacity:1; transform: scale(1);}} }}
@media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
</style>
</head>
<body>
<div class="wrap">
<header>
  <p class="eyebrow">Portföljöversikt · 8 solparker · {p['kwp']:,} kWp</p>
  <h1>{month_name.capitalize()} {d['year']} — produktion &amp; intäkt mot budget</h1>
  <p class="sub">Hittills <b>{d['days_with_data']} av {d['days_in_month']} dagar</b> (t.o.m. {d['last_date']}).
  Budget pro-ratas till samma period för en rättvis jämförelse (PVsyst TMY · {d['days_with_data']}/{d['days_in_month']} av månadsbudget).</p>
</header>

<div class="kpi-row">
  <div class="kpi" style="--i:0; --bar:var(--accent)">
    <div class="kpi__label">Produktion hittills</div>
    <div class="kpi__value">{p['actual_mwh']:,.0f}<small> MWh</small></div>
    <div class="kpi__sub">av {p['prorated_budget_mwh']:,.0f} MWh budget</div>
  </div>
  <div class="kpi" style="--i:1; --bar:{'var(--red)' if vs<100 else 'var(--green)'}">
    <div class="kpi__label">Mot budget</div>
    <div class="kpi__value {'down' if vs<100 else 'up'}">{vs:.0f}<small> %</small></div>
    <div class="kpi__sub {'down' if diff_mwh<0 else 'up'}">{diff_mwh:+,.0f} MWh mot budget</div>
  </div>
  <div class="kpi" style="--i:2; --bar:var(--green)">
    <div class="kpi__label">Spot-intäkt hittills</div>
    <div class="kpi__value">{p['rev_spot_eur']/1000:,.0f}<small> k€</small></div>
    <div class="kpi__sub">{p['rev_spot_eur']:,} EUR</div>
  </div>
  <div class="kpi" style="--i:3; --bar:var(--budget)">
    <div class="kpi__label">Intäkt mot budget*</div>
    <div class="kpi__value {'down' if rev_diff<0 else 'up'}">{rev_diff/1000:+,.0f}<small> k€</small></div>
    <div class="kpi__sub">budget ≈ {(p['budget_rev_eur'] or 0)/1000:,.0f} k€ (vol×capture)</div>
  </div>
</div>

<div class="grid2">
  <div class="card">
    <h2>Kumulativ produktion vs budget</h2>
    <p class="hint">MWh ackumulerat över juni · faktisk vs pro-ratad budget</p>
    <div class="chart-box"><canvas id="cumChart"></canvas></div>
  </div>
  <div class="card">
    <h2>Daglig produktion</h2>
    <p class="hint">MWh per dag · staplar = faktisk, linje = budget/dag</p>
    <div class="chart-box"><canvas id="dailyChart"></canvas></div>
  </div>
</div>

<div class="card">
  <h2>Per park — faktisk vs budget (MWh)</h2>
  <p class="hint">Sorterat efter produktion · budget pro-ratad till {d['days_with_data']}/{d['days_in_month']} dagar</p>
  <div class="chart-box"><canvas id="parkChart" height="120"></canvas></div>
</div>

<div class="table-wrap">
  <div class="table-scroll">
    <table id="tbl">
      <thead><tr>
        <th>Park</th><th>kWp</th><th>Faktisk<br>MWh</th><th>Budget<br>MWh</th>
        <th>Mot<br>budget</th><th>Yield<br>kWh/kWp</th><th>PR %</th>
        <th>Capture<br>€/MWh</th><th>Spot-intäkt<br>EUR</th>
      </tr></thead>
      <tbody></tbody>
      <tfoot></tfoot>
    </table>
  </div>
</div>

<p class="note">
<b>Metod.</b> Faktisk produktion kommer från Bazefield (grid-mätare, annars inverter-summa). Budget är PVsyst TMY-månadsbudget
pro-ratad linjärt till antalet dagar med data ({d['days_with_data']}/{d['days_in_month']}). Spot-intäkt = faktisk produktion × spotpris (SE3/SE4) per 15-min.
<b>*Intäkt mot budget</b> är en grov skattning: pro-ratad budgetvolym × samma capture-pris som faktiskt utfall — den isolerar volymavvikelsen, inte prisrörelser.
Capture-premie är negativ för alla parker i juni (sol-tunga timmar pressar priset). Data t.o.m. {d['last_date']}; juni har {d['days_in_month'] - d['days_with_data']} dagar kvar.
</p>
</div>

<script>
const D = {data_js};
const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const text = css('--text-dim'), grid = isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.06)';
const fam = css('--font-mono') || 'monospace';
const C = {{ accent: css('--accent'), green: css('--green'), budget: css('--budget'),
  accentDim: css('--accent-dim'), budgetDim: css('--budget-dim'), red: css('--red') }};
Chart.defaults.color = text; Chart.defaults.font.family = fam; Chart.defaults.font.size = 11;
const fmt = (v) => v.toLocaleString('sv-SE');
const dayLabels = D.daily_series.map(r => r.date.slice(8,10) + '/6');

// Kumulativ
new Chart(document.getElementById('cumChart'), {{
  type: 'line',
  data: {{ labels: dayLabels, datasets: [
    {{ label: 'Faktisk', data: D.daily_series.map(r=>r.cum_actual_mwh), borderColor: C.accent,
       backgroundColor: C.accentDim, fill: true, tension: .25, pointRadius: 0, borderWidth: 2.5 }},
    {{ label: 'Budget (pro-ratad)', data: D.daily_series.map(r=>r.cum_budget_mwh), borderColor: C.budget,
       borderDash: [6,4], fill: false, tension: .25, pointRadius: 0, borderWidth: 2 }},
  ]}},
  options: {{ responsive:true, maintainAspectRatio:false, interaction:{{mode:'index',intersect:false}},
    plugins:{{ legend:{{position:'top',labels:{{boxWidth:12,usePointStyle:true}}}},
      tooltip:{{callbacks:{{label:(c)=>c.dataset.label+': '+fmt(Math.round(c.parsed.y))+' MWh'}}}}}},
    scales:{{ x:{{grid:{{color:grid}}}}, y:{{grid:{{color:grid}},ticks:{{callback:v=>fmt(v)}}}} }} }}
}});

// Daglig
new Chart(document.getElementById('dailyChart'), {{
  data: {{ labels: dayLabels, datasets: [
    {{ type:'bar', label:'Faktisk', data: D.daily_series.map(r=>r.actual_mwh),
       backgroundColor: C.accent, borderRadius: 3, barPercentage:.85, categoryPercentage:.85 }},
    {{ type:'line', label:'Budget/dag', data: D.daily_series.map(r=>r.budget_mwh),
       borderColor: C.budget, borderDash:[5,4], pointRadius:0, borderWidth:2, tension:.2 }},
  ]}},
  options: {{ responsive:true, maintainAspectRatio:false, interaction:{{mode:'index',intersect:false}},
    plugins:{{ legend:{{position:'top',labels:{{boxWidth:12,usePointStyle:true}}}},
      tooltip:{{callbacks:{{label:(c)=>c.dataset.label+': '+fmt(Math.round(c.parsed.y))+' MWh'}}}}}},
    scales:{{ x:{{grid:{{display:false}}}}, y:{{grid:{{color:grid}},ticks:{{callback:v=>fmt(v)}}}} }} }}
}});

// Per park
new Chart(document.getElementById('parkChart'), {{
  type: 'bar',
  data: {{ labels: D.parks.map(p=>p.park), datasets: [
    {{ label:'Faktisk', data: D.parks.map(p=>p.actual_mwh), backgroundColor: C.accent, borderRadius:4 }},
    {{ label:'Budget (pro-ratad)', data: D.parks.map(p=>p.prorated_budget_mwh), backgroundColor: C.budgetDim,
       borderColor: C.budget, borderWidth:1.5, borderRadius:4 }},
  ]}},
  options: {{ responsive:true, maintainAspectRatio:false, indexAxis:'y',
    plugins:{{ legend:{{position:'top',labels:{{boxWidth:12,usePointStyle:true}}}},
      tooltip:{{callbacks:{{label:(c)=>c.dataset.label+': '+fmt(Math.round(c.parsed.x))+' MWh'}}}}}},
    scales:{{ x:{{grid:{{color:grid}},ticks:{{callback:v=>fmt(v)}}}}, y:{{grid:{{display:false}}}} }} }}
}});

// Tabell
const tb = document.querySelector('#tbl tbody');
const pill = (v) => {{ const c = v>=98?'good':(v>=90?'mid':'bad'); return `<span class="pill ${{c}}">${{v.toFixed(0)}} %</span>`; }};
D.parks.forEach(p => {{
  tb.insertAdjacentHTML('beforeend', `<tr>
    <td>${{p.park}} <span class="zone">${{p.zone}}</span></td>
    <td>${{fmt(p.kwp)}}</td>
    <td>${{fmt(Math.round(p.actual_mwh))}}</td>
    <td>${{fmt(Math.round(p.prorated_budget_mwh))}}</td>
    <td>${{pill(p.vs_budget_pct)}}</td>
    <td>${{p.yield_kwh_kwp.toFixed(0)}}</td>
    <td>${{p.pr_pct.toFixed(0)}}</td>
    <td>${{p.capture_eur_mwh.toFixed(1)}}</td>
    <td>${{fmt(p.rev_spot_eur)}}</td>
  </tr>`);
}});
const P = D.portfolio;
document.querySelector('#tbl tfoot').insertAdjacentHTML('beforeend', `<tr>
  <td>Portfölj</td><td>${{fmt(P.kwp)}}</td>
  <td>${{fmt(Math.round(P.actual_mwh))}}</td>
  <td>${{fmt(Math.round(P.prorated_budget_mwh))}}</td>
  <td>${{pill(P.vs_budget_pct)}}</td>
  <td></td><td></td><td></td><td>${{fmt(P.rev_spot_eur)}}</td>
</tr>`);
</script>
</body>
</html>
"""

os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print("Skrev", out, f"({len(html):,} tecken)")
