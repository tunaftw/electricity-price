"""Track A renderer — extends dashboard_v2 with an ASSETS tab.

Strategy: re-use the entire dashboard_v2 HTML body (CAPTURE / BESS / FUTURES
+ the original OPERATIONS plumbing), then perform surgical text substitutions
that rename the OPERATIONS tab into a new ASSETS tab. Subsequent tasks add
the fleet / park-card / table / drill-down UI inside the ASSETS view.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from generate_dashboard_v2 import _build_html as _build_v2_html  # noqa: E402


# ---------------------------------------------------------------------------
# Initial assets-view scaffold (placeholder body — populated in later tasks)
# ---------------------------------------------------------------------------

ASSETS_VIEW_HTML = """
<div id="assets-view" style="display:none">
  <div id="assets-fleet-mode">
    <div class="card" id="assets-filterbar" style="padding:0.7rem 1rem;display:flex;gap:1rem;align-items:center;flex-wrap:wrap">
        <div style="display:flex;gap:6px;align-items:center">
            <span style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.06em;color:var(--text-muted);font-weight:600">M&aring;nad:</span>
            <select id="assets-month-select" class="invest-input" style="width:auto;padding:4px 8px"></select>
        </div>
        <div style="display:flex;gap:6px;align-items:center">
            <span style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.06em;color:var(--text-muted);font-weight:600">Zon:</span>
            <select id="assets-zone-select" class="invest-input" style="width:auto;padding:4px 8px">
                <option value="ALL">Alla zoner</option>
                <option value="SE1">SE1</option>
                <option value="SE2">SE2</option>
                <option value="SE3">SE3</option>
                <option value="SE4">SE4</option>
            </select>
        </div>
    </div>
    <div class="card">
        <div class="card-title">Fleet Overview</div>
        <div id="fleet-kpi-row" style="display:flex;gap:1rem;margin-top:0.6rem;flex-wrap:wrap"></div>
    </div>
    <div class="card">
        <div class="card-title">Parker</div>
        <div style="font-size:0.72rem;color:var(--text-muted);margin-top:-0.4rem;margin-bottom:0.8rem;line-height:1.4">
            Klicka p&aring; en park f&ouml;r drill-down. F&auml;rg:
            <span style="color:#4ADE80">gr&ouml;n &ge; +5%</span>,
            <span style="color:#fde68a">gul &plusmn;5%</span>,
            <span style="color:#f87171">r&ouml;d &le; -5%</span> mot budget.
        </div>
        <div id="park-cards-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:1rem"></div>
    </div>
    <div class="card">
        <div class="card-title" style="display:flex;align-items:center;justify-content:space-between">
            <span>J&auml;mf&ouml;relse</span>
            <button onclick="exportParkTableCsv()" style="padding:4px 10px;border:1px solid var(--border);background:transparent;color:var(--text-muted);font-size:0.7rem;font-weight:600;cursor:pointer;border-radius:4px;font-family:var(--font)">Export CSV</button>
        </div>
        <div style="font-size:0.72rem;color:var(--text-muted);margin-top:-0.4rem;margin-bottom:0.8rem;line-height:1.4">
            Klicka p&aring; en kolumnrubrik f&ouml;r att sortera. Klicka p&aring; en rad f&ouml;r drill-down.
        </div>
        <div style="overflow-x:auto">
            <table id="park-comparison-table" style="width:100%;border-collapse:collapse;font-size:0.85rem"></table>
        </div>
    </div>
  </div>

  <div id="assets-drilldown-mode" style="display:none">
    <div class="card" style="padding:0.8rem 1rem">
        <div style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap">
            <button onclick="exitDrilldown()" style="padding:6px 14px;border:1px solid var(--border);background:transparent;color:var(--text);font-size:0.8rem;font-weight:600;cursor:pointer;border-radius:6px;font-family:var(--font)">&larr; Tillbaka till fleet</button>
            <div id="drilldown-park-name" style="font-size:1.2rem;font-weight:700;color:var(--text-bright)"></div>
            <div id="drilldown-park-zone" style="font-size:0.85rem;color:var(--text-muted)"></div>
            <div style="flex:1"></div>
            <div style="display:flex;gap:6px;align-items:center">
                <span style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.06em;color:var(--text-muted);font-weight:600">M&aring;nad:</span>
                <select id="drilldown-month-select" class="invest-input" style="width:auto;padding:4px 8px"></select>
            </div>
        </div>
    </div>
    <div class="card">
        <div class="card-title">KPI</div>
        <div id="drilldown-kpi-row" style="display:flex;gap:1rem;margin-top:0.6rem;flex-wrap:wrap"></div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:1rem">
        <div class="card">
            <div class="card-title">Energi vs Budget (12 mn)</div>
            <div id="drilldown-energy-chart" class="chart-container chart-secondary"></div>
        </div>
        <div class="card">
            <div class="card-title">Yield (kWh/kWp) (12 mn)</div>
            <div id="drilldown-yield-chart" class="chart-container chart-secondary"></div>
        </div>
        <div class="card">
            <div class="card-title">Daglig produktion (vald m&aring;nad)</div>
            <div id="drilldown-daily-chart" class="chart-container chart-secondary"></div>
        </div>
        <div class="card">
            <div class="card-title">Capture Price (zon, 12 mn)</div>
            <div id="drilldown-capture-chart" class="chart-container chart-secondary"></div>
        </div>
    </div>
    <div class="card">
        <div class="card-title">B&auml;sta &amp; s&auml;msta dagar (vald m&aring;nad)</div>
        <div id="drilldown-bestworst" style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-top:0.6rem"></div>
    </div>
    <div class="card">
        <div class="card-title">L&auml;nkar</div>
        <div id="drilldown-links" style="font-size:0.85rem;color:var(--text-muted);line-height:1.8"></div>
    </div>
  </div>
</div>
""".strip()


# ---------------------------------------------------------------------------
# CSS additions for the ASSETS tab
# ---------------------------------------------------------------------------

ASSETS_CSS = r"""
/* ===== ASSETS TAB ===== */
.assets-kpi {
    flex: 1 1 160px;
    min-width: 160px;
    background: var(--bg-sidebar);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.7rem 0.9rem;
}
.assets-kpi-label {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    font-weight: 600;
    margin-bottom: 0.35rem;
}
.assets-kpi-value {
    font-size: 1.4rem;
    font-weight: 700;
    color: var(--text-bright);
    font-family: var(--font-mono);
}
.assets-kpi-sub {
    margin-top: 0.3rem;
    font-size: 0.7rem;
    color: var(--text-muted);
}
.assets-kpi.vsb-green  .assets-kpi-value { color: #4ADE80; }
.assets-kpi.vsb-yellow .assets-kpi-value { color: #fde68a; }
.assets-kpi.vsb-red    .assets-kpi-value { color: #f87171; }
.assets-kpi.vsb-green  { border-left: 3px solid #4ADE80; }
.assets-kpi.vsb-yellow { border-left: 3px solid #fde68a; }
.assets-kpi.vsb-red    { border-left: 3px solid #f87171; }

.park-card {
    background: var(--bg-sidebar);
    border: 1px solid var(--border);
    border-left: 3px solid var(--border);
    border-radius: var(--radius);
    padding: 0.9rem 1rem;
    cursor: pointer;
    transition: transform 0.12s, border-color 0.12s, box-shadow 0.12s;
}
.park-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 14px rgba(0,0,0,0.35);
    border-color: var(--product);
}
.park-card.vsb-green  { border-left-color: #4ADE80; }
.park-card.vsb-yellow { border-left-color: #fde68a; }
.park-card.vsb-red    { border-left-color: #f87171; }
.park-card-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 0.6rem;
}
.park-card-name {
    font-size: 1rem;
    font-weight: 700;
    color: var(--text-bright);
}
.park-card-zone {
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--text-muted);
    background: var(--bg-card);
    padding: 2px 8px;
    border-radius: 4px;
    border: 1px solid var(--border);
}
.park-card-row {
    display: flex;
    justify-content: space-between;
    font-size: 0.8rem;
    color: var(--text);
    padding: 2px 0;
}
.park-card-row span:first-child { color: var(--text-muted); }
.park-card-spark { margin-top: 0.6rem; }

/* Comparison table row hover */
#park-comparison-table tbody tr:hover { background: var(--bg-hover); }

/* Drill-down KPI tile size override (slightly compact) */
#drilldown-kpi-row .assets-kpi { flex: 1 1 140px; }
""".strip()


# ---------------------------------------------------------------------------
# Assets-tab JS module
# ---------------------------------------------------------------------------

ASSETS_JS = r"""
// ================================================================
// ASSETS TAB
// ================================================================
(function() {
    var ASSETS = (typeof DATA !== 'undefined' && DATA.assets) ? DATA.assets : null;

    // Defensive HTML escape for any park-name / weekday / date strings
    // we splat into HTML attributes or text. Plotly text axes do their
    // own escaping, so this only needs to wrap raw HTML interpolations.
    function htmlEsc(s) {
        if (s === null || s === undefined) return '';
        return String(s).replace(/[&<>"']/g, function(c) {
            return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c];
        });
    }

    var VSB_THRESHOLD = 5;
    var VSB_COLORS = { green: '#4ADE80', yellow: '#fde68a', red: '#f87171', neutral: '#8892a4' };

    function vsBudgetClass(pct) {
        if (pct === null || pct === undefined || isNaN(pct)) return '';
        if (pct >= VSB_THRESHOLD) return 'vsb-green';
        if (pct <= -VSB_THRESHOLD) return 'vsb-red';
        return 'vsb-yellow';
    }
    function fmtNum(v, d) {
        if (v === null || v === undefined || isNaN(v)) return '–';
        return Number(v).toLocaleString(undefined, {
            minimumFractionDigits: d || 0,
            maximumFractionDigits: d || 0,
        });
    }
    function fmtPct(v, d) {
        if (v === null || v === undefined || isNaN(v)) return '–';
        var sign = v >= 0 ? '+' : '';
        return sign + Number(v).toFixed(d === undefined ? 1 : d) + '%';
    }

    function kpiTile(label, value, sub, cls) {
        return '<div class="assets-kpi ' + (cls || '') + '">' +
            '<div class="assets-kpi-label">' + label + '</div>' +
            '<div class="assets-kpi-value">' + value + '</div>' +
            (sub ? '<div class="assets-kpi-sub">' + sub + '</div>' : '') +
            '</div>';
    }

    function vsBudgetColor(pct) {
        if (pct === null || pct === undefined || isNaN(pct)) return VSB_COLORS.neutral;
        if (pct >= VSB_THRESHOLD) return VSB_COLORS.green;
        if (pct <= -VSB_THRESHOLD) return VSB_COLORS.red;
        return VSB_COLORS.yellow;
    }

    var FILTER_STATE = { monthKey: 'latest', zone: 'ALL' };

    function latestMonthKey() {
        if (!ASSETS || !ASSETS.parks) return null;
        var maxKey = null;
        Object.values(ASSETS.parks).forEach(function(p) {
            (p.months || []).forEach(function(m) {
                var k = m.year + '-' + String(m.month).padStart(2, '0');
                if (maxKey === null || k > maxKey) maxKey = k;
            });
        });
        return maxKey;
    }
    function activeMonthKey() {
        return FILTER_STATE.monthKey === 'latest' ? latestMonthKey() : FILTER_STATE.monthKey;
    }
    function allMonthKeys() {
        if (!ASSETS || !ASSETS.parks) return [];
        var set = {};
        Object.values(ASSETS.parks).forEach(function(p) {
            (p.months || []).forEach(function(m) {
                set[m.year + '-' + String(m.month).padStart(2, '0')] = true;
            });
        });
        return Object.keys(set).sort();
    }
    function filteredParkEntries() {
        var entries = Object.entries((ASSETS && ASSETS.parks) || {});
        if (FILTER_STATE.zone !== 'ALL') {
            entries = entries.filter(function(e) { return e[1].zone === FILTER_STATE.zone; });
        }
        return entries;
    }

    function parkMonth(park, monthKey) {
        return (park.months || []).find(function(m) {
            return (m.year + '-' + String(m.month).padStart(2, '0')) === monthKey;
        });
    }

    function sparkline(months) {
        // Skip rendering for too-few-data — a single bar at full width
        // looks awkward and adds no signal.
        if (!months || months.length < 2) return '';
        var W = 96, H = 26;
        var BARW = Math.min(12, Math.max(2, Math.floor(W / months.length) - 1));
        var max = Math.max.apply(null, months.map(function(m) { return m.energy_mwh || 0; })) || 1;
        var bars = months.map(function(m, i) {
            var v = (m.energy_mwh || 0) / max;
            var h = Math.max(1, Math.round(H * v));
            return '<rect x="' + (i * (BARW + 1)) + '" y="' + (H - h) +
                '" width="' + BARW + '" height="' + h + '" fill="#67e8f9" opacity="0.85"/>';
        }).join('');
        return '<svg width="' + W + '" height="' + H + '" style="display:block">' + bars + '</svg>';
    }

    function renderFleetKPIs() {
        var row = document.getElementById('fleet-kpi-row');
        var entries = filteredParkEntries();
        if (entries.length === 0) {
            row.innerHTML = '<div style="color:var(--text-muted);padding:1rem">Inga parker matchar filtret.</div>';
            return;
        }
        var monthKey = activeMonthKey();
        var totalCap = 0, totalActual = 0, totalBudget = 0, count = entries.length;
        entries.forEach(function(e) {
            var p = e[1];
            totalCap += (p.capacity_mwp || 0);
            var m = parkMonth(p, monthKey);
            if (m) {
                totalActual += (m.energy_mwh || 0);
                totalBudget += (m.budget_mwh || 0);
            }
        });
        var vsBudget = totalBudget > 0 ? 100 * (totalActual - totalBudget) / totalBudget : null;
        var tiles = [
            kpiTile('Parker', count, ''),
            kpiTile('Installerat', fmtNum(totalCap, 1) + ' MWp', ''),
            kpiTile(htmlEsc(monthKey || '') + ' Energi',
                    fmtNum(totalActual, 0) + ' MWh',
                    'Budget: ' + fmtNum(totalBudget, 0) + ' MWh'),
            kpiTile('vs Budget', fmtPct(vsBudget, 1), '', vsBudgetClass(vsBudget)),
        ];
        row.innerHTML = tiles.join('');
    }

    function renderParkCards() {
        var monthKey = activeMonthKey();
        var grid = document.getElementById('park-cards-grid');
        var entries = filteredParkEntries();
        if (entries.length === 0) {
            grid.innerHTML = '<div style="color:var(--text-muted)">Inga parker matchar filtret.</div>';
            return;
        }
        grid.innerHTML = entries.map(function(e) {
            var pk = e[0], p = e[1];
            var m = parkMonth(p, monthKey);
            var vs = m ? m.vs_budget_pct : null;
            var spark = sparkline(p.months || []);
            var pkEsc = htmlEsc(pk);
            var mkEsc = htmlEsc(monthKey || '-');
            return '<div class="park-card ' + vsBudgetClass(vs) + '" data-park="' + pkEsc + '" onclick="window.assetsOnPark && window.assetsOnPark(\'' + pkEsc + '\')">' +
                '<div class="park-card-head">' +
                    '<div class="park-card-name">' + htmlEsc(p.name || pk) + '</div>' +
                    '<div class="park-card-zone">' + htmlEsc(p.zone || '') + '</div>' +
                '</div>' +
                '<div class="park-card-row"><span>Kapacitet</span><span>' + fmtNum(p.capacity_mwp, 2) + ' MWp</span></div>' +
                '<div class="park-card-row"><span>Energi (' + mkEsc + ')</span><span>' + (m ? fmtNum(m.energy_mwh, 0) + ' MWh' : '–') + '</span></div>' +
                '<div class="park-card-row"><span>Budget</span><span>' + (m ? fmtNum(m.budget_mwh, 0) + ' MWh' : '–') + '</span></div>' +
                '<div class="park-card-row" style="font-weight:700;color:' + vsBudgetColor(vs) + '"><span>vs Budget</span><span>' + (m ? fmtPct(vs) : '–') + '</span></div>' +
                '<div class="park-card-row"><span>Yield</span><span>' + (m ? fmtNum(m.yield_kwh_kwp, 1) + ' kWh/kWp' : '–') + '</span></div>' +
                '<div class="park-card-spark">' + spark + '</div>' +
            '</div>';
        }).join('');
    }

    // ----------------- Drill-down --------------------
    var ASSETS_VIEW_STATE = { mode: 'fleet', selectedPark: null };

    function showFleetMode() {
        ASSETS_VIEW_STATE.mode = 'fleet';
        ASSETS_VIEW_STATE.selectedPark = null;
        document.getElementById('assets-fleet-mode').style.display = '';
        document.getElementById('assets-drilldown-mode').style.display = 'none';
    }
    function showDrilldownMode() {
        ASSETS_VIEW_STATE.mode = 'drilldown';
        document.getElementById('assets-fleet-mode').style.display = 'none';
        document.getElementById('assets-drilldown-mode').style.display = '';
    }

    window.exitDrilldown = function() {
        showFleetMode();
    };

    function trackerGainForMonth(monthKey) {
        if (!ASSETS || !ASSETS.tracker_gain || !ASSETS.tracker_gain.monthly) return null;
        if (!monthKey) return null;
        var yr = parseInt(monthKey.split('-')[0]);
        var mo = parseInt(monthKey.split('-')[1]);
        var rec = ASSETS.tracker_gain.monthly.find(function(r) {
            return r.year === yr && r.month === mo;
        });
        if (!rec) return null;
        return rec.gain_pct != null ? rec.gain_pct : null;
    }

    function captureForZoneMonth(zone, monthKey) {
        if (!ASSETS || !ASSETS.capture_by_zone || !zone || !monthKey) return null;
        var arr = ASSETS.capture_by_zone[zone];
        if (!arr) return null;
        var rec = arr.find(function(r) { return r.month === monthKey; });
        return rec ? rec.capture_eur_mwh : null;
    }

    function captureSeriesForZone(zone, monthKeys) {
        return monthKeys.map(function(k) { return captureForZoneMonth(zone, k); });
    }

    function ensureDrilldownMonthSelect(p, currentMonthKey) {
        var sel = document.getElementById('drilldown-month-select');
        if (!sel) return;
        // Bygg lista över månader som har dagsdata för denna park
        var keys = Object.keys(p.daily_by_month || {}).sort();
        // Fall tillbaka på alla månader om det inte finns dagsdata
        if (keys.length === 0) {
            keys = (p.months || []).map(function(mm) {
                return mm.year + '-' + String(mm.month).padStart(2, '0');
            }).sort();
        }
        var html = keys.slice().reverse().map(function(k) {
            var ke = htmlEsc(k);
            return '<option value="' + ke + '"' + (k === currentMonthKey ? ' selected' : '') + '>' + ke + '</option>';
        }).join('');
        sel.innerHTML = html;
        if (!sel.dataset.bound) {
            sel.addEventListener('change', function() {
                ASSETS_VIEW_STATE.drilldownMonthKey = sel.value;
                renderDrilldown();
            });
            sel.dataset.bound = '1';
        }
    }

    function renderBestWorstDays(p, monthKey) {
        var container = document.getElementById('drilldown-bestworst');
        if (!container) return;
        var days = (p.daily_by_month && p.daily_by_month[monthKey]) || [];
        if (!days.length) {
            container.innerHTML = '<div style="color:var(--text-muted);padding:0.5rem;grid-column:1/-1">Ingen daglig data f&ouml;r ' + htmlEsc(monthKey) + '.</div>';
            return;
        }
        var sorted = days.slice().sort(function(a, b) {
            return (b.energy_mwh || 0) - (a.energy_mwh || 0);
        });
        var top = sorted.slice(0, 5);
        var bottom = sorted.slice(-5).reverse();

        function tableHtml(title, rows, color) {
            var head = '<thead><tr>' +
                '<th style="text-align:left;padding:6px 8px;border-bottom:1px solid var(--border);color:var(--text-muted);font-size:0.7rem;text-transform:uppercase;letter-spacing:0.06em">Datum</th>' +
                '<th style="text-align:left;padding:6px 8px;border-bottom:1px solid var(--border);color:var(--text-muted);font-size:0.7rem;text-transform:uppercase;letter-spacing:0.06em">Veckodag</th>' +
                '<th style="text-align:right;padding:6px 8px;border-bottom:1px solid var(--border);color:var(--text-muted);font-size:0.7rem;text-transform:uppercase;letter-spacing:0.06em">MWh</th>' +
                '<th style="text-align:right;padding:6px 8px;border-bottom:1px solid var(--border);color:var(--text-muted);font-size:0.7rem;text-transform:uppercase;letter-spacing:0.06em">kWh/kWp</th>' +
                '</tr></thead>';
            var body = '<tbody>' + rows.map(function(r) {
                return '<tr>' +
                    '<td style="padding:6px 8px;border-bottom:1px solid var(--border)">' + htmlEsc(r.date || '–') + '</td>' +
                    '<td style="padding:6px 8px;border-bottom:1px solid var(--border);color:var(--text-muted)">' + htmlEsc(r.weekday || '') + '</td>' +
                    '<td style="padding:6px 8px;border-bottom:1px solid var(--border);text-align:right;font-family:var(--font-mono);color:' + color + '">' + fmtNum(r.energy_mwh, 2) + '</td>' +
                    '<td style="padding:6px 8px;border-bottom:1px solid var(--border);text-align:right;font-family:var(--font-mono)">' + fmtNum(r.yield_kwh_kwp, 1) + '</td>' +
                    '</tr>';
            }).join('') + '</tbody>';
            return '<div>' +
                '<div style="font-size:0.78rem;font-weight:700;color:' + color + ';margin-bottom:0.4rem;text-transform:uppercase;letter-spacing:0.06em">' + title + '</div>' +
                '<table style="width:100%;border-collapse:collapse;font-size:0.85rem">' + head + body + '</table>' +
                '</div>';
        }

        container.innerHTML =
            tableHtml('Topp 5', top, '#4ADE80') +
            tableHtml('Botten 5', bottom, '#f87171');
    }

    function renderDrilldown() {
        if (!ASSETS) return;
        var pk = ASSETS_VIEW_STATE.selectedPark;
        var p = ASSETS.parks[pk];
        if (!p) return;

        // Pick month: drilldown-local override → activeMonthKey from filterbar
        var monthKey = ASSETS_VIEW_STATE.drilldownMonthKey || activeMonthKey();
        // If selected month has no data record, drop back to latest available
        if (!parkMonth(p, monthKey)) {
            var available = (p.months || []).map(function(mm) {
                return mm.year + '-' + String(mm.month).padStart(2, '0');
            }).sort();
            if (available.length) monthKey = available[available.length - 1];
        }
        ASSETS_VIEW_STATE.drilldownMonthKey = monthKey;
        var m = parkMonth(p, monthKey);

        ensureDrilldownMonthSelect(p, monthKey);

        // textContent is auto-escaped, but use defensively in case anyone
        // refactors to innerHTML later.
        document.getElementById('drilldown-park-name').textContent = p.name || pk;
        document.getElementById('drilldown-park-zone').textContent = (p.zone || '') + (p.capacity_mwp ? '  ·  ' + fmtNum(p.capacity_mwp, 2) + ' MWp' : '');

        // ---- KPI tiles per design: Energy, vs Budget %, Yield, Capture (zone),
        //      Negative-price hours, Tracker gain (Hova only) ----
        var captureZone = captureForZoneMonth(p.zone, monthKey);
        var trackerPct = trackerGainForMonth(monthKey);
        var isHova = (pk === 'hova');

        var trackerTile;
        if (isHova) {
            trackerTile = kpiTile('Tracker gain',
                trackerPct != null ? fmtPct(trackerPct, 1) : '—',
                'vs SE3 fixed-tilt');
        } else {
            trackerTile = '<div class="assets-kpi" style="opacity:0.5">' +
                '<div class="assets-kpi-label">Tracker gain</div>' +
                '<div class="assets-kpi-value" style="font-size:1.1rem">—</div>' +
                '<div class="assets-kpi-sub">endast Hova</div>' +
                '</div>';
        }

        var kpis = [
            kpiTile('Energi (' + htmlEsc(monthKey) + ')', m ? fmtNum(m.energy_mwh, 0) + ' MWh' : '–'),
            kpiTile('vs Budget',                  m ? fmtPct(m.vs_budget_pct) : '–', '', vsBudgetClass(m && m.vs_budget_pct)),
            kpiTile('Yield',                      m ? fmtNum(m.yield_kwh_kwp, 1) + ' kWh/kWp' : '–'),
            kpiTile('Capture (' + htmlEsc(p.zone || '') + ')',
                    captureZone != null ? fmtNum(captureZone, 1) + ' EUR/MWh' : '–'),
            kpiTile('Negativa pris-timmar',
                    m && m.neg_price_hours != null ? fmtNum(m.neg_price_hours, 0) + ' h' : '–',
                    m && m.neg_price_volume_mwh != null ? fmtNum(m.neg_price_volume_mwh, 0) + ' MWh f&ouml;rlust' : ''),
            trackerTile,
        ];
        document.getElementById('drilldown-kpi-row').innerHTML = kpis.join('');

        var months = (p.months || []).slice();
        var xs = months.map(function(mm) { return mm.year + '-' + String(mm.month).padStart(2, '0'); });

        // Energy vs budget — grouped bars
        Plotly.react('drilldown-energy-chart', [
            { x: xs, y: months.map(function(mm) { return mm.energy_mwh; }), name: 'Faktisk', type: 'bar', marker: { color: '#67e8f9' } },
            { x: xs, y: months.map(function(mm) { return mm.budget_mwh; }), name: 'Budget',  type: 'bar', marker: { color: '#a78bfa', opacity: 0.5 } },
        ], Object.assign({}, PLOTLY_DARK, {
            barmode: 'group',
            yaxis: Object.assign({}, PLOTLY_DARK.yaxis, { title: 'MWh' }),
            margin: { t: 20, b: 60, l: 60, r: 20 },
        }), { responsive: true, displayModeBar: false });

        // Yield 12 mo
        Plotly.react('drilldown-yield-chart', [
            { x: xs, y: months.map(function(mm) { return mm.yield_kwh_kwp; }), type: 'scatter', mode: 'lines+markers', line: { color: '#fde68a' }, name: 'Yield' },
        ], Object.assign({}, PLOTLY_DARK, {
            yaxis: Object.assign({}, PLOTLY_DARK.yaxis, { title: 'kWh/kWp' }),
            margin: { t: 20, b: 60, l: 60, r: 20 },
        }), { responsive: true, displayModeBar: false });

        // Daily Generation — selected month
        var days = (p.daily_by_month && p.daily_by_month[monthKey]) || [];
        if (days.length) {
            var dxs = days.map(function(d) { return d.date; });
            var dys = days.map(function(d) { return d.energy_mwh; });
            var dexp = days.map(function(d) { return d.expected_mwh; });
            Plotly.react('drilldown-daily-chart', [
                { x: dxs, y: dys, name: 'Faktisk', type: 'bar', marker: { color: '#67e8f9' } },
                { x: dxs, y: dexp, name: 'F&ouml;rv&auml;ntad', type: 'scatter', mode: 'lines',
                  line: { color: '#a78bfa', dash: 'dash', width: 2 } },
            ], Object.assign({}, PLOTLY_DARK, {
                yaxis: Object.assign({}, PLOTLY_DARK.yaxis, { title: 'MWh' }),
                margin: { t: 20, b: 60, l: 60, r: 20 },
            }), { responsive: true, displayModeBar: false });
        } else {
            Plotly.purge('drilldown-daily-chart');
            document.getElementById('drilldown-daily-chart').innerHTML =
                '<div style="padding:1.5rem;color:var(--text-muted);text-align:center">Ingen daglig data tillg&auml;nglig f&ouml;r ' + htmlEsc(monthKey) + '.</div>';
        }

        // Capture price for zone (12mo line)
        var capYs = captureSeriesForZone(p.zone, xs);
        Plotly.react('drilldown-capture-chart', [
            { x: xs, y: capYs, type: 'scatter', mode: 'lines+markers',
              line: { color: '#86efac' }, name: 'Capture ' + (p.zone || '') },
        ], Object.assign({}, PLOTLY_DARK, {
            yaxis: Object.assign({}, PLOTLY_DARK.yaxis, { title: 'EUR/MWh' }),
            margin: { t: 20, b: 60, l: 60, r: 20 },
        }), { responsive: true, displayModeBar: false });

        // Best/Worst days table
        renderBestWorstDays(p, monthKey);

        var reportPath = 'performance_' + pk + '_' + (p.zone || '') + '_' + monthKey + '.html';
        var reportPathEsc = htmlEsc(reportPath);
        document.getElementById('drilldown-links').innerHTML =
            '&rarr; <a href="' + reportPathEsc + '" target="_blank" style="color:var(--accent)">' + reportPathEsc + '</a> (om genererad)';
    }

    window.assetsOnPark = function(pk) {
        ASSETS_VIEW_STATE.selectedPark = pk;
        ASSETS_VIEW_STATE.drilldownMonthKey = null; // återställ vid nytt drill-down
        showDrilldownMode();
        renderDrilldown();
    };

    // ----------------- Comparison Table ---------------
    var TABLE_STATE = { sortKey: 'energy_mwh', sortDir: 'desc' };

    function ytdSum(park, monthKey) {
        if (!monthKey) return 0;
        var yr = parseInt(monthKey.split('-')[0]);
        var mo = parseInt(monthKey.split('-')[1]);
        var sum = 0;
        (park.months || []).forEach(function(m) {
            if (m.year === yr && m.month <= mo && m.energy_mwh) sum += m.energy_mwh;
        });
        return sum;
    }

    function tableRows(monthKey) {
        return filteredParkEntries().map(function(e) {
            var pk = e[0], p = e[1];
            var m = parkMonth(p, monthKey);
            return {
                key: pk,
                name: p.name || pk,
                zone: p.zone || '',
                capacity_mwp: p.capacity_mwp || 0,
                energy_mwh: m ? m.energy_mwh : null,
                budget_mwh: m ? m.budget_mwh : null,
                vs_budget_pct: m ? m.vs_budget_pct : null,
                ytd_mwh: ytdSum(p, monthKey),
                yield_kwh_kwp: m ? m.yield_kwh_kwp : null,
            };
        });
    }

    function renderParkTable() {
        var monthKey = activeMonthKey();
        var rows = tableRows(monthKey);
        var dir = TABLE_STATE.sortDir === 'asc' ? 1 : -1;
        var sk = TABLE_STATE.sortKey;
        rows.sort(function(a, b) {
            var av = a[sk], bv = b[sk];
            if (av === null || av === undefined) return 1;
            if (bv === null || bv === undefined) return -1;
            if (typeof av === 'string') return dir * av.localeCompare(bv);
            return dir * (av - bv);
        });

        var cols = [
            { k: 'name',          label: 'Park' },
            { k: 'zone',          label: 'Zon' },
            { k: 'capacity_mwp',  label: 'Cap MWp', fmt: function(v) { return fmtNum(v, 2); } },
            { k: 'energy_mwh',    label: 'MWh (' + htmlEsc(monthKey || '-') + ')', fmt: function(v) { return fmtNum(v, 0); } },
            { k: 'vs_budget_pct', label: 'vs Budget', fmt: fmtPct, color: true },
            { k: 'ytd_mwh',       label: 'YTD MWh', fmt: function(v) { return fmtNum(v, 0); } },
            { k: 'yield_kwh_kwp', label: 'Yield kWh/kWp', fmt: function(v) { return fmtNum(v, 1); } },
        ];

        var head = '<thead><tr>' + cols.map(function(c) {
            var arrow = (c.k === sk) ? (dir > 0 ? ' ▲' : ' ▼') : '';
            return '<th onclick="sortParkTable(\'' + c.k + '\')" style="cursor:pointer;text-align:left;padding:8px;border-bottom:1px solid var(--border);color:var(--text-muted);font-size:0.7rem;text-transform:uppercase;letter-spacing:0.06em">' + c.label + arrow + '</th>';
        }).join('') + '</tr></thead>';

        var body = '<tbody>' + rows.map(function(r) {
            return '<tr style="cursor:pointer" onclick="window.assetsOnPark && window.assetsOnPark(\'' + htmlEsc(r.key) + '\')">' +
                cols.map(function(c) {
                    var color = (c.color) ? ('color:' + vsBudgetColor(r[c.k])) : '';
                    var v = r[c.k];
                    var disp;
                    if (c.fmt) {
                        disp = c.fmt(v);
                    } else if (v == null) {
                        disp = '–';
                    } else if (typeof v === 'string') {
                        // String columns (name, zone) come from data — escape defensively.
                        disp = htmlEsc(v);
                    } else {
                        disp = v;
                    }
                    return '<td style="padding:8px;border-bottom:1px solid var(--border);' + color + '">' + disp + '</td>';
                }).join('') +
            '</tr>';
        }).join('') + '</tbody>';

        document.getElementById('park-comparison-table').innerHTML = head + body;
    }

    window.sortParkTable = function(k) {
        if (TABLE_STATE.sortKey === k) {
            TABLE_STATE.sortDir = TABLE_STATE.sortDir === 'asc' ? 'desc' : 'asc';
        } else {
            TABLE_STATE.sortKey = k;
            TABLE_STATE.sortDir = 'desc';
        }
        renderParkTable();
    };

    window.exportParkTableCsv = function() {
        var monthKey = activeMonthKey();
        var rows = [['Park','Zon','Capacity_MWp','Energy_MWh_' + monthKey,'Budget_MWh','vs_Budget_pct','YTD_MWh','Yield_kWh_kWp']];
        tableRows(monthKey).forEach(function(r) {
            rows.push([r.name, r.zone, r.capacity_mwp, r.energy_mwh, r.budget_mwh, r.vs_budget_pct, r.ytd_mwh, r.yield_kwh_kwp]);
        });
        var csv = rows.map(function(r) {
            return r.map(function(c) {
                if (c == null) return '';
                var s = String(c);
                if (s.indexOf(',') !== -1 || s.indexOf('"') !== -1) {
                    return '"' + s.replace(/"/g, '""') + '"';
                }
                return s;
            }).join(',');
        }).join('\n');
        var blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'park_comparison_' + monthKey + '.csv';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    };

    function initFilters() {
        var msel = document.getElementById('assets-month-select');
        if (msel && !msel.dataset.bound) {
            msel.innerHTML = '<option value="latest">Senaste m&aring;nad</option>' +
                allMonthKeys().slice().reverse().map(function(k) {
                    var ke = htmlEsc(k);
                    return '<option value="' + ke + '">' + ke + '</option>';
                }).join('');
            msel.addEventListener('change', function() {
                FILTER_STATE.monthKey = msel.value;
                renderAssetsAll();
            });
            msel.dataset.bound = '1';
        }
        var zsel = document.getElementById('assets-zone-select');
        if (zsel && !zsel.dataset.bound) {
            zsel.addEventListener('change', function() {
                FILTER_STATE.zone = zsel.value;
                renderAssetsAll();
            });
            zsel.dataset.bound = '1';
        }
    }

    function renderAssetsAll() {
        if (ASSETS_VIEW_STATE.mode === 'drilldown') {
            renderDrilldown();
            return;
        }
        renderFleetKPIs();
        renderParkCards();
        renderParkTable();
    }

    window.renderAssets = function() {
        if (!ASSETS) {
            document.getElementById('assets-view').innerHTML =
                '<div style="padding:2rem;color:var(--text-muted)">Ingen asset-data tillg&auml;nglig.</div>';
            return;
        }
        initFilters();
        renderAssetsAll();
    };
})();
""".strip()


def _merge_data(unified: dict) -> dict:
    """Build a single DATA dict consumed by both v2 and the new ASSETS tab.

    The v2 body reads top-level keys (zones, profiles, data, operations, …);
    we splat market into the root and attach the asset/meta blobs alongside.
    """
    market = unified.get("market", {}) or {}
    merged = dict(market)
    merged["assets"] = unified.get("assets", {})
    merged["meta"] = unified.get("meta", {})
    if "generated" not in merged:
        merged["generated"] = unified.get("generated", "")
    return merged


def _patch_v2_html(html: str) -> str:
    """Apply the surgical edits that turn dashboard_v2 into the unified Track A."""

    # 0. Inject ASSETS CSS just before </style>
    html = html.replace("</style>", ASSETS_CSS + "\n</style>", 1)

    # 1. Update <title>
    html = html.replace(
        "<title>Elpris Dashboard v2</title>",
        "<title>Elpris Unified Dashboard</title>",
        1,
    )

    # 2. Topbar: rename OPERATIONS tab → ASSETS
    html = html.replace(
        '<div class="topbar-title dash-tab" id="tab-operations" onclick="switchDashboard(\'operations\')" style="cursor:pointer"><span>ELPRIS</span> OPERATIONS</div>',
        '<div class="topbar-title dash-tab" id="tab-assets" onclick="switchDashboard(\'assets\')" style="cursor:pointer"><span>ELPRIS</span> ASSETS</div>',
        1,
    )

    # 3. Sidebar block — rename operations-sidebar to assets-sidebar (kept hidden)
    html = html.replace(
        '<aside class="sidebar" id="operations-sidebar" style="display:none"></aside>',
        '<aside class="sidebar" id="assets-sidebar" style="display:none"></aside>',
        1,
    )

    # 4. Replace the entire "<!-- Operations sections -->" block (operations-view div)
    # with the new ASSETS view.
    ops_open = '<!-- Operations sections -->'
    end_marker = '</div>\n        </div>\n    </main>'  # closes operations-view + main wrapper
    if ops_open in html:
        before, _, rest = html.partition(ops_open)
        end_idx = rest.find(end_marker)
        if end_idx != -1:
            after = '</div>\n    </main>' + rest[end_idx + len(end_marker):]
            html = (
                before
                + '<!-- ASSETS sections -->\n        '
                + ASSETS_VIEW_HTML
                + '\n        '
                + after
            )

    # 5. switchDashboard JS — operates on rendered HTML (single braces).
    html = html.replace(
        "['capture', 'bess', 'futures', 'operations'].forEach(t => {",
        "['capture', 'bess', 'futures', 'assets'].forEach(t => {",
        1,
    )
    html = html.replace(
        "document.getElementById('operations-view').style.display = which === 'operations' ? '' : 'none';",
        "document.getElementById('assets-view').style.display = which === 'assets' ? '' : 'none';",
        1,
    )
    html = html.replace(
        "document.getElementById('operations-sidebar').style.display = which === 'operations' ? '' : 'none';",
        "document.getElementById('assets-sidebar').style.display = which === 'assets' ? '' : 'none';",
        1,
    )
    # Disable the now-stale ops-sidebar init (assets-sidebar is empty)
    html = html.replace(
        "if (which === 'operations' && !state.ops_initialized) {",
        "if (false /* assets tab no longer uses ops sidebar */) {",
        1,
    )

    # 6. render() dispatcher — point 'assets' to renderAssets()
    html = html.replace(
        "} else if (state.dashboard === 'operations') {",
        "} else if (state.dashboard === 'assets') {",
        1,
    )
    html = html.replace(
        "        renderOperations();\n    } else {\n        renderForwardCurve();",
        "        renderAssets();\n    } else {\n        renderForwardCurve();",
        1,
    )

    # 7. Inject the ASSETS_JS block just before the GO marker
    html = html.replace(
        "// ================================================================\n// GO\n// ================================================================",
        ASSETS_JS + "\n\n// ================================================================\n// GO\n// ================================================================",
        1,
    )

    return html


def render_track_a(data: dict) -> str:
    """Render the Track A unified dashboard (Bloomberg-dark theme).

    `data` is the dict produced by `elpris.unified_dashboard_data.build_unified_data()`.
    """
    merged = _merge_data(data)
    base = _build_v2_html(merged)
    return _patch_v2_html(base)
