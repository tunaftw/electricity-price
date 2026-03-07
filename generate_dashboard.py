#!/usr/bin/env python3
"""Generera en interaktiv HTML-dashboard för svenska elpriser.

Skapar en fristående HTML-fil med Plotly.js som visar:
  1. Årsöversikt — tabell och grupperat stapeldiagram
  2. Månadsvy — jämförelse av månader över flera år
  3. Trendanalys — kronologisk tidsserie med dubbla y-axlar

All data beräknas av elpris.dashboard_data.calculate_dashboard_data().
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Säkerställ att projektets rot finns i sys.path
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris.dashboard_data import calculate_dashboard_data


def _build_html(data: dict) -> str:
    """Bygg den kompletta HTML-strängen med inbäddad data och JavaScript."""

    data_json = json.dumps(data, ensure_ascii=False, indent=None)

    html = f"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Elpris Dashboard &mdash; Sverige</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
/* ===== CSS Reset & Base ===== */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

:root {{
    --color-primary: #2563eb;
    --color-secondary: #0d9488;
    --color-accent: #f59e0b;
    --color-bg: #f8fafc;
    --color-surface: #ffffff;
    --color-text: #1e293b;
    --color-text-muted: #64748b;
    --color-border: #e2e8f0;
    --color-se1: #3b82f6;
    --color-se2: #10b981;
    --color-se3: #f59e0b;
    --color-se4: #ef4444;
    --radius: 8px;
    --shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06);
    --shadow-md: 0 4px 6px rgba(0,0,0,0.07), 0 2px 4px rgba(0,0,0,0.05);
    --font-sans: 'Segoe UI', system-ui, -apple-system, sans-serif;
    --font-mono: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
}}

html {{ scroll-behavior: smooth; }}

body {{
    font-family: var(--font-sans);
    background: var(--color-bg);
    color: var(--color-text);
    line-height: 1.6;
    min-height: 100vh;
}}

/* ===== Header ===== */
.header {{
    background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
    color: #fff;
    padding: 2rem 1.5rem 1.5rem;
    text-align: center;
}}
.header h1 {{
    font-size: 1.8rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    margin-bottom: 0.3rem;
}}
.header .subtitle {{
    font-size: 0.95rem;
    opacity: 0.85;
    margin-bottom: 0.2rem;
}}
.header .generated {{
    font-size: 0.8rem;
    opacity: 0.65;
}}

/* ===== Tab Navigation ===== */
.tab-nav {{
    display: flex;
    justify-content: center;
    gap: 0;
    background: var(--color-surface);
    border-bottom: 2px solid var(--color-border);
    position: sticky;
    top: 0;
    z-index: 100;
    box-shadow: var(--shadow);
}}
.tab-btn {{
    padding: 0.85rem 1.8rem;
    border: none;
    background: transparent;
    color: var(--color-text-muted);
    font-size: 0.95rem;
    font-weight: 500;
    cursor: pointer;
    border-bottom: 3px solid transparent;
    transition: all 0.2s ease;
    font-family: inherit;
}}
.tab-btn:hover {{
    color: var(--color-primary);
    background: rgba(37, 99, 235, 0.04);
}}
.tab-btn.active {{
    color: var(--color-primary);
    border-bottom-color: var(--color-primary);
    font-weight: 600;
}}

/* ===== Main Container ===== */
.container {{
    max-width: 1400px;
    margin: 0 auto;
    padding: 1.5rem;
}}

.tab-content {{
    display: none;
}}
.tab-content.active {{
    display: block;
}}

/* ===== Section Headings ===== */
.section-header {{
    margin-bottom: 1.5rem;
}}
.section-header h2 {{
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-text);
    margin-bottom: 0.3rem;
}}
.section-header p {{
    font-size: 0.9rem;
    color: var(--color-text-muted);
    max-width: 720px;
}}

/* ===== Card ===== */
.card {{
    background: var(--color-surface);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    padding: 1.5rem;
    margin-bottom: 1.5rem;
}}
.card-title {{
    font-size: 1.05rem;
    font-weight: 600;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}}

/* ===== Filter Controls ===== */
.filters {{
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    align-items: flex-end;
    margin-bottom: 1rem;
    padding: 1rem;
    background: #f1f5f9;
    border-radius: var(--radius);
}}
.filter-group {{
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
}}
.filter-group label {{
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
}}
.filter-group select,
.filter-group input[type="checkbox"] {{
    font-family: inherit;
}}
.filter-group select {{
    padding: 0.45rem 0.7rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    font-size: 0.88rem;
    background: #fff;
    color: var(--color-text);
    cursor: pointer;
    min-width: 140px;
}}
.checkbox-group {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1rem;
}}
.checkbox-group label {{
    display: flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.88rem;
    font-weight: 400;
    text-transform: none;
    letter-spacing: 0;
    cursor: pointer;
    color: var(--color-text);
}}
.checkbox-group input[type="checkbox"] {{
    accent-color: var(--color-primary);
    width: 16px;
    height: 16px;
}}

/* ===== Tables ===== */
.table-wrapper {{
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.88rem;
}}
thead th {{
    background: #f1f5f9;
    color: var(--color-text-muted);
    font-weight: 600;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 0.65rem 0.8rem;
    text-align: right;
    border-bottom: 2px solid var(--color-border);
    white-space: nowrap;
}}
thead th:first-child {{
    text-align: left;
}}
tbody td {{
    padding: 0.55rem 0.8rem;
    text-align: right;
    border-bottom: 1px solid var(--color-border);
    white-space: nowrap;
}}
tbody td:first-child {{
    text-align: left;
    font-weight: 500;
}}
tbody tr:hover {{
    background: rgba(37, 99, 235, 0.03);
}}
.zone-header {{
    background: #f8fafc;
    font-weight: 700 !important;
    color: var(--color-primary);
}}
.zone-header td {{
    padding-top: 0.9rem;
    border-bottom: 2px solid var(--color-primary);
    font-weight: 700;
}}

/* Ratio color coding */
.ratio-good {{ color: #059669; font-weight: 600; }}
.ratio-ok {{ color: #d97706; font-weight: 600; }}
.ratio-bad {{ color: #dc2626; font-weight: 600; }}

/* ===== Tooltip / Info Icon ===== */
.info-tip {{
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #e2e8f0;
    color: var(--color-text-muted);
    font-size: 0.7rem;
    font-weight: 700;
    cursor: help;
    flex-shrink: 0;
}}
.info-tip .tip-text {{
    display: none;
    position: absolute;
    bottom: calc(100% + 8px);
    left: 50%;
    transform: translateX(-50%);
    background: #1e293b;
    color: #fff;
    padding: 0.6rem 0.8rem;
    border-radius: 6px;
    font-size: 0.8rem;
    font-weight: 400;
    line-height: 1.45;
    width: 280px;
    z-index: 200;
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    text-align: left;
    white-space: normal;
}}
.info-tip .tip-text::after {{
    content: '';
    position: absolute;
    top: 100%;
    left: 50%;
    transform: translateX(-50%);
    border: 6px solid transparent;
    border-top-color: #1e293b;
}}
.info-tip:hover .tip-text {{
    display: block;
}}

/* ===== Chart Container ===== */
.chart-container {{
    width: 100%;
    min-height: 400px;
}}

/* ===== Footer ===== */
.footer {{
    margin-top: 2rem;
    padding: 1.5rem;
    text-align: center;
    font-size: 0.8rem;
    color: var(--color-text-muted);
    border-top: 1px solid var(--color-border);
}}
.footer a {{
    color: var(--color-primary);
    text-decoration: none;
}}
.footer a:hover {{
    text-decoration: underline;
}}
.footer .sources {{
    margin-top: 0.5rem;
}}

/* ===== Responsive ===== */
@media (max-width: 768px) {{
    .header h1 {{ font-size: 1.4rem; }}
    .tab-btn {{ padding: 0.65rem 1rem; font-size: 0.85rem; }}
    .container {{ padding: 1rem; }}
    .filters {{ flex-direction: column; }}
}}
</style>
</head>
<body>

<!-- ===== Header ===== -->
<div class="header">
    <h1>Elpris Dashboard &mdash; Sverige</h1>
    <p class="subtitle">Spotpriser, capture prices och solproduktionsanalys f&ouml;r SE1&ndash;SE4</p>
    <p class="generated">Genererad: {data["generated"]}</p>
</div>

<!-- ===== Tab Navigation ===== -->
<nav class="tab-nav">
    <button class="tab-btn active" onclick="switchTab('yearly')">&#128202; &Aring;rs&ouml;versikt</button>
    <button class="tab-btn" onclick="switchTab('monthly')">&#128197; M&aring;nadsvy</button>
    <button class="tab-btn" onclick="switchTab('trend')">&#128200; Trendanalys</button>
</nav>

<div class="container">

<!-- ============================================================ -->
<!-- SECTION 1: &Aring;rsöversikt                                      -->
<!-- ============================================================ -->
<div id="tab-yearly" class="tab-content active">

    <div class="section-header">
        <h2>&Aring;rs&ouml;versikt
            <span class="info-tip">&oline;
                <span class="tip-text">Denna vy visar baseload- och capture-priser sammanfattade per &aring;r f&ouml;r varje elomr&aring;de (SE1&ndash;SE4). Anv&auml;nd dropdown-menyn f&ouml;r att v&auml;lja vilken solprofil som visas.</span>
            </span>
        </h2>
        <p>&Aring;rlig sammanst&auml;llning av genomsnittliga spotpriser och solproduktionsviktade capture prices per elomr&aring;de.</p>
    </div>

    <!-- Filters -->
    <div class="filters">
        <div class="filter-group">
            <label for="yearly-profile">Prim&auml;r capture-profil</label>
            <select id="yearly-profile" onchange="renderYearly()">
            </select>
        </div>
    </div>

    <!-- Table -->
    <div class="card">
        <div class="card-title">
            Priser per &aring;r och zon (EUR/MWh)
            <span class="info-tip">&oline;
                <span class="tip-text"><strong>Baseload:</strong> Genomsnittligt elpris f&ouml;r alla timmar under perioden.<br><br><strong>Capture price:</strong> Genomsnittligt elpris viktat mot solproduktion &mdash; priset en solanl&auml;ggning faktiskt f&aring;r.<br><br><strong>Capture ratio:</strong> Capture price / Baseload &mdash; &lt;1 betyder att sol producerar mer n&auml;r priset &auml;r l&aring;gt.</span>
            </span>
        </div>
        <div class="table-wrapper">
            <table id="yearly-table">
                <thead id="yearly-thead"></thead>
                <tbody id="yearly-tbody"></tbody>
            </table>
        </div>
    </div>

    <!-- Chart -->
    <div class="card">
        <div class="card-title">Baseload vs Capture Price per &aring;r</div>
        <div id="yearly-chart" class="chart-container"></div>
    </div>
</div>

<!-- ============================================================ -->
<!-- SECTION 2: M&aring;nadsvy                                         -->
<!-- ============================================================ -->
<div id="tab-monthly" class="tab-content">

    <div class="section-header">
        <h2>M&aring;nadsvy
            <span class="info-tip">&oline;
                <span class="tip-text">J&auml;mf&ouml;r m&aring;nadsm&ouml;nster &ouml;ver flera &aring;r. V&auml;lj zon, &aring;r och profil f&ouml;r att se hur priserna varierar under &aring;ret.</span>
            </span>
        </h2>
        <p>J&auml;mf&ouml;r m&aring;nadspriser &ouml;ver &aring;ren f&ouml;r att identifiera s&auml;songsm&ouml;nster i baseload och capture prices.</p>
    </div>

    <!-- Filters -->
    <div class="filters">
        <div class="filter-group">
            <label for="monthly-zone">Zon</label>
            <select id="monthly-zone" onchange="renderMonthly()">
            </select>
        </div>
        <div class="filter-group">
            <label>&Aring;r att j&auml;mf&ouml;ra</label>
            <div id="monthly-years" class="checkbox-group"></div>
        </div>
        <div class="filter-group">
            <label for="monthly-profile">Capture-profil</label>
            <select id="monthly-profile" onchange="renderMonthly()">
            </select>
        </div>
    </div>

    <!-- Table -->
    <div class="card">
        <div class="card-title">M&aring;nadspriser (EUR/MWh)</div>
        <div class="table-wrapper">
            <table id="monthly-table">
                <thead id="monthly-thead"></thead>
                <tbody id="monthly-tbody"></tbody>
            </table>
        </div>
    </div>

    <!-- Chart -->
    <div class="card">
        <div class="card-title">M&aring;nadsm&ouml;nster &mdash; Baseload och Capture Price</div>
        <div id="monthly-chart" class="chart-container"></div>
    </div>
</div>

<!-- ============================================================ -->
<!-- SECTION 3: Trendanalys                                       -->
<!-- ============================================================ -->
<div id="tab-trend" class="tab-content">

    <div class="section-header">
        <h2>Trendanalys
            <span class="info-tip">&oline;
                <span class="tip-text">Kronologisk tidsserie &ouml;ver alla m&aring;nader. Baseload och capture prices p&aring; v&auml;nster y-axel, capture ratio p&aring; h&ouml;ger y-axel. Anv&auml;nd range-slidern f&ouml;r att zooma.</span>
            </span>
        </h2>
        <p>Kronologisk utveckling av priser och capture ratio m&aring;nad f&ouml;r m&aring;nad &mdash; identifiera l&aring;ngsiktiga trender.</p>
    </div>

    <!-- Filters -->
    <div class="filters">
        <div class="filter-group">
            <label for="trend-zone">Zon</label>
            <select id="trend-zone" onchange="renderTrend()">
            </select>
        </div>
        <div class="filter-group">
            <label>Profiler att visa</label>
            <div id="trend-profiles" class="checkbox-group"></div>
        </div>
    </div>

    <!-- Chart -->
    <div class="card">
        <div class="card-title">Prisutveckling &ouml;ver tid (EUR/MWh)
            <span class="info-tip">&oline;
                <span class="tip-text"><strong>Fyllda linjer (v&auml;nster axel):</strong> Pris i EUR/MWh.<br><br><strong>Streckad linje (h&ouml;ger axel):</strong> Capture ratio (capture / baseload).<br><br>Anv&auml;nd range-slidern nedanf&ouml;r diagrammet f&ouml;r att zooma in p&aring; en specifik period.</span>
            </span>
        </div>
        <div id="trend-chart" class="chart-container" style="min-height:500px;"></div>
    </div>
</div>

</div><!-- /container -->

<!-- ===== Footer ===== -->
<div class="footer">
    <p><strong>Elpris Dashboard</strong> &mdash; Svea Solar Analys</p>
    <div class="sources">
        <p><strong>Datak&auml;llor:</strong>
            <a href="https://www.elprisetjustnu.se/" target="_blank">elprisetjustnu.se</a> (spotpriser) &bull;
            <a href="https://transparency.entsoe.eu/" target="_blank">ENTSO-E</a> (produktion) &bull;
            Solprofiler fr&aring;n PVsyst-simuleringar och ENTSO-E normaliserad produktion
        </p>
        <p style="margin-top:0.3rem;">
            <strong>Metod:</strong> Capture price = &Sigma;(spotpris &times; solproduktionsvikt) / &Sigma;(solproduktionsvikt).
            Baseload = aritmetiskt medelv&auml;rde av alla spotpriser under perioden.
        </p>
    </div>
</div>

<!-- ===== JavaScript ===== -->
<script>
// ============================================================
// Inbäddad data
// ============================================================
const DATA = {data_json};

// ============================================================
// Hjälpfunktioner
// ============================================================
const ZONE_COLORS = {{
    'SE1': '#3b82f6',
    'SE2': '#10b981',
    'SE3': '#f59e0b',
    'SE4': '#ef4444'
}};

const PROFILE_COLORS = {{
    'south_lundby': '#f59e0b',
    'ew_boda': '#8b5cf6',
    'tracker_sweden': '#10b981',
    'entsoe_solar_SE1': '#93c5fd',
    'entsoe_solar_SE2': '#6ee7b7',
    'entsoe_solar_SE3': '#fcd34d',
    'entsoe_solar_SE4': '#fca5a5'
}};

const YEAR_COLORS = [
    '#3b82f6',  // 2021 blue
    '#10b981',  // 2022 green
    '#f59e0b',  // 2023 amber
    '#ef4444',  // 2024 red
    '#8b5cf6',  // 2025 purple
    '#0d9488',  // 2026 teal
    '#ec4899',  // 2027 pink
    '#6366f1',  // 2028 indigo
];

const MONTH_NAMES = [
    'Jan', 'Feb', 'Mar', 'Apr', 'Maj', 'Jun',
    'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dec'
];

const MONTH_FULL = [
    'Januari', 'Februari', 'Mars', 'April', 'Maj', 'Juni',
    'Juli', 'Augusti', 'September', 'Oktober', 'November', 'December'
];

function fmt(v, decimals) {{
    if (v === null || v === undefined) return '&ndash;';
    decimals = decimals !== undefined ? decimals : 1;
    return v.toFixed(decimals);
}}

function ratioClass(r) {{
    if (r === null || r === undefined) return '';
    if (r >= 0.9) return 'ratio-good';
    if (r >= 0.7) return 'ratio-ok';
    return 'ratio-bad';
}}

function ratioHtml(r) {{
    if (r === null || r === undefined) return '<span>&ndash;</span>';
    const cls = ratioClass(r);
    return '<span class="' + cls + '">' + fmt(r, 2) + '</span>';
}}

function getProfileLabel(key) {{
    return DATA.profiles[key] || key;
}}

function getAllYears() {{
    const years = new Set();
    for (const zone of DATA.zones) {{
        if (DATA.yearly[zone]) {{
            DATA.yearly[zone].forEach(r => years.add(r.year));
        }}
    }}
    return Array.from(years).sort();
}}

function getProfileKeys() {{
    return Object.keys(DATA.profiles);
}}

// Determine the primary (first-listed PVsyst) profiles for the table columns
function getPrimaryProfiles() {{
    const pvsyst = [];
    const entsoe = [];
    for (const key of getProfileKeys()) {{
        if (key.startsWith('entsoe_')) {{
            entsoe.push(key);
        }} else {{
            pvsyst.push(key);
        }}
    }}
    return {{ pvsyst, entsoe, all: [...pvsyst, ...entsoe] }};
}}

// ============================================================
// Tab switching
// ============================================================
function switchTab(tab) {{
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
    document.getElementById('tab-' + tab).classList.add('active');
    // Find button by tab name
    const btns = document.querySelectorAll('.tab-btn');
    const names = ['yearly', 'monthly', 'trend'];
    const idx = names.indexOf(tab);
    if (idx >= 0 && btns[idx]) btns[idx].classList.add('active');

    // Trigger Plotly resize for hidden → visible charts
    setTimeout(() => {{
        window.dispatchEvent(new Event('resize'));
    }}, 50);

    // Lazy-render sections on first activation
    if (tab === 'monthly' && !monthlyRendered) {{
        initMonthly();
        monthlyRendered = true;
    }}
    if (tab === 'trend' && !trendRendered) {{
        initTrend();
        trendRendered = true;
    }}
}}

let monthlyRendered = false;
let trendRendered = false;

// ============================================================
// SECTION 1: Årsöversikt
// ============================================================
function initYearly() {{
    const sel = document.getElementById('yearly-profile');
    const profiles = getPrimaryProfiles();
    profiles.pvsyst.forEach(key => {{
        const opt = document.createElement('option');
        opt.value = key;
        opt.textContent = getProfileLabel(key);
        sel.appendChild(opt);
    }});
    profiles.entsoe.forEach(key => {{
        const opt = document.createElement('option');
        opt.value = key;
        opt.textContent = getProfileLabel(key);
        sel.appendChild(opt);
    }});
    // Default to south_lundby if available
    if (profiles.pvsyst.includes('south_lundby')) {{
        sel.value = 'south_lundby';
    }}
    renderYearly();
}}

function renderYearly() {{
    const profileKey = document.getElementById('yearly-profile').value;
    const profiles = getPrimaryProfiles();

    // === Table ===
    const thead = document.getElementById('yearly-thead');
    const tbody = document.getElementById('yearly-tbody');

    // Build header: Zon/År | Baseload | Capture (vald profil) | Ratio | (andra profiler ratios)
    let headerHtml = '<tr>';
    headerHtml += '<th style="text-align:left">&Aring;r</th>';
    headerHtml += '<th>Baseload</th>';
    headerHtml += '<th>Capture (' + getProfileLabel(profileKey) + ')</th>';
    headerHtml += '<th>Ratio</th>';
    // Add other PVsyst profiles as additional ratio columns
    profiles.pvsyst.forEach(k => {{
        if (k !== profileKey) {{
            headerHtml += '<th>Ratio ' + getProfileLabel(k).split(' ')[0] + '</th>';
        }}
    }});
    headerHtml += '<th style="font-size:0.72rem;">Datapunkter</th>';
    headerHtml += '</tr>';
    thead.innerHTML = headerHtml;

    // Build body: grouped by zone
    let bodyHtml = '';
    DATA.zones.forEach(zone => {{
        const rows = DATA.yearly[zone] || [];
        if (rows.length === 0) return;

        // Zone header row
        bodyHtml += '<tr class="zone-header"><td colspan="99" style="color:' + ZONE_COLORS[zone] + '">' + zone + '</td></tr>';

        rows.forEach(row => {{
            const isPartial = (row.year === 2021 && row.records < 8760 * 4) ||
                              (row.year === new Date().getFullYear());
            const yearLabel = isPartial && row.year === new Date().getFullYear()
                ? row.year + ' (YTD)' : String(row.year);

            bodyHtml += '<tr>';
            bodyHtml += '<td>' + yearLabel + '</td>';
            bodyHtml += '<td>' + fmt(row.baseload) + '</td>';
            bodyHtml += '<td>' + fmt(row.capture[profileKey]) + '</td>';
            bodyHtml += '<td>' + ratioHtml(row.ratio[profileKey]) + '</td>';
            profiles.pvsyst.forEach(k => {{
                if (k !== profileKey) {{
                    bodyHtml += '<td>' + ratioHtml(row.ratio[k]) + '</td>';
                }}
            }});
            bodyHtml += '<td style="color:var(--color-text-muted);font-size:0.82rem">' + (row.records || '') + '</td>';
            bodyHtml += '</tr>';
        }});
    }});
    tbody.innerHTML = bodyHtml;

    // === Chart ===
    renderYearlyChart(profileKey);
}}

function renderYearlyChart(profileKey) {{
    const years = getAllYears();
    const traces = [];

    DATA.zones.forEach((zone, zi) => {{
        const rows = DATA.yearly[zone] || [];
        const baseloadVals = years.map(y => {{
            const r = rows.find(row => row.year === y);
            return r ? r.baseload : null;
        }});
        const captureVals = years.map(y => {{
            const r = rows.find(row => row.year === y);
            return r && r.capture[profileKey] !== undefined ? r.capture[profileKey] : null;
        }});
        const ratioVals = years.map(y => {{
            const r = rows.find(row => row.year === y);
            return r && r.ratio[profileKey] !== undefined ? r.ratio[profileKey] : null;
        }});

        // Baseload bar
        traces.push({{
            x: years.map(String),
            y: baseloadVals,
            name: zone + ' Baseload',
            type: 'bar',
            marker: {{ color: ZONE_COLORS[zone], opacity: 0.6 }},
            legendgroup: zone,
            hovertemplate: zone + ' %{{x}}<br>Baseload: %{{y:.1f}} EUR/MWh<extra></extra>',
            offsetgroup: zone,
        }});

        // Capture bar
        traces.push({{
            x: years.map(String),
            y: captureVals,
            name: zone + ' Capture',
            type: 'bar',
            marker: {{ color: ZONE_COLORS[zone], opacity: 1.0 }},
            legendgroup: zone,
            showlegend: false,
            customdata: ratioVals,
            hovertemplate: zone + ' %{{x}}<br>Capture: %{{y:.1f}} EUR/MWh<br>Ratio: %{{customdata:.2f}}<extra></extra>',
            offsetgroup: zone + '_c',
        }});
    }});

    const layout = {{
        barmode: 'group',
        xaxis: {{
            title: '',
            type: 'category',
        }},
        yaxis: {{
            title: 'EUR/MWh',
            rangemode: 'tozero',
        }},
        legend: {{
            orientation: 'h',
            yanchor: 'bottom',
            y: 1.02,
            xanchor: 'center',
            x: 0.5,
        }},
        margin: {{ t: 40, r: 30, b: 40, l: 60 }},
        plot_bgcolor: '#fff',
        paper_bgcolor: '#fff',
        font: {{ family: 'Segoe UI, system-ui, sans-serif', size: 13 }},
        hoverlabel: {{ bgcolor: '#1e293b', font: {{ color: '#fff', size: 13 }} }},
    }};

    Plotly.newPlot('yearly-chart', traces, layout, {{
        responsive: true,
        displayModeBar: true,
        modeBarButtonsToRemove: ['lasso2d', 'select2d'],
    }});
}}

// ============================================================
// SECTION 2: Månadsvy
// ============================================================
function initMonthly() {{
    // Zone dropdown
    const zoneSel = document.getElementById('monthly-zone');
    DATA.zones.forEach(z => {{
        const opt = document.createElement('option');
        opt.value = z;
        opt.textContent = z;
        if (z === 'SE3') opt.selected = true;
        zoneSel.appendChild(opt);
    }});

    // Profile dropdown
    const profSel = document.getElementById('monthly-profile');
    getProfileKeys().forEach(key => {{
        const opt = document.createElement('option');
        opt.value = key;
        opt.textContent = getProfileLabel(key);
        profSel.appendChild(opt);
    }});
    if (getProfileKeys().includes('south_lundby')) {{
        profSel.value = 'south_lundby';
    }}

    // Year checkboxes
    const yearsDiv = document.getElementById('monthly-years');
    const years = getAllYears();
    years.forEach((y, i) => {{
        const lbl = document.createElement('label');
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.value = y;
        // Check the last 3 years by default
        if (i >= years.length - 3) cb.checked = true;
        cb.addEventListener('change', renderMonthly);
        lbl.appendChild(cb);
        lbl.appendChild(document.createTextNode(' ' + y));
        yearsDiv.appendChild(lbl);
    }});

    renderMonthly();
}}

function getSelectedMonthlyYears() {{
    const cbs = document.querySelectorAll('#monthly-years input[type="checkbox"]:checked');
    return Array.from(cbs).map(cb => parseInt(cb.value)).sort();
}}

function renderMonthly() {{
    const zone = document.getElementById('monthly-zone').value;
    const profileKey = document.getElementById('monthly-profile').value;
    const selectedYears = getSelectedMonthlyYears();
    const monthlyData = DATA.monthly[zone] || [];

    // === Table ===
    const thead = document.getElementById('monthly-thead');
    const tbody = document.getElementById('monthly-tbody');

    let headerHtml = '<tr><th style="text-align:left">M&aring;nad</th>';
    selectedYears.forEach(y => {{
        headerHtml += '<th colspan="3" style="text-align:center;border-left:2px solid var(--color-border)">' + y + '</th>';
    }});
    headerHtml += '</tr>';
    headerHtml += '<tr><th></th>';
    selectedYears.forEach(() => {{
        headerHtml += '<th style="border-left:2px solid var(--color-border)">Baseload</th><th>Capture</th><th>Ratio</th>';
    }});
    headerHtml += '</tr>';
    thead.innerHTML = headerHtml;

    let bodyHtml = '';
    for (let m = 1; m <= 12; m++) {{
        bodyHtml += '<tr>';
        bodyHtml += '<td>' + MONTH_FULL[m - 1] + '</td>';
        selectedYears.forEach(y => {{
            const row = monthlyData.find(r => r.year === y && r.month === m);
            if (row) {{
                bodyHtml += '<td style="border-left:2px solid var(--color-border)">' + fmt(row.baseload) + '</td>';
                bodyHtml += '<td>' + fmt(row.capture[profileKey]) + '</td>';
                bodyHtml += '<td>' + ratioHtml(row.ratio[profileKey]) + '</td>';
            }} else {{
                bodyHtml += '<td style="border-left:2px solid var(--color-border)">&ndash;</td><td>&ndash;</td><td>&ndash;</td>';
            }}
        }});
        bodyHtml += '</tr>';
    }}
    tbody.innerHTML = bodyHtml;

    // === Chart ===
    renderMonthlyChart(zone, profileKey, selectedYears);
}}

function renderMonthlyChart(zone, profileKey, selectedYears) {{
    const monthlyData = DATA.monthly[zone] || [];
    const traces = [];

    selectedYears.forEach((year, yi) => {{
        const color = YEAR_COLORS[yi % YEAR_COLORS.length];

        const baseloadVals = [];
        const captureVals = [];
        const months = [];

        for (let m = 1; m <= 12; m++) {{
            const row = monthlyData.find(r => r.year === year && r.month === m);
            months.push(MONTH_NAMES[m - 1]);
            baseloadVals.push(row ? row.baseload : null);
            captureVals.push(row && row.capture[profileKey] !== undefined ? row.capture[profileKey] : null);
        }}

        // Baseload line (dashed)
        traces.push({{
            x: months,
            y: baseloadVals,
            name: year + ' Baseload',
            type: 'scatter',
            mode: 'lines+markers',
            line: {{ color: color, dash: 'dash', width: 2 }},
            marker: {{ size: 5 }},
            legendgroup: String(year),
            hovertemplate: year + ' %{{x}}<br>Baseload: %{{y:.1f}} EUR/MWh<extra></extra>',
        }});

        // Capture line (solid)
        traces.push({{
            x: months,
            y: captureVals,
            name: year + ' Capture',
            type: 'scatter',
            mode: 'lines+markers',
            line: {{ color: color, width: 2.5 }},
            marker: {{ size: 6 }},
            legendgroup: String(year),
            showlegend: false,
            hovertemplate: year + ' %{{x}}<br>Capture (' + getProfileLabel(profileKey) + '): %{{y:.1f}} EUR/MWh<extra></extra>',
        }});
    }});

    const layout = {{
        xaxis: {{
            title: '',
            type: 'category',
        }},
        yaxis: {{
            title: 'EUR/MWh',
            rangemode: 'tozero',
        }},
        legend: {{
            orientation: 'h',
            yanchor: 'bottom',
            y: 1.02,
            xanchor: 'center',
            x: 0.5,
        }},
        margin: {{ t: 40, r: 30, b: 40, l: 60 }},
        plot_bgcolor: '#fff',
        paper_bgcolor: '#fff',
        font: {{ family: 'Segoe UI, system-ui, sans-serif', size: 13 }},
        hoverlabel: {{ bgcolor: '#1e293b', font: {{ color: '#fff', size: 13 }} }},
        hovermode: 'x unified',
    }};

    Plotly.newPlot('monthly-chart', traces, layout, {{
        responsive: true,
        displayModeBar: true,
        modeBarButtonsToRemove: ['lasso2d', 'select2d'],
    }});
}}

// ============================================================
// SECTION 3: Trendanalys
// ============================================================
function initTrend() {{
    // Zone dropdown
    const zoneSel = document.getElementById('trend-zone');
    DATA.zones.forEach(z => {{
        const opt = document.createElement('option');
        opt.value = z;
        opt.textContent = z;
        if (z === 'SE3') opt.selected = true;
        zoneSel.appendChild(opt);
    }});

    // Profile checkboxes
    const profsDiv = document.getElementById('trend-profiles');
    getProfileKeys().forEach((key, i) => {{
        const lbl = document.createElement('label');
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.value = key;
        // Default: check first 3 PVsyst profiles
        if (!key.startsWith('entsoe_') || i < 1) cb.checked = true;
        cb.addEventListener('change', renderTrend);
        lbl.appendChild(cb);
        lbl.appendChild(document.createTextNode(' ' + getProfileLabel(key)));
        profsDiv.appendChild(lbl);
    }});

    renderTrend();
}}

function getSelectedTrendProfiles() {{
    const cbs = document.querySelectorAll('#trend-profiles input[type="checkbox"]:checked');
    return Array.from(cbs).map(cb => cb.value);
}}

function renderTrend() {{
    const zone = document.getElementById('trend-zone').value;
    const selectedProfiles = getSelectedTrendProfiles();
    const monthlyData = (DATA.monthly[zone] || []).slice().sort((a, b) => {{
        if (a.year !== b.year) return a.year - b.year;
        return a.month - b.month;
    }});

    if (monthlyData.length === 0) {{
        Plotly.purge('trend-chart');
        return;
    }}

    // X axis labels: "2022-03" style
    const xLabels = monthlyData.map(r => r.year + '-' + String(r.month).padStart(2, '0'));

    const traces = [];

    // Baseload line (primary, thick, blue)
    traces.push({{
        x: xLabels,
        y: monthlyData.map(r => r.baseload),
        name: 'Baseload',
        type: 'scatter',
        mode: 'lines',
        line: {{ color: '#2563eb', width: 3 }},
        yaxis: 'y',
        hovertemplate: '%{{x}}<br>Baseload: %{{y:.1f}} EUR/MWh<extra></extra>',
    }});

    // Capture lines per selected profile
    selectedProfiles.forEach(profileKey => {{
        const color = PROFILE_COLORS[profileKey] || '#888';

        // Capture price line
        traces.push({{
            x: xLabels,
            y: monthlyData.map(r => r.capture[profileKey] !== undefined ? r.capture[profileKey] : null),
            name: 'Capture ' + getProfileLabel(profileKey),
            type: 'scatter',
            mode: 'lines',
            line: {{ color: color, width: 2 }},
            yaxis: 'y',
            legendgroup: profileKey,
            hovertemplate: '%{{x}}<br>Capture (' + getProfileLabel(profileKey) + '): %{{y:.1f}} EUR/MWh<extra></extra>',
        }});

        // Ratio line (dashed, on y2)
        traces.push({{
            x: xLabels,
            y: monthlyData.map(r => r.ratio[profileKey] !== undefined ? r.ratio[profileKey] : null),
            name: 'Ratio ' + getProfileLabel(profileKey),
            type: 'scatter',
            mode: 'lines',
            line: {{ color: color, width: 1.5, dash: 'dot' }},
            yaxis: 'y2',
            legendgroup: profileKey,
            showlegend: false,
            hovertemplate: '%{{x}}<br>Ratio (' + getProfileLabel(profileKey) + '): %{{y:.2f}}<extra></extra>',
        }});
    }});

    const layout = {{
        xaxis: {{
            title: '',
            rangeslider: {{ visible: true, thickness: 0.08 }},
            type: 'category',
            tickangle: -45,
            nticks: 24,
        }},
        yaxis: {{
            title: 'EUR/MWh',
            rangemode: 'tozero',
            side: 'left',
        }},
        yaxis2: {{
            title: 'Capture Ratio',
            overlaying: 'y',
            side: 'right',
            range: [0, 1.5],
            showgrid: false,
            tickformat: '.2f',
        }},
        legend: {{
            orientation: 'h',
            yanchor: 'bottom',
            y: 1.02,
            xanchor: 'center',
            x: 0.5,
        }},
        margin: {{ t: 40, r: 60, b: 40, l: 60 }},
        plot_bgcolor: '#fff',
        paper_bgcolor: '#fff',
        font: {{ family: 'Segoe UI, system-ui, sans-serif', size: 13 }},
        hoverlabel: {{ bgcolor: '#1e293b', font: {{ color: '#fff', size: 13 }} }},
        hovermode: 'x unified',
    }};

    Plotly.newPlot('trend-chart', traces, layout, {{
        responsive: true,
        displayModeBar: true,
        modeBarButtonsToRemove: ['lasso2d', 'select2d'],
    }});
}}

// ============================================================
// Initialization
// ============================================================
document.addEventListener('DOMContentLoaded', function() {{
    initYearly();
}});
</script>
</body>
</html>"""

    return html


def main() -> None:
    """Huvudfunktion: beräkna data, generera HTML, skriv fil."""
    print("Beräknar dashboard-data...")
    data = calculate_dashboard_data()

    zones_count = len(data.get("zones", []))
    profiles_count = len(data.get("profiles", {}))
    print(f"  Zoner: {zones_count}, Profiler: {profiles_count}")

    yearly_count = sum(len(v) for v in data.get("yearly", {}).values())
    monthly_count = sum(len(v) for v in data.get("monthly", {}).values())
    print(f"  Årsrader: {yearly_count}, Månadsrader: {monthly_count}")

    print("Genererar HTML...")
    html = _build_html(data)

    # Utdatakatalog
    output_dir = PROJECT_ROOT / "Resultat" / "rapporter"
    output_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y%m%d")
    output_path = output_dir / f"dashboard_elpris_{today}.html"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = output_path.stat().st_size / 1024
    print(f"\nDashboard genererad:")
    print(f"  Fil: {output_path}")
    print(f"  Storlek: {size_kb:.0f} KB")


if __name__ == "__main__":
    main()
