"""Renderare för Electricity Price (huvudversionen, byggd på Översikt).

En fristående HTML-sida på engelska i Primoras profil (verktygsstandarden i
SveaSolarObsidianv2/Projects/Primora-Energy/verktygsstandard.md, referens
Nättariffer). Förslag och beslut: vaultens
Projects/electricity-prices/01-produktversion.md.

Principer (docs/plans/2026-09-22-oversikt-design.md):

* Varje avsnitt öppnar med en mening i klartext; diagrammen är beviset.
* Varje tal visas med enhet, period och jämförelse. Okänt är aldrig noll.
* Status visas med text och ikon, aldrig bara med färg.

Allt som behövs bakas in så att sidan fungerar offline och som mejlbilaga:
typsnitt (woff2), loggor, Iconoir-ikoner, växlaren och Ge feedback
(primora-tema.js, primora-feedback.js) och Plotly (delpaketet cartesian).
Data injiceras som ``const D = …``; all presentation sker i JS nedan.
"""

from __future__ import annotations

import base64
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from ..dashboard_common import esc, script_json

HERE = Path(__file__).parent
ASSETS = HERE / "assets"
WEB = HERE / "web"
PLOTLY_VENDOR = HERE / "vendor" / "plotly-cartesian.min.js"
TOOLS_URL = "https://claude.ai/artifact/WTeshECjaQFDJELpV5ZHRF"
TITLE = "Electricity Price"

FONTS = [
    ("Figtree", 400, "figtree-latin-400-normal.woff2"),
    ("Figtree", 500, "figtree-latin-500-normal.woff2"),
    ("Figtree", 600, "figtree-latin-600-normal.woff2"),
    ("Figtree", 700, "figtree-latin-700-normal.woff2"),
    ("IBM Plex Sans", 400, "ibm-plex-sans-latin-400-normal.woff2"),
    ("IBM Plex Sans", 500, "ibm-plex-sans-latin-500-normal.woff2"),
    ("IBM Plex Sans", 600, "ibm-plex-sans-latin-600-normal.woff2"),
    ("IBM Plex Mono", 400, "ibm-plex-mono-latin-400-normal.woff2"),
]

# Iconoir Regular 7.12.1 (MIT), licensen ligger i assets/iconoir/LICENSE.
ICON_NAMES = ["warning-triangle", "info-circle", "help-circle", "check-circle", "xmark-circle", "xmark",
              "arrow-left", "arrow-right", "download", "nav-arrow-down", "nav-arrow-right", "clock",
              "database", "table-rows", "calendar"]


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


@lru_cache(maxsize=None)
def font_css() -> str:
    out = []
    for family, weight, name in FONTS:
        p = ASSETS / "fonts" / name
        if p.exists():
            out.append(f"@font-face{{font-family:'{family}';font-style:normal;font-weight:{weight};"
                       f"font-display:swap;src:url(data:font/woff2;base64,{_b64(p)}) format('woff2');}}")
    return "\n".join(out)


@lru_cache(maxsize=None)
def icons() -> Dict[str, str]:
    """Ikonernas inre SVG-kod, nyckel = Iconoir-namn."""
    out = {}
    for name in ICON_NAMES:
        p = ASSETS / "iconoir" / f"{name}.svg"
        svg = p.read_text(encoding="utf-8")
        inner = re.sub(r"^.*?<svg[^>]*>|</svg>\s*$", "", svg, flags=re.S).strip()
        out[name] = re.sub(r"\s+", " ", inner)
    return out


def icon_svg(name: str, cls: str = "ikon") -> str:
    return (f'<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" '
            f'aria-hidden="true" focusable="false">{icons()[name]}</svg>')


def _logo(name: str) -> str:
    return f"data:image/png;base64,{_b64(ASSETS / name)}"


def _shared(name: str) -> str:
    return (WEB / name).read_text(encoding="utf-8")


CSS = r"""
/* Primoras profil: samma tokens som Nättariffer (SveaSolar/Nattariffer/web/style.css).
   Två accenter per vy: teal (--accent) för interaktion och primär serie, Warm Yellow (--warn)
   för anmärkningar. Rött (--crit) bara för fel. Hierarki med storlek, vikt och luft. */
:root {
  color-scheme: light;
  --bg: #f5f8f8; --surface: #ffffff; --surface-2: #eaf1f1; --border: #d5e2e3; --field-border: #768f94;
  --hair: #eaf1f1; --ink: #073746; --text: #18171d; --muted: #526c72; --faint: #5b7479;
  --accent: #0b7a83; --accent-ink: #ffffff; --band: #a6d4d1; --band-ink: #073746; --mark: #f4b942;
  --s1: #008e98; --s2: #c98712; --s3: #b3336e; --s4: #5470c2; --s5: #8a7a2a; --s6: #526c72;
  --s-compare: #b0c6c9; --grid: #eaf1f1; --axis: #b0c6c9;
  --hm0: #eaf1f1; --hm1: #008e98; --hm2: #073746;
  --good: #1f7a4d; --good-bg: #e3f3ea; --warn: #7a4f00; --warn-bg: #fff4de;
  --crit: #b42318; --crit-bg: #fde8e7; --info: #415f67; --info-bg: #eaf1f1; --accent-bg: #edf6f6;
  --font-display: "Figtree", "Segoe UI", system-ui, sans-serif;
  --font-sans: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
  --font-mono: "IBM Plex Mono", Consolas, "SFMono-Regular", monospace;
  --radius: 12px; --radius-sm: 8px;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --bg: #042732; --surface: #073746; --surface-2: #0b4250; --border: #1b4d5a; --field-border: #6a98a2; --hair: #0f4452;
    --ink: #eaf1f1; --text: #e4eeee; --muted: #b0c6c9; --faint: #9db6ba;
    --accent: #a6d4d1; --accent-ink: #073746; --band: #0b4250; --band-ink: #eaf1f1; --mark: #f4b942;
    --s1: #179aa2; --s2: #bf8820; --s3: #d0508a; --s4: #6784d4; --s5: #8b9536; --s6: #b0c6c9;
    --s-compare: #4d7a84; --grid: #0f4452; --axis: #2a5f6b;
    --hm0: #0b4250; --hm1: #179aa2; --hm2: #eaf1f1;
    --good: #7fd4a8; --good-bg: #123f35; --warn: #f4c462; --warn-bg: #3d3314;
    --crit: #ff9b90; --crit-bg: #4a1f24; --info: #b0c6c9; --info-bg: #0f4452; --accent-bg: #0e4a55;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --bg: #042732; --surface: #073746; --surface-2: #0b4250; --border: #1b4d5a; --field-border: #6a98a2; --hair: #0f4452;
  --ink: #eaf1f1; --text: #e4eeee; --muted: #b0c6c9; --faint: #9db6ba;
  --accent: #a6d4d1; --accent-ink: #073746; --band: #0b4250; --band-ink: #eaf1f1; --mark: #f4b942;
  --s1: #179aa2; --s2: #bf8820; --s3: #d0508a; --s4: #6784d4; --s5: #8b9536; --s6: #b0c6c9;
  --s-compare: #4d7a84; --grid: #0f4452; --axis: #2a5f6b;
  --hm0: #0b4250; --hm1: #179aa2; --hm2: #eaf1f1;
  --good: #7fd4a8; --good-bg: #123f35; --warn: #f4c462; --warn-bg: #3d3314;
  --crit: #ff9b90; --crit-bg: #4a1f24; --info: #b0c6c9; --info-bg: #0f4452; --accent-bg: #0e4a55;
}

* { box-sizing: border-box; }
[hidden] { display: none !important; }
html { -webkit-text-size-adjust: 100%; scroll-padding-top: 72px; }
body { margin: 0; background: var(--bg); color: var(--text); font-family: var(--font-sans); font-size: 16px; line-height: 1.5; }
h1, h2, h3, h4, nav, button, label, summary, th, .display { font-family: var(--font-display); }
h1, h2, h3, h4 { color: var(--ink); text-wrap: balance; margin: 0; line-height: 1.2; }
h2 { font-size: 1.75rem; font-weight: 700; letter-spacing: -0.015em; }
h3 { font-size: 1.125rem; font-weight: 700; }
h4 { font-size: 1rem; font-weight: 600; }
p { margin: 0; }
a { color: var(--accent); text-underline-offset: 2px; }
:where(a, button, input, select, summary, [tabindex]):focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.num, td.n, th.n { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
.muted { color: var(--muted); }
code { font-family: var(--font-mono); font-size: 1em; }
.ikon { width: 20px; height: 20px; flex: none; display: inline-block; vertical-align: -4px; }
.vh { position: absolute !important; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
.hoppa { position: absolute; left: 16px; top: -60px; z-index: 50; background: var(--surface); color: var(--ink); padding: 10px 14px; border-radius: var(--radius-sm); font-family: var(--font-display); font-weight: 600; }
.hoppa:focus { top: 12px; }
main:focus { outline: none; }
.wrap { max-width: 1240px; margin: 0 auto; padding-inline: 24px; }

/* Sidhuvud */
.band { background: var(--band); color: var(--band-ink); }
.band .wrap { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-block: 16px; }
.brand { display: flex; align-items: center; gap: 16px; min-width: 0; }
.brand .home { display: block; flex: none; border-radius: 4px; }
.brand img { height: 24px; width: auto; display: block; }
.brand .logo-dark { display: none; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) .brand .logo-light { display: none; } :root:not([data-theme="light"]) .brand .logo-dark { display: block; } }
:root[data-theme="dark"] .brand .logo-light { display: none; }
:root[data-theme="dark"] .brand .logo-dark { display: block; }
.brand h1 { font-family: var(--font-display); font-weight: 600; font-size: 1.125rem; letter-spacing: -0.01em; color: var(--band-ink); padding-left: 16px; border-left: 1px solid color-mix(in srgb, var(--band-ink) 25%, transparent); white-space: nowrap; }
.band-end { display: flex; align-items: center; gap: 10px; }
.fb-slot, .tema-slot { display: flex; color: var(--band-ink); }

.tabs { background: var(--surface); border-bottom: 1px solid var(--border); position: sticky; top: env(safe-area-inset-top, 0px); z-index: 10; }
.tabs ul { list-style: none; margin: 0; padding: 0; display: flex; gap: 4px; overflow-x: auto; scrollbar-width: none; }
.tabs li { flex: none; }
.tabs a { display: inline-flex; align-items: center; gap: 6px; line-height: 49px; padding: 0 14px; font-family: var(--font-display); font-size: 15px; font-weight: 600; color: var(--muted); text-decoration: none; border-bottom: 3px solid transparent; margin-bottom: -1px; }
.tabs a:hover { color: var(--ink); }
.tabs a[aria-current="true"] { color: var(--ink); border-bottom-color: var(--accent); }
.tabs a:focus-visible { outline-offset: -4px; }
.tabs .count { font-family: var(--font-mono); font-size: 13px; font-weight: 400; color: var(--warn); background: var(--warn-bg); border-radius: 6px; padding: 0 6px; line-height: 20px; }

.stand { display: flex; flex-wrap: wrap; gap: 4px 18px; padding-top: 20px; color: var(--muted); font-size: 14px; }
.stand b { font-family: var(--font-mono); font-weight: 400; color: var(--text); }

/* Avsnitt */
main { padding-bottom: 64px; }
section.view { padding-top: 40px; display: grid; gap: 20px; }
section.view + section.view { margin-top: 24px; border-top: 1px solid var(--border); }
.vyhuvud { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-end; gap: 12px 24px; }
.vyhuvud .scope { color: var(--muted); font-size: 14px; margin-top: 4px; }
.lede { font-family: var(--font-sans); font-size: 1.25rem; line-height: 1.45; max-width: 68ch; color: var(--text); }
.lede b, .lede .num { color: var(--ink); font-weight: 600; }
.lede .num { font-weight: 400; }
.note { font-size: 15px; color: var(--muted); max-width: 90ch; }
.controls { display: flex; flex-wrap: wrap; gap: 10px 16px; align-items: center; }
.field { display: inline-flex; align-items: center; gap: 8px; }
.field > span, .field > label { font-family: var(--font-display); font-size: 15px; font-weight: 600; color: var(--ink); }
.valj { position: relative; display: inline-block; }
.valj::after { content: ""; position: absolute; right: 12px; top: 50%; width: 18px; height: 18px; margin-top: -9px; pointer-events: none; background: var(--muted);
  -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.5'%3E%3Cpath d='M6 9L12 15L18 9' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") center / contain no-repeat;
  mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.5'%3E%3Cpath d='M6 9L12 15L18 9' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") center / contain no-repeat; }
select { font: inherit; font-size: 16px; color: var(--text); min-height: 44px; background: var(--surface); border: 1px solid var(--field-border); border-radius: var(--radius-sm); padding: 9px 40px 9px 12px; appearance: none; max-width: 100%; }

.btn { display: inline-flex; align-items: center; justify-content: center; gap: 8px; min-height: 42px; font: inherit; font-family: var(--font-display); font-size: 15px; font-weight: 600; line-height: 1.2;
  border: 1px solid var(--field-border); background: var(--surface); color: var(--ink); border-radius: var(--radius-sm); padding: 9px 16px; cursor: pointer; text-decoration: none; white-space: nowrap; }
.btn:hover { background: var(--surface-2); }
.btn .ikon { width: 18px; height: 18px; }
.btn.lank { background: none; border: 0; color: var(--accent); padding: 4px 2px; min-height: 0; text-decoration: underline; text-underline-offset: 3px; }
.seg { display: inline-flex; border: 1px solid var(--field-border); border-radius: var(--radius-sm); overflow: hidden; background: var(--surface); flex-wrap: wrap; }
.seg button { font: inherit; font-family: var(--font-display); font-size: 15px; font-weight: 600; border: 0; background: transparent; color: var(--muted); padding: 9px 14px; cursor: pointer; min-height: 42px; }
.seg button + button { border-left: 1px solid var(--field-border); }
.seg button[aria-pressed="true"] { background: var(--ink); color: var(--surface); }
.seg button:focus-visible { outline-offset: -4px; }
.chip { display: inline-flex; align-items: center; gap: 8px; font: inherit; font-family: var(--font-display); font-size: 15px; font-weight: 600; border: 1px solid var(--field-border);
  background: var(--surface); color: var(--muted); border-radius: var(--radius-sm); padding: 7px 12px; cursor: pointer; min-height: 42px; }
.chip[aria-pressed="true"] { color: var(--ink); border-color: var(--ink); background: var(--surface-2); }
.chip svg.linje { width: 26px; height: 10px; flex: none; }
.chip[aria-pressed="false"] svg.linje { opacity: .45; }

/* Status: text och ikon, aldrig bara färg */
.status { display: inline-flex; align-items: center; gap: 6px; border-radius: 6px; padding: 2px 9px; font-family: var(--font-display); font-size: 14px; font-weight: 600; line-height: 22px; white-space: nowrap; background: var(--surface-2); color: var(--muted); }
.status .ikon { width: 16px; height: 16px; }
.status.ok { background: var(--good-bg); color: var(--good); }
.status.warn { background: var(--warn-bg); color: var(--warn); }
.status.crit { background: var(--crit-bg); color: var(--crit); }
.inc { display: inline-flex; vertical-align: -2px; margin-left: 4px; color: var(--warn); }
.inc .ikon { width: 16px; height: 16px; }

.callout { background: var(--warn-bg); color: var(--text); border-radius: var(--radius-sm); padding: 12px 16px; display: flex; gap: 12px; align-items: flex-start; max-width: 100ch; }
.callout .ikon { color: var(--warn); margin-top: 2px; }
.callout.info { background: var(--info-bg); }
.callout.info .ikon { color: var(--info); }
.callout.crit { background: var(--crit-bg); }
.callout.crit .ikon { color: var(--crit); }
.callout strong { font-family: var(--font-display); color: var(--ink); }

/* ?-knapp */
.hjalp-wrap { position: relative; display: inline-flex; vertical-align: middle; }
.hjalp { display: inline-grid; place-items: center; width: 28px; height: 28px; border: 0; border-radius: 50%; background: transparent; color: var(--muted); cursor: pointer; padding: 0; }
.hjalp:hover, .hjalp[aria-expanded="true"] { color: var(--ink); background: var(--surface-2); }
.hjalp .ikon { width: 18px; height: 18px; }
.hjalp-ruta { position: absolute; top: calc(100% + 6px); left: 0; z-index: 30; width: min(340px, calc(100vw - 32px)); background: var(--surface); color: var(--text); border: 1px solid var(--border);
  border-radius: var(--radius-sm); box-shadow: 0 10px 30px rgba(7, 55, 70, .18); padding: 12px 14px; font-family: var(--font-sans); font-size: 15px; font-weight: 400; line-height: 1.45; text-align: left; white-space: normal; }
.hjalp-ruta strong { font-family: var(--font-display); color: var(--ink); display: block; margin-bottom: 2px; }

/* Nyckeltal */
.kpis { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); }
.kpi { padding: 18px 20px; min-width: 0; }
.kpi + .kpi { border-left: 1px solid var(--border); }
.kpi .label { display: flex; align-items: center; gap: 2px; font-family: var(--font-display); font-size: 15px; font-weight: 600; color: var(--ink); min-height: 28px; }
.kpi .value { font-family: var(--font-mono); font-size: 1.875rem; line-height: 1.15; color: var(--ink); margin: 6px 0 4px; letter-spacing: -0.02em; white-space: nowrap; }
.kpi .value small { font-size: 15px; color: var(--muted); letter-spacing: 0; }
.kpi .sub { font-size: 14px; color: var(--muted); }
.kpi .sub .num { color: var(--text); }
@media (max-width: 1000px) { .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } .kpi + .kpi { border-left: 0; } .kpi { border-top: 1px solid var(--border); } .kpi:nth-child(-n+2) { border-top: 0; } .kpi:nth-child(even) { border-left: 1px solid var(--border); } }

/* Kort och tabeller */
.card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 22px 24px; min-width: 0; display: grid; gap: 14px; align-content: start; }
.card > header { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-start; gap: 8px 16px; }
.card > header p { color: var(--muted); font-size: 15px; margin-top: 2px; max-width: 70ch; }
.grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 480px), 1fr)); gap: 20px; }
.grid-2 > * { min-width: 0; }
.tablewrap { overflow-x: auto; position: relative; }
table { border-collapse: collapse; width: 100%; font-size: 15px; }
thead th { color: var(--muted); font-size: 14px; font-weight: 600; text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border); white-space: nowrap; vertical-align: bottom; }
thead th .u { display: block; font-family: var(--font-sans); font-weight: 400; font-size: 13px; color: var(--muted); }
tbody td, tbody th[scope="row"] { padding: 10px 12px; border-top: 1px solid var(--hair); vertical-align: top; }
tbody th[scope="row"] { text-align: left; font-family: var(--font-sans); font-weight: 400; color: var(--text); white-space: nowrap; }
tbody tr:first-child > td, tbody tr:first-child > th { border-top: 0; }
td.n, th.n { text-align: right; white-space: nowrap; }
thead th.n { font-family: var(--font-display); }
tr.grupp th { text-align: left; padding: 18px 12px 6px; font-family: var(--font-display); font-size: 15px; font-weight: 700; color: var(--ink); border-top: 0; }
tr.total > td, tr.total > th { font-weight: 600; color: var(--ink); border-top: 2px solid var(--ink); }
tr.total > th[scope="row"] { font-family: var(--font-display); }
.tag { font-size: 14px; color: var(--muted); margin-left: 6px; font-family: var(--font-sans); }
th .sortera { font: inherit; color: inherit; background: none; border: 0; padding: 0; cursor: pointer; display: inline-flex; flex-direction: column; align-items: inherit; text-align: inherit; }
th.n .sortera { align-items: flex-end; }
th .sortera:hover { color: var(--ink); }
th[aria-sort] .sortera { color: var(--ink); }
tr.park th[scope="row"] a { font-family: var(--font-display); font-weight: 600; color: var(--ink); text-decoration: none; }
tr.park th[scope="row"] a:hover { text-decoration: underline; }
tr.park:hover > * { background: var(--surface-2); }
.selected > * { background: var(--accent-bg); }

/* Dagremsa: datatäckning per dag (hel stapel, halv stapel, kontur) */
.strip { display: inline-flex; align-items: flex-end; gap: 1.5px; height: 16px; vertical-align: middle; margin-left: 10px; }
.strip i { display: block; width: 3.5px; border-radius: 1px; }
.strip i.ok { height: 16px; background: var(--muted); }
.strip i.part { height: 8px; background: var(--muted); }
.strip i.miss { height: 16px; background: transparent; box-shadow: inset 0 0 0 1px var(--crit); }
.strip i.none { height: 3px; background: var(--grid); }
.legend-row { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 14px; color: var(--muted); align-items: center; }
.legend-row .strip { margin-left: 6px; height: 14px; }
.legend-row .strip i.ok, .legend-row .strip i.miss { height: 14px; } .legend-row .strip i.part { height: 7px; }

/* Diagram */
figure { margin: 0; min-width: 0; display: grid; gap: 8px; }
figcaption h3 { font-size: 1.0625rem; }
figcaption p { color: var(--muted); font-size: 15px; margin-top: 2px; }
.plot { height: 320px; width: 100%; }
.plot.tall { height: 380px; }
.plot .fallback { font-size: 15px; color: var(--muted); padding: 12px 0; }
details.data summary { cursor: pointer; color: var(--accent); font-size: 15px; font-weight: 600; display: inline-flex; align-items: center; gap: 6px; list-style: none; }
details.data summary::-webkit-details-marker { display: none; }
details.data summary .ikon { width: 18px; height: 18px; transition: transform .15s; }
details.data[open] summary .ikon { transform: rotate(90deg); }
details.data .tablewrap { margin-top: 8px; max-height: 420px; overflow: auto; }
details.data table { font-size: 14px; }

/* Parkens vy */
.back { display: inline-flex; align-items: center; gap: 6px; font-family: var(--font-display); font-weight: 600; font-size: 15px; text-decoration: none; }
.facts { color: var(--muted); font-size: 15px; }
dl.om { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr)); gap: 12px 24px; margin: 0; }
dl.om div { min-width: 0; }
dl.om dt { font-family: var(--font-display); font-size: 14px; font-weight: 600; color: var(--muted); }
dl.om dd { margin: 2px 0 0; }

/* Data */
dl.defs { margin: 0; display: grid; gap: 14px; }
dl.defs dt { font-family: var(--font-display); font-weight: 700; color: var(--ink); }
dl.defs dd { margin: 2px 0 0; color: var(--text); max-width: 90ch; }
ul.issues { margin: 0; padding: 0; list-style: none; display: grid; gap: 10px; }
footer { padding: 24px 0 56px; color: var(--muted); font-size: 14px; border-top: 1px solid var(--border); }

@media (max-width: 600px) {
  .wrap { padding-inline: 16px; }
  .band .wrap { padding-block: 12px; }
  .brand { gap: 12px; }
  .brand h1 { padding-left: 12px; font-size: 1rem; }
  h2 { font-size: 1.5rem; }
  .lede { font-size: 1.125rem; }
  .kpi { padding: 14px 14px; }
  .kpi .value { font-size: 1.5rem; }
  .card { padding: 18px 16px; }
  .plot { height: 280px; }
  .plot.tall { height: 320px; }
}
@media (max-width: 480px) {
  .brand { gap: 10px; }
  .brand h1 { white-space: normal; font-size: 15px; line-height: 1.1; padding-left: 10px; max-width: 80px; }
  .band-end { gap: 6px; }
}
@media print { .tabs, .band-end, details.data, .controls, .btn { display: none !important; } section.view { break-inside: avoid-page; } }
"""

BODY = r"""
<a class="hoppa" href="#innehall">Skip to content</a>
<header class="band">
  <div class="wrap">
    <div class="brand">
      <a class="home" href="__TOOLS_URL__" target="_top" aria-label="Primora, to Primora Tools">
        <img class="logo-light" src="__LOGO_NAVY__" alt="" width="141" height="24">
        <img class="logo-dark" src="__LOGO_AQUA__" alt="" width="141" height="24">
      </a>
      <h1>Electricity Price</h1>
    </div>
    <div class="band-end"><div class="tema-slot" id="tema"></div><div class="fb-slot" id="feedback"></div></div>
  </div>
</header>
<nav class="tabs" aria-label="Sections">
  <div class="wrap"><ul>
    <li><a href="#portfolio" data-sec="portfolio">Portfolio</a></li>
    <li><a href="#market" data-sec="market">Market</a></li>
    <li><a href="#futures" data-sec="futures">Futures</a></li>
    <li><a href="#battery" data-sec="battery">Battery</a></li>
    <li><a href="#data" data-sec="data" id="nav-data">Data</a></li>
  </ul></div>
</nav>
<main id="innehall" tabindex="-1">
  <div class="wrap">
    <p class="stand" id="stand"></p>
    <div id="main-view">
      <section class="view" id="portfolio" aria-labelledby="portfolio-h">
        <div class="vyhuvud">
          <div><h2 id="portfolio-h">Portfolio</h2><p class="scope" id="p-scope"></p></div>
          <div class="controls"><div class="field"><label for="month">Month</label><span class="valj"><select id="month"></select></span></div></div>
        </div>
        <p class="lede" id="p-lede"></p>
        <div id="p-flags"></div>
        <div class="kpis" id="p-kpis"></div>
        <div class="card">
          <header><div><h3>Parks</h3><p>Select a park to see its months and days. Sort by any column.</p></div>
            <button type="button" class="btn" id="p-export" hidden></button></header>
          <div class="tablewrap"><table id="p-table"></table></div>
          <div class="legend-row" id="p-legend"></div>
          <p class="status-line note" id="p-export-status" role="status" aria-live="polite"></p>
        </div>
        <div class="grid-2">
          <figure class="card">
            <figcaption><h3>Production by month</h3><p>Bars show metered production for all parks; hatched bars have less than 95% data coverage. The line marks the budget for the same time with metered data.</p></figcaption>
            <div class="plot" id="p-months"></div>
            <details class="data" id="p-months-d"><summary></summary><div class="tablewrap" id="p-months-tbl"></div></details>
          </figure>
          <figure class="card">
            <figcaption><h3>What the power was worth</h3><p>Portfolio capture price against the spot price in the parks' zones, weighted by production. EUR/MWh.</p></figcaption>
            <div class="plot" id="p-value"></div>
            <details class="data"><summary></summary><div class="tablewrap" id="p-value-tbl"></div></details>
          </figure>
        </div>
      </section>

      <section class="view" id="market" aria-labelledby="market-h">
        <div class="vyhuvud"><div><h2 id="market-h">Market</h2><p class="scope" id="m-scope"></p></div></div>
        <p class="lede" id="m-lede"></p>
        <div class="controls" id="m-controls"></div>
        <div class="grid-2">
          <figure class="card">
            <figcaption><h3>Spot price by month</h3><p>Average day-ahead price. EUR/MWh.</p></figcaption>
            <div class="plot" id="m-price"></div>
            <details class="data"><summary></summary><div class="tablewrap" id="m-price-tbl"></div></details>
          </figure>
          <figure class="card">
            <figcaption><h3>Solar capture rate by month</h3><p>What solar power earned as a share of the month's average spot price. Winter months are left out.</p></figcaption>
            <div class="plot" id="m-capture"></div>
            <details class="data"><summary></summary><div class="tablewrap" id="m-capture-tbl"></div></details>
          </figure>
        </div>
        <div class="card">
          <header><div><h3>By year</h3><p id="m-year-note"></p></div></header>
          <div class="grid-2" id="m-years"></div>
          <p class="note" id="m-spread"></p>
        </div>
        <div class="card">
          <header><div><h3>When in the day power is cheap</h3><p id="hm-note"></p></div>
            <div class="controls" id="hm-controls"></div></header>
          <div class="plot tall" id="m-heatmap" role="img"></div>
          <details class="data"><summary></summary><div class="tablewrap" id="m-heatmap-tbl"></div></details>
        </div>
        <div class="card">
          <header><div><h3>Capture by panel design</h3><p id="pc-note"></p></div><div class="controls" id="pc-controls"></div></header>
          <div class="tablewrap" id="pc-table"></div>
          <div class="plot" id="pc-chart"></div>
        </div>
      </section>

      <section class="view" id="futures" aria-labelledby="futures-h">
        <div class="vyhuvud"><div><h2 id="futures-h">Futures</h2><p class="scope" id="f-scope"></p></div></div>
        <p class="lede" id="f-lede"></p>
        <div id="f-flags"></div>
        <div class="grid-2" id="f-tables"></div>
        <p class="note" id="f-tables-note"></p>
        <figure class="card">
          <figcaption><h3 id="f-chart-title">Area price over time</h3><p>Area price = system price (SYS) + area differential (EPAD). EUR/MWh. Shaded periods have no recorded prices.</p></figcaption>
          <div class="controls" id="f-contracts" role="group" aria-label="Contract"></div>
          <div class="plot tall" id="f-history"></div>
          <details class="data"><summary></summary><div class="tablewrap" id="f-history-tbl"></div></details>
        </figure>
        <div class="card">
          <header><div><h3>What the market expected, and what it got</h3><p>Last area price before delivery started, against the average spot price during the quarter.</p></div></header>
          <div class="tablewrap" id="f-convergence"></div>
        </div>
        <div class="card" id="nm-card">
          <header><div><h3>All Nordic zones</h3><p id="nm-status"></p></div></header>
          <div class="controls" id="nm-controls"></div>
          <div class="tablewrap"><table id="nm-forward"></table></div>
          <p class="note">Select a delivery period to compare it with history below. A dash means no complete price: the area differential (EPAD) is missing, and the system price is never used in its place.</p>
        </div>
        <div class="grid-2">
          <div class="card">
            <header><div><h3 id="nm-cmp-title">Forward against history</h3><p>Forward area price against the time-weighted spot price (baseload) in the same completed period earlier.</p></div></header>
            <p id="nm-insight"></p>
            <div class="tablewrap"><table id="nm-comparison"></table></div>
            <div class="plot" id="nm-chart"></div>
          </div>
          <div class="card">
            <header><div><h3>Zone spreads</h3><p>How the difference between zones is priced now, against the same difference in the historical period.</p></div></header>
            <div class="controls" id="nm-anchor-c"></div>
            <div class="tablewrap"><table id="nm-spreads"></table></div>
            <p class="note">A historical difference is not a fair forward price. Weather, fuel prices, grid limits, new production and risk premiums can all justify a change.</p>
          </div>
        </div>
      </section>

      <section class="view" id="battery" aria-labelledby="battery-h">
        <div class="vyhuvud"><div><h2 id="battery-h">Battery</h2><p class="scope" id="b-scope"></p></div></div>
        <p class="lede" id="b-lede"></p>
        <div class="controls" id="b-controls" role="group" aria-label="Bidding zones"></div>
        <div class="grid-2">
          <figure class="card">
            <figcaption><h3>Daily spread by month</h3><p>The day's 2 most expensive hours minus its 2 cheapest, monthly average. EUR/MWh.</p></figcaption>
            <div class="plot" id="b-spread"></div>
            <details class="data"><summary></summary><div class="tablewrap" id="b-spread-tbl"></div></details>
          </figure>
          <figure class="card">
            <figcaption><h3>Arbitrage cap by month</h3><p>1 MW / 2 MWh, one cycle per day, perfect foresight. EUR per MW.</p></figcaption>
            <div class="plot" id="b-rev"></div>
            <details class="data"><summary></summary><div class="tablewrap" id="b-rev-tbl"></div></details>
          </figure>
        </div>
        <div class="card">
          <header><div><h3>Arbitrage cap by year</h3><p>EUR per MW of battery power.</p></div></header>
          <div class="tablewrap" id="b-years"></div>
          <p class="note" id="b-notes"></p>
        </div>
        <div class="card">
          <header><div><h3>Ancillary services</h3><p id="anc-note"></p></div><div class="controls" id="anc-controls"></div></header>
          <div class="callout info" id="anc-caveat"></div>
          <div class="grid-2">
            <div class="tablewrap" id="anc-table"></div>
            <figure><div class="plot" id="anc-chart"></div>
              <details class="data"><summary></summary><div class="tablewrap" id="anc-chart-tbl"></div></details></figure>
          </div>
        </div>
      </section>

      <section class="view" id="data" aria-labelledby="data-h">
        <div class="vyhuvud"><div><h2 id="data-h">Data</h2><p class="scope" id="d-scope"></p></div></div>
        <p class="lede" id="d-lede"></p>
        <div class="grid-2">
          <div class="card"><header><div><h3>Known issues</h3></div></header><ul class="issues" id="d-issues"></ul></div>
          <div class="card"><header><div><h3>Sources and latest data</h3></div></header><div class="tablewrap" id="d-sources"></div></div>
        </div>
        <div class="card"><header><div><h3>How we calculate</h3></div></header><dl class="defs" id="d-defs"></dl></div>
        <div class="card"><header><div><h3>Not shown, and why</h3></div></header><dl class="defs" id="d-left"></dl></div>
      </section>
    </div>
    <div id="park-view" hidden></div>
  </div>
</main>
<footer><div class="wrap" id="footer"></div></footer>
"""

JS = r"""
document.documentElement.lang = 'en';
// ---------- format (English: decimal point, narrow no-break space for thousands, U+2212 minus) ----------
const NN = ' ', MINUS = '−';
const MSHORT = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const MLONG = ['January','February','March','April','May','June','July','August','September','October','November','December'];
const ZONE_NAMES = {SE1: 'SE1 Luleå', SE2: 'SE2 Sundsvall', SE3: 'SE3 Stockholm', SE4: 'SE4 Malmö', DK1: 'DK1 West Denmark', DK2: 'DK2 East Denmark', SYS: 'System price'};
// Zone -> fixed colour token, line style and marker, so series are distinguishable without colour.
const ZSTYLE = {SE3: ['--s1', 'solid', 'circle'], SE4: ['--s2', 'dash', 'square'], SE1: ['--s4', 'dot', 'diamond'], SE2: ['--s5', 'dashdot', 'triangle-up'],
  DK1: ['--s3', 'longdash', 'x'], DK2: ['--s6', 'longdashdot', 'star'], SYS: ['--s6', 'dot', 'circle-open']};
function isNum(v) { return v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v)); }
function fmt(v, d) {
  if (!isNum(v)) return '–';
  d = d || 0;
  const n = Number(v);
  const s = Math.abs(n).toLocaleString('en-US', {minimumFractionDigits: d, maximumFractionDigits: d}).replace(/,/g, NN);
  return (n < 0 && /[1-9]/.test(s) ? MINUS : '') + s;
}
function signed(v, d) { if (!isNum(v)) return '–'; const s = fmt(v, d); return (Number(v) > 0 && /[1-9]/.test(s) ? '+' : '') + s; }
function pct(v, d, sign) { if (!isNum(v)) return '–'; d = d === undefined ? 0 : d; return (sign ? signed(v * 100, d) : fmt(v * 100, d)) + '%'; }
function eur(v, d) { return isNum(v) ? fmt(v, d === undefined ? 1 : d) + ' EUR/MWh' : '–'; }
function money(v) { return isNum(v) ? fmt(v, 0) + ' EUR' : '–'; }
// Only the figure itself is set in Plex Mono; units and words stay in the text face.
function num(s) { return String(s).replace(/^([+−\-]?[\d .,]+%?)(.*)$/, '<span class="num">$1</span>$2'); }
function mLabel(mk, long) { const [y, m] = mk.split('-'); return (long ? MLONG : MSHORT)[+m - 1] + ' ' + y; }
function dLabel(day) { if (!day) return '–'; const [y, m, d] = day.split('-'); return (+d) + ' ' + MSHORT[+m - 1] + ' ' + y; }
function dShort(day) { if (!day) return '–'; const [y, m, d] = day.split('-'); return (+d) + ' ' + MSHORT[+m - 1]; }
function esc(s) { return String(s === null || s === undefined ? '' : s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'})[c]); }
function el(id) { return document.getElementById(id); }
function icon(name) { return '<svg class="ikon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true" focusable="false">' + (ICONS[name] || '') + '</svg>'; }
function words(v, d, unit, up, down) {
  if (!isNum(v)) return '–';
  if (Math.abs(v) < Math.pow(10, -(d || 0)) / 2) return 'unchanged';
  return fmt(Math.abs(v), d) + (unit || '') + ' ' + (v > 0 ? (up || 'up') : (down || 'down'));
}
function callout(text, kind) { return '<div class="callout ' + (kind || '') + '">' + icon(kind === 'info' ? 'info-circle' : 'warning-triangle') + '<div>' + text + '</div></div>'; }
function incMark(title) { return '<span class="inc" title="' + esc(title) + '">' + icon('warning-triangle') + '<span class="vh">' + esc(title) + '</span></span>'; }
function statusBadge(s) {
  const map = {ok: ['ok', 'check-circle', 'Current'], gammal: ['warn', 'clock', 'Behind'], saknas: ['crit', 'xmark-circle', 'Missing']};
  const m = map[s] || map.saknas;
  return '<span class="status ' + m[0] + '">' + icon(m[1]) + m[2] + '</span>';
}

// ---------- glossary and ?-buttons ----------
const GLOSS = {}; (D.definitions || []).forEach(d => { GLOSS[d[0]] = {term: d[1], text: d[2]}; });
function help(key) {
  const g = GLOSS[key]; if (!g) return '';
  return '<span class="hjalp-wrap"><button type="button" class="hjalp" aria-expanded="false" data-help="' + key + '" aria-label="What is ' + esc(g.term.toLowerCase()) + '?">' + icon('help-circle') + '</button></span>';
}
function closeHelp() { document.querySelectorAll('.hjalp-ruta').forEach(n => n.remove()); document.querySelectorAll('.hjalp[aria-expanded="true"]').forEach(b => b.setAttribute('aria-expanded', 'false')); }
document.addEventListener('click', e => {
  const b = e.target.closest('.hjalp');
  if (!b) { if (!e.target.closest('.hjalp-ruta')) closeHelp(); return; }
  const open = b.getAttribute('aria-expanded') === 'true';
  closeHelp();
  if (open) return;
  const g = GLOSS[b.dataset.help];
  const box = document.createElement('div');
  box.className = 'hjalp-ruta'; box.setAttribute('role', 'note');
  box.innerHTML = '<strong>' + esc(g.term) + '</strong>' + g.text;
  b.parentNode.appendChild(box);
  const r = box.getBoundingClientRect();
  if (r.right > document.documentElement.clientWidth - 8) { box.style.left = 'auto'; box.style.right = '0'; }
  b.setAttribute('aria-expanded', 'true');
});
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeHelp(); });

// ---------- charts: Plotly theme built from the same tokens as the CSS ----------
function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
function zc(z) { return css((ZSTYLE[z] || ['--s6'])[0]) || '#888'; }
function zline(z, width) { const s = ZSTYLE[z] || ['--s6', 'solid']; return {color: css(s[0]), width: width || 2, dash: s[1]}; }
function zmarker(z, size) { const s = ZSTYLE[z] || ['--s6', 'solid', 'circle']; return {color: css(s[0]), size: size || 6, symbol: s[2]}; }
const PLOT_CFG = {displayModeBar: false, responsive: true};
function layout(extra) {
  const mono = {family: css('--font-mono'), size: 13, color: css('--muted')};
  const base = {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: {family: css('--font-display'), size: 13, color: css('--muted')},
    margin: {l: 60, r: 16, t: 12, b: 44}, separators: '. ', showlegend: false,
    hovermode: 'x unified',
    hoverlabel: {bgcolor: css('--surface'), bordercolor: css('--border'), font: {family: css('--font-mono'), color: css('--text'), size: 13}},
    legend: {orientation: 'h', x: 0, y: 1.14, font: {family: css('--font-display'), size: 13, color: css('--text')}},
    xaxis: {gridcolor: css('--grid'), linecolor: css('--axis'), tickcolor: css('--axis'), tickfont: mono, zeroline: false, showgrid: false, fixedrange: true},
    yaxis: {gridcolor: css('--grid'), linecolor: css('--axis'), zerolinecolor: css('--axis'), tickfont: mono, zeroline: true, fixedrange: true, rangemode: 'tozero',
      tickformat: ',.0f', title: {font: {family: css('--font-display'), size: 13, color: css('--muted')}, standoff: 8}},
  };
  for (const k in (extra || {})) {
    if (extra[k] && typeof extra[k] === 'object' && !Array.isArray(extra[k]) && base[k]) {
      base[k] = Object.assign({}, base[k], extra[k]);
      if (extra[k].title && base[k].title !== extra[k].title) base[k].title = Object.assign({font: {family: css('--font-display'), size: 13, color: css('--muted')}, standoff: 8}, extra[k].title);
    } else base[k] = extra[k];
  }
  return base;
}
const RENDERERS = [];
function safe(fn) { try { fn(); } catch (e) { console.error(e); } }
function draw(fn) { RENDERERS.push(fn); safe(fn); }
function redrawAll() { RENDERERS.forEach(safe); }
function plot(id, data, lay, label) {
  const node = el(id);
  if (!node) return;
  if (label) { node.setAttribute('role', 'img'); node.setAttribute('aria-label', label); }
  if (!window.Plotly) { node.innerHTML = '<p class="fallback">The chart could not load. The figures are under "Show data".</p>'; node.style.height = 'auto'; return; }
  Plotly.react(node, data, lay, PLOT_CFG);
}
window.addEventListener('primora-tema', () => redrawAll());
if (window.matchMedia) window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => redrawAll());
new MutationObserver(() => redrawAll()).observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
function monthTicks(months) { return months.map((m, i) => (i === 0 || m.slice(5) === '01') ? MSHORT[+m.slice(5) - 1] + '<br>' + m.slice(0, 4) : MSHORT[+m.slice(5) - 1]); }
// Month category axis: always horizontal labels; in narrow windows only every third month is labelled.
function monthAxis(months) {
  const step = document.documentElement.clientWidth < 600 ? 3 : 1;
  const ticks = monthTicks(months).map((t, i) => (i % step === 0 || i === months.length - 1) ? t : '');
  return {type: 'category', tickmode: 'array', tickvals: months, ticktext: ticks, tickangle: 0};
}
let LAST_W = window.innerWidth;
window.addEventListener('resize', () => { if ((LAST_W < 600) !== (window.innerWidth < 600)) { LAST_W = window.innerWidth; redrawAll(); } });

// Tables: header row with scope, first cell as row header, numbers right-aligned in mono.
function table(head, rows, opts) {
  opts = opts || {};
  const numCols = opts.num || head.map((_, i) => i > 0);
  return '<table>' + (opts.caption ? '<caption class="vh">' + esc(opts.caption) + '</caption>' : '') + '<thead><tr>' +
    head.map((h, i) => '<th scope="col"' + (numCols[i] ? ' class="n"' : '') + '>' + h + '</th>').join('') + '</tr></thead><tbody>' +
    rows.map(r => '<tr>' + r.map((c, i) => i === 0 ? '<th scope="row">' + c + '</th>' : '<td' + (numCols[i] ? ' class="n"' : '') + '>' + c + '</td>').join('') + '</tr>').join('') +
    '</tbody></table>';
}
function showData() { document.querySelectorAll('details.data > summary').forEach(s => { if (!s.innerHTML) s.innerHTML = icon('nav-arrow-right') + 'Show data'; }); }

// ---------- state and shareable address ----------
const P = D.portfolj || {}, M = D.marknad || {}, F = D.terminer || {}, B = D.batteri || {}, S = D.datastatus || {}, X = D.tillagg || {};
const SECTIONS = ['portfolio', 'market', 'futures', 'battery', 'data'];
const STATE = {sec: 'portfolio', park: null, m: P.default_month, zones: new Set(M.main_zones || ['SE3', 'SE4']), range: '36', contract: null,
  bzones: new Set((M.main_zones || ['SE3', 'SE4'])), hmZone: 'SE3', hmYear: null, pcZone: 'SE3', ancZone: 'SE3', ancKey: null,
  nkind: 'year', ncontract: null, nbench: null, nanchor: 'SE4', sort: {key: null, dir: -1}};
function readHash() {
  let h = decodeURIComponent(location.hash.slice(1) || '');
  let sec = h, q = '';
  if (h.includes('?')) { [sec, q] = h.split('?'); } else if (h.includes('=')) { sec = ''; q = h; }
  const p = new URLSearchParams(q);
  if (p.get('m') && P.portfolio && P.portfolio[p.get('m')]) STATE.m = p.get('m');
  if (sec === 'park' || p.get('park')) { const k = p.get('p') || p.get('park'); if (P.parks && P.parks[k]) { STATE.park = k; sec = 'park'; } }
  if (p.get('zones')) { const z = p.get('zones').split(',').filter(x => (M.zones || []).includes(x)); if (z.length) STATE.zones = new Set(z); }
  if (p.get('range') === 'all') STATE.range = 'all';
  if (p.get('c')) STATE.contract = p.get('c');
  if (p.get('kind') && ['year', 'quarter', 'month'].includes(p.get('kind'))) STATE.nkind = p.get('kind');
  if (p.get('nc')) STATE.ncontract = p.get('nc');
  if (p.get('bz')) { const z = p.get('bz').split(',').filter(x => (B.zones || []).includes(x)); if (z.length) STATE.bzones = new Set(z); }
  STATE.sec = SECTIONS.includes(sec) || sec === 'park' ? sec : 'portfolio';
}
function hashFor(sec) {
  const p = new URLSearchParams();
  if (sec === 'park') { p.set('p', STATE.park); p.set('m', STATE.m); }
  if (sec === 'portfolio' && STATE.m !== P.default_month) p.set('m', STATE.m);
  if (sec === 'market') { const z = Array.from(STATE.zones).join(','); if (z !== (M.main_zones || []).join(',')) p.set('zones', z); if (STATE.range === 'all') p.set('range', 'all'); }
  if (sec === 'futures') { if (STATE.contract && STATE.contract !== F.default_contract) p.set('c', STATE.contract); if (STATE.nkind !== 'year') p.set('kind', STATE.nkind); if (STATE.ncontract) p.set('nc', STATE.ncontract); }
  if (sec === 'battery') { const z = Array.from(STATE.bzones).join(','); if (z !== (M.main_zones || []).join(',')) p.set('bz', z); }
  const s = p.toString();
  return '#' + sec + (s ? '?' + s : '');
}
function writeHash(sec, push) {
  STATE.sec = sec;
  try { history[push ? 'pushState' : 'replaceState'](null, '', hashFor(sec)); } catch (e) { /* embedded view */ }
}
function scrollToSec(sec) { const t = el(sec); if (t) window.scrollTo({top: t.getBoundingClientRect().top + window.scrollY - 64, behavior: 'auto'}); }
function markNav(sec) { document.querySelectorAll('.tabs a').forEach(a => a.setAttribute('aria-current', String(a.dataset.sec === sec))); }
document.querySelectorAll('.tabs a').forEach(a => a.addEventListener('click', e => {
  e.preventDefault();
  if (STATE.park) closePark(false);
  writeHash(a.dataset.sec, true); markNav(a.dataset.sec); scrollToSec(a.dataset.sec);
  const h = el(a.dataset.sec + '-h'); if (h) { h.setAttribute('tabindex', '-1'); h.focus({preventScroll: true}); }
}));
if ('IntersectionObserver' in window) {
  const io = new IntersectionObserver(entries => {
    if (STATE.park) return;
    entries.forEach(en => { if (en.isIntersecting) { markNav(en.target.id); if (STATE.sec !== en.target.id) { STATE.sec = en.target.id; try { history.replaceState(null, '', hashFor(en.target.id)); } catch (e) {} } } });
  }, {rootMargin: '-80px 0px -70% 0px'});
  SECTIONS.forEach(s => { const n = el(s); if (n) io.observe(n); });
}
window.addEventListener('popstate', () => { readHash(); if (STATE.sec === 'park') openPark(STATE.park, false); else { closePark(false); renderPortfolio(); scrollToSec(STATE.sec); } });

// =====================================================================
// Header line: what each source runs to
// =====================================================================
function renderStand() {
  const n = (S.issues || []).length;
  el('stand').innerHTML = '<span>Parks to <b>' + dLabel(P.data_end) + '</b></span><span>Spot to <b>' + dLabel(M.data_end) + '</b></span>' +
    '<span>Futures to <b>' + dLabel(F.latest_date) + '</b></span><span>Prices in EUR/MWh, Swedish time</span>';
  if (n) el('nav-data').innerHTML = 'Data <span class="count" aria-label="' + n + ' known issues">' + n + '</span>';
}

// =====================================================================
// Portfolio
// =====================================================================
const PARK_KEYS = Object.keys(P.parks || {});
function monthName(mk) { const pm = P.portfolio[mk]; return mLabel(mk, true) + (pm && pm.partial ? ' (to ' + dShort(P.data_end) + ')' : ''); }
function monthOptions() {
  const sel = el('month');
  sel.innerHTML = P.months.slice().reverse().map(mk => '<option value="' + mk + '"' + (mk === STATE.m ? ' selected' : '') + '>' + monthName(mk) + '</option>').join('');
  sel.addEventListener('change', () => { STATE.m = sel.value; writeHash('portfolio'); renderPortfolio(); });
}
function renderPortfolio() {
  const mk = STATE.m, pm = P.portfolio[mk], y = P.ytd[mk];
  if (!pm) { el('p-lede').textContent = 'No park data for this month.'; return; }
  el('month').value = mk;
  const name = k => P.parks[k].info.name;
  const excl = pm.parks_excluded.map(name);
  el('p-scope').textContent = 'Eight solar parks in SE3 and SE4 · ' + monthName(mk);
  let s = 'In ' + monthName(mk) + ' the portfolio produced <b>' + num(fmt(pm.energy_mwh) + NN + 'MWh') + '</b>';
  if (isNum(pm.vs_budget)) s += ', <b>' + num(words(pm.vs_budget * 100, 1, '%', 'above', 'below')) + ' budget</b> for the time with metered data';
  s += '. ';
  if (isNum(pm.capture_eur)) s += 'The power was worth <b>' + num(eur(pm.capture_eur)) + '</b> on the spot market, <b>' + num(pct(pm.capture_ratio)) + '</b> of the average spot price.';
  el('p-lede').innerHTML = s;
  el('p-flags').innerHTML = excl.length ? callout('<strong>' + esc(excl.join(', ')) + '</strong> ' + (excl.length === 1 ? 'has' : 'have') +
    ' metered data for less than 80% of daylight and ' + (excl.length === 1 ? 'is' : 'are') + ' left out of the budget comparison. Measured production still counts in the total.') : '';
  const ytdName = 'Year to date (Jan–' + MSHORT[+mk.slice(5) - 1] + ')';
  const kpis = [
    {label: 'Production', help: 'production', value: fmt(pm.energy_mwh), unit: 'MWh', sub: ytdName + ': ' + num(fmt(y.energy_mwh) + NN + 'MWh')},
    {label: 'Versus budget', help: 'vs_budget', value: pct(pm.vs_budget, 1, true), unit: '',
     sub: pm.parks_included.length + ' of ' + (pm.parks_included.length + pm.parks_excluded.length) + ' parks · year to date ' + num(pct(y.vs_budget, 1, true))},
    {label: 'Spot value', help: 'spot_value', value: fmt(pm.value_eur), unit: 'EUR', sub: ytdName + ': ' + num(money(y.value_eur))},
    {label: 'Capture price', help: 'capture_price', value: fmt(pm.capture_eur, 1), unit: 'EUR/MWh', sub: num(pct(pm.capture_ratio)) + ' of spot (' + num(eur(pm.baseload_mix_eur)) + ')' + help('capture_ratio')},
    {label: 'Data coverage', help: 'coverage', value: pct(pm.coverage), unit: '', sub: 'Unknown, not zero · year to date ' + num(pct(y.coverage))},
  ];
  el('p-kpis').innerHTML = kpis.map(k => '<div class="kpi"><div class="label">' + k.label + help(k.help) + '</div><div class="value">' + k.value +
    (k.unit ? ' <small>' + k.unit + '</small>' : '') + '</div><div class="sub">' + k.sub + '</div></div>').join('');
  renderParkTable();
  renderPortfolioTrend();
}
function stripHtml(k, mk) {
  const days = P.parks[k].days[mk] || [];
  const c = {ok: 0, part: 0, miss: 0, none: 0};
  const bars = days.map(d => {
    let cls = 'none';
    if (isNum(d.coverage)) cls = d.coverage >= 0.95 ? 'ok' : (d.coverage >= 0.5 ? 'part' : 'miss');
    c[cls]++;
    return '<i class="' + cls + '" title="' + dShort(d.date) + ': ' + (isNum(d.coverage) ? pct(d.coverage) + ' coverage, ' + fmt(d.energy_mwh, 1) + NN + 'MWh' : 'no daylight data') + '"></i>';
  }).join('');
  return '<span class="strip" role="img" aria-label="Days: ' + c.ok + ' complete, ' + c.part + ' partial, ' + c.miss + ' missing">' + bars + '</span>';
}
const COLS = [['name', 'Park', '', false], ['zone', 'Zone', '', false], ['energy', 'Production', 'MWh', true], ['vs', 'Versus budget', 'time with data', true],
  ['yield', 'Specific yield', 'kWh/kWp', true], ['capture', 'Capture price', 'EUR/MWh', true], ['ratio', 'Capture rate', 'of spot price', true], ['cov', 'Data coverage', 'daylight · by day', true]];
function parkRow(k, mk) {
  const p = P.parks[k], m = p.months[mk];
  const link = '<a href="#park?p=' + k + '&m=' + mk + '" data-park="' + k + '">' + esc(p.info.name) + '</a>' + (p.info.type === 'tracker' ? '<span class="tag">tracker</span>' : '');
  if (!m) return {k, html: '<tr class="park"><th scope="row">' + link + '</th><td>' + p.info.zone + '</td><td colspan="6" class="muted">No data for this month</td></tr>', v: {name: p.info.name, zone: p.info.zone}};
  const low = isNum(m.coverage) && m.coverage < P.rules.good_coverage;
  const wm = low ? incMark('Incomplete data: the value is probably too low') : '';
  const vs = isNum(m.vs_budget) ? pct(m.vs_budget, 1, true) : '<span class="muted">too little data</span>';
  const html = '<tr class="park"><th scope="row">' + link + '</th><td>' + p.info.zone + '</td>' +
    '<td class="n">' + fmt(m.energy_mwh) + wm + '</td><td class="n">' + vs + '</td><td class="n">' + fmt(m.yield_kwh_kwp, 0) + wm + '</td>' +
    '<td class="n">' + fmt(m.capture_eur, 1) + '</td><td class="n">' + pct(m.capture_ratio) + '</td><td class="n">' + pct(m.coverage) + stripHtml(k, mk) + '</td></tr>';
  return {k, html, v: {name: p.info.name, zone: p.info.zone, energy: m.energy_mwh, vs: m.vs_budget, yield: m.yield_kwh_kwp, capture: m.capture_eur, ratio: m.capture_ratio, cov: m.coverage}};
}
function renderParkTable() {
  const mk = STATE.m, pm = P.portfolio[mk], SORT = STATE.sort;
  let rows = PARK_KEYS.map(k => parkRow(k, mk)), body = '';
  if (SORT.key) {
    rows.sort((a, b) => {
      const x = a.v[SORT.key], y = b.v[SORT.key];
      if (x === undefined || x === null) return 1;
      if (y === undefined || y === null) return -1;
      return (x > y ? 1 : x < y ? -1 : 0) * SORT.dir;
    });
    body = rows.map(r => r.html).join('');
  } else {
    ['SE4', 'SE3'].forEach(z => { const zr = rows.filter(r => P.parks[r.k].info.zone === z); if (zr.length) body += '<tr class="grupp"><th colspan="8" scope="rowgroup">' + ZONE_NAMES[z] + '</th></tr>' + zr.map(r => r.html).join(''); });
  }
  body += '<tr class="total"><th scope="row">Portfolio</th><td></td><td class="n">' + fmt(pm.energy_mwh) + '</td><td class="n">' + pct(pm.vs_budget, 1, true) + '</td><td class="n">' +
    fmt(pm.yield_kwh_kwp, 0) + '</td><td class="n">' + fmt(pm.capture_eur, 1) + '</td><td class="n">' + pct(pm.capture_ratio) + '</td><td class="n">' + pct(pm.coverage) + '</td></tr>';
  el('p-table').innerHTML = '<caption class="vh">Parks, ' + esc(monthName(mk)) + '</caption><thead><tr>' + COLS.map(c => '<th scope="col"' + (c[3] ? ' class="n"' : '') +
    (SORT.key === c[0] ? ' aria-sort="' + (SORT.dir > 0 ? 'ascending' : 'descending') + '"' : '') + '><button type="button" class="sortera" data-k="' + c[0] + '">' + c[1] +
    (c[2] ? '<span class="u">' + c[2] + '</span>' : '') + '</button></th>').join('') + '</tr></thead><tbody>' + body + '</tbody>';
  el('p-table').querySelectorAll('button.sortera').forEach(b => b.addEventListener('click', () => {
    const k = b.dataset.k;
    if (SORT.key === k) { if (SORT.dir === -1) SORT.dir = 1; else SORT.key = null; } else { SORT.key = k; SORT.dir = (k === 'name' || k === 'zone') ? 1 : -1; }
    renderParkTable();
    const again = el('p-table').querySelector('button.sortera[data-k="' + k + '"]'); if (again) again.focus();
  }));
  el('p-table').querySelectorAll('a[data-park]').forEach(a => a.addEventListener('click', e => { e.preventDefault(); openPark(a.dataset.park, true); }));
  el('p-legend').innerHTML = '<span>Data coverage by day:</span><span>Complete<span class="strip" aria-hidden="true"><i class="ok"></i></span></span>' +
    '<span>Partial (50–95%)<span class="strip" aria-hidden="true"><i class="part"></i></span></span><span>Missing<span class="strip" aria-hidden="true"><i class="miss"></i></span></span>' +
    '<span>' + icon('warning-triangle') + ' Under 95% coverage: the value is probably too low</span>';
}
let TREND = false;
function renderPortfolioTrend() {
  const fn = () => {
    const months = P.months.filter(x => x <= STATE.m).slice(-13), pm = m => P.portfolio[m];
    plot('p-months', [
      {type: 'bar', name: 'Metered production', x: months, y: months.map(m => pm(m).energy_mwh),
       marker: {color: css('--s1'), pattern: {shape: months.map(m => pm(m).coverage >= 0.95 ? '' : '/'), bgcolor: css('--accent-bg'), fgcolor: css('--s1'), solidity: 0.3}, line: {color: css('--s1'), width: 1}},
       customdata: months.map(m => [pct(pm(m).coverage), mLabel(m)]), hovertemplate: '%{customdata[1]}: %{y:,.0f} MWh · coverage %{customdata[0]}<extra></extra>'},
      {type: 'scatter', mode: 'markers', name: 'Budget for time with data', x: months, y: months.map(m => pm(m).budget_obs_mwh),
       marker: {symbol: 'line-ew', size: 24, line: {width: 3, color: css('--ink')}}, hovertemplate: 'budget %{y:,.0f} MWh<extra></extra>'},
    ], layout({xaxis: monthAxis(months), yaxis: {title: {text: 'MWh'}}, bargap: 0.35, showlegend: true, margin: {l: 60, r: 16, t: 36, b: 48}}),
    'Portfolio production by month against budget');
    el('p-months-tbl').innerHTML = table(['Month', 'Production<span class="u">MWh</span>', 'Budget, time with data<span class="u">MWh</span>', 'Versus budget', 'Data coverage'],
      months.slice().reverse().map(m => [mLabel(m), fmt(pm(m).energy_mwh), fmt(pm(m).budget_obs_mwh), pct(pm(m).vs_budget, 1, true), pct(pm(m).coverage)]));
    plot('p-value', [
      {type: 'scatter', mode: 'lines+markers', name: 'Spot price', x: months, y: months.map(m => pm(m).baseload_mix_eur), line: {color: css('--muted'), width: 2, dash: 'dash'}, marker: {size: 6, symbol: 'square', color: css('--muted')},
       hovertemplate: 'spot %{y:,.1f} EUR/MWh<extra></extra>'},
      {type: 'scatter', mode: 'lines+markers', name: 'Capture price', x: months, y: months.map(m => pm(m).capture_eur), line: {color: css('--s1'), width: 2.5}, marker: {size: 7, color: css('--s1')},
       customdata: months.map(m => [pct(pm(m).capture_ratio)]), hovertemplate: 'capture %{y:,.1f} EUR/MWh (%{customdata[0]})<extra></extra>'},
    ], layout({xaxis: monthAxis(months), yaxis: {title: {text: 'EUR/MWh'}}, showlegend: true, margin: {l: 60, r: 16, t: 36, b: 48}}),
    'Portfolio capture price against spot price by month');
    el('p-value-tbl').innerHTML = table(['Month', 'Capture price<span class="u">EUR/MWh</span>', 'Spot price<span class="u">EUR/MWh</span>', 'Capture rate'],
      months.slice().reverse().map(m => [mLabel(m), fmt(pm(m).capture_eur, 1), fmt(pm(m).baseload_mix_eur, 1), pct(pm(m).capture_ratio)]));
  };
  if (!TREND) { TREND = true; draw(fn); } else fn();
}

// ---------- CSV export of the park table (downloads capability on claude.ai, a normal download elsewhere) ----------
let DOWNLOADS = null;
function csvCell(v) { if (v === null || v === undefined) return ''; const s = String(v); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; }
function parkCsv() {
  const mk = STATE.m;
  const head = ['Month', 'Park', 'Zone', 'Production MWh', 'Versus budget %', 'Specific yield kWh/kWp', 'Capture price EUR/MWh', 'Capture rate %', 'Data coverage %', 'Partial month'];
  const rows = PARK_KEYS.map(k => { const p = P.parks[k], m = p.months[mk] || {};
    const r = (v, d) => isNum(v) ? Number(v).toFixed(d) : '';
    return [mk, p.info.name, p.info.zone, r(m.energy_mwh, 1), isNum(m.vs_budget) ? r(m.vs_budget * 100, 1) : '', r(m.yield_kwh_kwp, 1), r(m.capture_eur, 2),
      isNum(m.capture_ratio) ? r(m.capture_ratio * 100, 1) : '', isNum(m.coverage) ? r(m.coverage * 100, 1) : '', m.partial ? 'yes' : 'no']; });
  return [head].concat(rows).map(r => r.map(csvCell).join(',')).join('\r\n') + '\r\n';
}
async function exportCsv() {
  const name = 'electricity-price-parks-' + STATE.m + '.csv', data = parkCsv(), st = el('p-export-status');
  if (DOWNLOADS) {
    try { await DOWNLOADS.save({filename: name, data}); st.textContent = 'Saved ' + name + '.'; }
    catch (e) { st.textContent = e && e.code === 'declined' ? 'Export cancelled.' : 'The file could not be saved here.'; }
    return;
  }
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob(['﻿' + data], {type: 'text/csv;charset=utf-8'}));
  a.download = name; document.body.appendChild(a); a.click(); a.remove();
  st.textContent = 'Downloaded ' + name + '.';
}
(function setupExport() {
  const b = el('p-export');
  b.innerHTML = icon('download') + 'Export CSV';
  b.addEventListener('click', exportCsv);
  if (window.claude && typeof window.claude.use === 'function') {
    window.claude.use('downloads').then(d => { DOWNLOADS = d; b.hidden = !d; }).catch(() => { b.hidden = true; });
  } else b.hidden = false;
})();

// =====================================================================
// A park (own view)
// =====================================================================
const FACT_LABELS = [['location', 'Location'], ['commissioning_date', 'Commissioned'], ['module_type', 'Modules'], ['module_wp', 'Module rating', ' Wp'], ['num_modules', 'Number of modules'],
  ['inverter_manufacturer', 'Inverter make'], ['inverter_model', 'Inverter model'], ['num_inverters', 'Number of inverters'], ['tilt_angle', 'Tilt', '°'], ['azimuth', 'Azimuth', '°'],
  ['tracking_type', 'Tracking'], ['ac_capacity_mwac', 'AC capacity', ' MW'], ['grid_limit_mwac', 'Grid limit', ' MW'], ['transformer_capacity_kva', 'Transformer', ' kVA'], ['expected_annual_yield_kwh_kwp', 'Expected annual yield', ' kWh/kWp']];
function openPark(k, push) {
  if (!P.parks[k]) return;
  STATE.park = k;
  el('main-view').hidden = true; el('park-view').hidden = false;
  markNav('portfolio');
  writeHash('park', push);
  renderParkView();
  window.scrollTo({top: 0, behavior: 'auto'});
  const h = el('park-h'); if (h) h.focus({preventScroll: true});
}
function closePark(push) {
  if (!STATE.park) return;
  const k = STATE.park; STATE.park = null;
  el('park-view').hidden = true; el('main-view').hidden = false;
  if (push !== false) { writeHash('portfolio', push); scrollToSec('portfolio'); const a = el('p-table').querySelector('a[data-park="' + k + '"]'); if (a) a.focus({preventScroll: true}); }
}
function renderParkView() {
  const k = STATE.park, p = P.parks[k], info = p.info, mk = STATE.m, m = p.months[mk], y = p.ytd[mk];
  const facts = (X.park_facts || {})[k] || {};
  const issues = (S.issues || []).filter(i => i.park === info.name || i.park === 'All parks' || (i.park || '').split(', ').includes(info.name));
  const opts = Object.keys(p.months).slice().reverse().map(x => '<option value="' + x + '"' + (x === mk ? ' selected' : '') + '>' + monthName(x) + '</option>').join('');
  let lede = '';
  if (m) {
    lede = 'In ' + monthName(mk) + ' ' + esc(info.name) + ' produced <b>' + num(fmt(m.energy_mwh) + NN + 'MWh') + '</b>';
    lede += isNum(m.vs_budget) ? ', <b>' + num(words(m.vs_budget * 100, 1, '%', 'above', 'below')) + ' budget</b> for the time with metered data.' :
      '. Data coverage was ' + num(pct(m.coverage)) + ', too low for a budget comparison.';
    lede += ' Its power was worth ' + num(eur(m.capture_eur)) + ', ' + num(pct(m.capture_ratio)) + ' of the spot price in ' + info.zone + '.';
  } else lede = 'No data for ' + esc(info.name) + ' in ' + monthName(mk) + '.';
  const fullDays = (p.days[mk] || []).filter(d => isNum(d.coverage) && d.coverage >= 0.95 && isNum(d.budget_mwh) && d.budget_mwh > 0);
  const ranked = fullDays.slice().sort((a, b) => b.energy_mwh - a.energy_mwh);
  const dayRows = list => list.map(d => [dLabel(d.date), fmt(d.energy_mwh, 1), fmt(d.budget_mwh, 1), pct(d.energy_mwh / d.budget_mwh - 1, 0, true)]);
  const factItems = FACT_LABELS.filter(f => facts[f[0]] !== null && facts[f[0]] !== undefined && facts[f[0]] !== '').map(f => {
    let v = facts[f[0]]; if (typeof v === 'number') v = fmt(v, Number.isInteger(v) ? 0 : (v < 10 ? 2 : 1)); else if (typeof v === 'boolean') v = v ? 'Yes' : 'No';
    return '<div><dt>' + f[1] + '</dt><dd' + (typeof facts[f[0]] === 'number' ? ' class="num"' : '') + '>' + esc(v) + esc(f[2] || '') + '</dd></div>'; }).join('');
  el('park-view').innerHTML = '<section class="view" aria-labelledby="park-h">' +
    '<a class="back" href="' + hashFor('portfolio') + '" id="pk-back">' + icon('arrow-left') + 'Portfolio</a>' +
    '<div class="vyhuvud"><div><h2 id="park-h" tabindex="-1">' + esc(info.name) + '</h2><p class="facts">' +
      [info.zone, fmt(info.kwp / 1000, 1) + NN + 'MWp', info.type === 'tracker' ? 'single-axis tracker' : 'fixed mounting', info.grid_limit_mw ? 'grid limit ' + fmt(info.grid_limit_mw, 1) + NN + 'MW' : null,
       'data since ' + dLabel(info.first_data)].filter(Boolean).join(' · ') + '</p></div>' +
      '<div class="controls"><div class="field"><label for="pk-month">Month</label><span class="valj"><select id="pk-month">' + opts + '</select></span></div></div></div>' +
    '<p class="lede">' + lede + '</p>' + issues.map(i => callout(esc(i.text))).join('') +
    '<div class="grid-2"><figure class="card"><figcaption><h3>Production by month</h3><p>Last 13 months. Hatched bars have incomplete data; grey bars have too little data for a budget comparison. The line marks the budget for the time with data.</p></figcaption><div class="plot" id="pk-months"></div></figure>' +
    '<figure class="card"><figcaption><h3>Production by day, ' + mLabel(mk, true) + '</h3><p>Hatched bars are incomplete days. The line marks each day\'s budget.</p></figcaption><div class="plot" id="pk-days"></div>' +
      '<details class="data"><summary></summary><div class="tablewrap" id="pk-days-tbl"></div></details></figure></div>' +
    '<div class="card"><header><div><h3>Month and year to date</h3><p>Year to date compares only months with at least 80% data coverage against budget; the budget column then shows the budget for those measured periods.</p></div></header><div class="tablewrap">' +
      table(['Period', 'Production<span class="u">MWh</span>', 'Budget<span class="u">time with data, MWh</span>', 'Versus budget' + help('vs_budget'), 'Specific yield<span class="u">kWh/kWp</span>', 'Capture price<span class="u">EUR/MWh</span>', 'Data coverage'],
        [m ? [monthName(mk), fmt(m.energy_mwh), fmt(m.budget_obs_mwh), pct(m.vs_budget, 1, true), fmt(m.yield_kwh_kwp, 0), fmt(m.capture_eur, 1), pct(m.coverage)] : null,
         y ? ['Year to date', fmt(y.energy_mwh), fmt(y.compared_budget_mwh), pct(y.vs_budget, 1, true), fmt(y.yield_kwh_kwp, 0), fmt(y.capture_eur, 1), pct(y.coverage)] : null].filter(Boolean)) + '</div></div>' +
    (ranked.length >= 6 ? '<div class="grid-2"><div class="card"><header><div><h3>Best days</h3><p>Ranked by production among days with complete data.</p></div></header><div class="tablewrap">' +
      table(['Day', 'Production<span class="u">MWh</span>', 'Budget<span class="u">MWh</span>', 'Versus budget'], dayRows(ranked.slice(0, 3))) + '</div></div>' +
      '<div class="card"><header><div><h3>Weakest days</h3><p>Low production on a complete day usually means weather; check the day chart.</p></div></header><div class="tablewrap">' +
      table(['Day', 'Production<span class="u">MWh</span>', 'Budget<span class="u">MWh</span>', 'Versus budget'], dayRows(ranked.slice(-3).reverse())) + '</div></div></div>' : '') +
    (factItems ? '<div class="card"><header><div><h3>About this park</h3></div></header><dl class="om">' + factItems + '</dl></div>' : '') + '</section>';
  el('pk-back').addEventListener('click', e => { e.preventDefault(); closePark(true); });
  el('pk-month').addEventListener('change', e => { STATE.m = e.target.value; writeHash('park'); renderParkView(); renderPortfolio(); });
  showData();
  const months = Object.keys(p.months).filter(x => x <= mk).slice(-13);
  const pat = cov => !isNum(cov) || cov < 0.8 ? '' : (cov < 0.95 ? '/' : '');
  const col = cov => !isNum(cov) || cov < 0.8 ? css('--s-compare') : css('--s1');
  plot('pk-months', [
    {type: 'bar', name: 'Metered', x: months, y: months.map(x => p.months[x].energy_mwh),
     marker: {color: months.map(x => col(p.months[x].coverage)), pattern: {shape: months.map(x => pat(p.months[x].coverage)), bgcolor: css('--accent-bg'), fgcolor: css('--s1'), solidity: 0.3}},
     customdata: months.map(x => [pct(p.months[x].coverage), pct(p.months[x].vs_budget, 1, true), mLabel(x)]),
     hovertemplate: '%{customdata[2]}: %{y:,.0f} MWh · coverage %{customdata[0]} · versus budget %{customdata[1]}<extra></extra>'},
    {type: 'scatter', mode: 'markers', name: 'Budget, time with data', x: months, y: months.map(x => p.months[x].budget_obs_mwh),
     marker: {symbol: 'line-ew', size: 24, line: {width: 3, color: css('--ink')}}, hovertemplate: 'budget %{y:,.0f} MWh<extra></extra>'},
  ], layout({xaxis: monthAxis(months), yaxis: {title: {text: 'MWh'}}, bargap: 0.35, margin: {l: 60, r: 16, t: 12, b: 48}}),
  info.name + ' production by month');
  const days = p.days[mk] || [];
  plot('pk-days', [
    {type: 'bar', name: 'Metered', x: days.map(d => d.date), y: days.map(d => d.energy_mwh),
     marker: {color: days.map(d => !isNum(d.coverage) || d.coverage < 0.5 ? css('--s-compare') : css('--s1')), pattern: {shape: days.map(d => isNum(d.coverage) && d.coverage >= 0.5 && d.coverage < 0.95 ? '/' : ''), bgcolor: css('--accent-bg'), fgcolor: css('--s1'), solidity: 0.3}},
     customdata: days.map(d => [pct(d.coverage)]), hovertemplate: '%{y:,.1f} MWh · coverage %{customdata[0]}<extra></extra>'},
    {type: 'scatter', mode: 'markers', name: 'Budget', x: days.map(d => d.date), y: days.map(d => d.budget_mwh),
     marker: {symbol: 'line-ew', size: 10, line: {width: 2.5, color: css('--ink')}}, hovertemplate: 'budget %{y:,.1f} MWh<extra></extra>'},
  ], layout({xaxis: {type: 'date', tickformat: '%-d %b', dtick: 7 * 86400000, hoverformat: '%-d %b %Y'}, yaxis: {title: {text: 'MWh'}}, bargap: 0.25}), info.name + ' production by day');
  el('pk-days-tbl').innerHTML = table(['Day', 'Production<span class="u">MWh</span>', 'Budget<span class="u">MWh</span>', 'Data coverage'], days.map(d => [dLabel(d.date), fmt(d.energy_mwh, 1), fmt(d.budget_mwh, 1), pct(d.coverage)]));
}
RENDERERS.push(() => { if (STATE.park) renderParkView(); });

// =====================================================================
// Market
// =====================================================================
function zoneChips(box, zones, set, onChange) {
  box.innerHTML = zones.map(z => { const s = ZSTYLE[z]; const dash = {solid: '', dash: '6 3', dot: '1.5 3', dashdot: '6 3 1.5 3', longdash: '10 3', longdashdot: '10 3 1.5 3'}[s[1]] || '';
    return '<button type="button" class="chip" data-z="' + z + '" aria-pressed="' + set.has(z) + '"><svg class="linje" viewBox="0 0 26 10" aria-hidden="true"><line x1="1" y1="5" x2="25" y2="5" stroke="currentColor" stroke-width="2.5" stroke-dasharray="' + dash + '" style="color:var(' + s[0] + ')"/></svg>' + ZONE_NAMES[z] + '</button>'; }).join('');
  box.querySelectorAll('button.chip').forEach(b => b.addEventListener('click', () => {
    const z = b.dataset.z;
    if (set.has(z)) { if (set.size > 1) set.delete(z); } else set.add(z);
    box.querySelectorAll('button.chip').forEach(x => x.setAttribute('aria-pressed', String(set.has(x.dataset.z))));
    onChange();
  }));
}
function segmented(label, options, value, onChange) {
  const wrap = document.createElement('div'); wrap.className = 'seg'; wrap.setAttribute('role', 'group'); wrap.setAttribute('aria-label', label);
  wrap.innerHTML = options.map(([v, l]) => '<button type="button" data-v="' + v + '" aria-pressed="' + (v === value) + '">' + l + '</button>').join('');
  wrap.querySelectorAll('button').forEach(b => b.addEventListener('click', () => { wrap.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', String(x === b))); onChange(b.dataset.v); }));
  return wrap;
}
function selectField(id, label, options, value, onChange) {
  const f = document.createElement('div'); f.className = 'field';
  f.innerHTML = '<label for="' + id + '">' + label + '</label><span class="valj"><select id="' + id + '">' + options.map(([v, l]) => '<option value="' + esc(v) + '"' + (String(v) === String(value) ? ' selected' : '') + '>' + esc(l) + '</option>').join('') + '</select></span>';
  f.querySelector('select').addEventListener('change', e => onChange(e.target.value));
  return f;
}
function activeZones(zones, set) { return zones.filter(z => set.has(z)); }
function renderMarket() {
  const ty = M.this_year, ly = String(+ty - 1);
  el('m-scope').textContent = 'Jan 2022 to ' + dLabel(M.data_end) + ' · day-ahead prices and actual solar output';
  const parts = M.main_zones.map(z => { const cur = M.yearly[z][ty] || {}, prev = M.ytd_compare[z] || {};
    return '<b>' + num(pct(cur.capture_rate)) + '</b> in ' + z + ' (' + num(pct(prev.capture_rate)) + ' in the same period of ' + ly + ')'; });
  el('m-lede').innerHTML = 'So far this year solar power has earned ' + parts.join(' and ') + ' of the average spot price' + help('capture_rate') +
    '. The spot price itself averaged ' + M.main_zones.map(z => '<b>' + num(eur((M.yearly[z][ty] || {}).base)) + '</b> in ' + z).join(' and ') + '.';
  const c = el('m-controls');
  const chips = document.createElement('div'); chips.className = 'controls'; chips.setAttribute('role', 'group'); chips.setAttribute('aria-label', 'Bidding zones');
  zoneChips(chips, M.zones, STATE.zones, () => { writeHash('market'); redrawAll(); });
  c.appendChild(chips);
  c.appendChild(segmented('Period', [['36', 'Last 3 years'], ['all', 'Since 2022']], STATE.range, v => { STATE.range = v; writeHash('market'); redrawAll(); }));
  draw(() => {
    const months = STATE.range === 'all' ? M.months : M.months.slice(-(+STATE.range));
    const zs = activeZones(M.zones, STATE.zones);
    const xs = months.map(mk => mk + '-15');
    const xa = {type: 'date', tickformat: STATE.range === 'all' ? '%Y' : '%b %Y', dtick: STATE.range === 'all' ? 'M12' : 'M6', hoverformat: '%b %Y'};
    plot('m-price', zs.map(z => ({type: 'scatter', mode: 'lines', name: z, x: xs, y: months.map(mk => (M.monthly[z][mk] || {}).base), line: zline(z), connectgaps: false,
      hovertemplate: z + ': %{y:,.1f} EUR/MWh<extra></extra>'})), layout({xaxis: xa, yaxis: {title: {text: 'EUR/MWh'}}, showlegend: true, margin: {l: 60, r: 16, t: 36, b: 44}}), 'Spot price by month for ' + zs.join(', '));
    el('m-price-tbl').innerHTML = table(['Month'].concat(zs.map(z => z + '<span class="u">EUR/MWh</span>')), months.slice().reverse().map(mk => [mLabel(mk)].concat(zs.map(z => fmt((M.monthly[z][mk] || {}).base, 1)))));
    const shown = months.filter(mk => zs.some(z => isNum((M.monthly[z][mk] || {}).capture_rate)));
    const cmax = Math.max(1.1, ...[].concat(...zs.map(z => months.map(mk => (M.monthly[z][mk] || {}).capture_rate).filter(isNum))));
    plot('m-capture', zs.map(z => ({type: 'scatter', mode: 'lines+markers', name: z, x: xs, y: months.map(mk => (M.monthly[z][mk] || {}).capture_rate), line: zline(z), marker: zmarker(z, 6),
      connectgaps: false, hovertemplate: z + ': %{y:.0%}<extra></extra>'})),
      layout({xaxis: xa, yaxis: {tickformat: '.0%', range: [0, cmax * 1.05], rangemode: 'normal'}, showlegend: true, margin: {l: 60, r: 16, t: 36, b: 44},
        shapes: [{type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 1, y1: 1, line: {color: css('--muted'), width: 1}}],
        annotations: [{xref: 'paper', x: 1, y: 1, yanchor: 'bottom', xanchor: 'right', text: '100% = spot price', showarrow: false, font: {family: css('--font-display'), size: 13, color: css('--muted')}}]}),
      'Solar capture rate by month for ' + zs.join(', '));
    el('m-capture-tbl').innerHTML = table(['Month'].concat(zs), shown.slice().reverse().map(mk => [mLabel(mk)].concat(zs.map(z => pct((M.monthly[z][mk] || {}).capture_rate)))));
    renderMarketYears();
  });
  const sp = M.spread_se4_se3 || {}, spy = sp[ty], spl = sp[ly], spo = sp[String(+ty - 2)];
  if (spy) el('m-spread').innerHTML = 'This year SE4 has been more expensive than SE3 ' + num(pct(spy.share_se4_higher)) + ' of the time, by ' + num(eur(spy.mean_eur)) + ' on average. ' +
    ly + ': ' + num(pct(spl && spl.share_se4_higher)) + ' of the time (' + num(eur(spl && spl.mean_eur)) + ')' + (spo ? '; ' + (+ty - 2) + ': ' + num(pct(spo.share_se4_higher)) + '.' : '.');
  renderHeatmapControls(); renderProfileControls();
  draw(renderHeatmap); draw(renderProfiles);
}
function renderMarketYears() {
  const ty = M.this_year, ly = String(+ty - 1);
  el('m-year-note').textContent = ty + ' covers 1 Jan to ' + dShort(M.data_end) + ' and is compared with the same period of ' + ly + '. Do not compare the part-year with full years: autumn and winter have higher prices and a higher capture rate.';
  const zs = activeZones(M.zones, STATE.zones);
  el('m-years').innerHTML = zs.map(z => {
    const yrs = Object.keys(M.yearly[z]).filter(y => y >= '2022');
    const rows = yrs.map(y => [y === ty ? y + ' <span class="muted">to ' + dShort(M.data_end) + '</span>' : y, M.yearly[z][y]]);
    rows.push([ly + ' <span class="muted">same period</span>', M.ytd_compare[z] || {}]);
    let weakAny = false;
    const body = rows.map(([lbl, c]) => { const weak = c && isNum(c.solar_data_share) && c.solar_data_share < 0.9; weakAny = weakAny || weak;
      return [lbl, fmt(c.base, 1), fmt(c.solar_price, 1), pct(c.capture_rate) + (weak ? incMark('ENTSO-E has no solar data for ' + pct(1 - c.solar_data_share) + ' of the period') : ''), fmt(c.neg_hours, 0)]; });
    return '<div><h4>' + ZONE_NAMES[z] + '</h4><div class="tablewrap">' + table(['Year', 'Spot price<span class="u">EUR/MWh</span>', 'Solar price<span class="u">EUR/MWh</span>', 'Capture rate<span class="u">solar / spot</span>', 'Negative hours<span class="u">h</span>'], body, {caption: ZONE_NAMES[z] + ' by year'}) +
      '</div>' + (weakAny ? '<p class="note">' + icon('warning-triangle') + ' ENTSO-E has no solar data for more than 10% of the period, so the capture rate is uncertain.</p>' : '') + '</div>';
  }).join('');
}
// Spot price by hour × month (from Track C, same calculation: _calculate_hour_month_heatmap)
function renderHeatmapControls() {
  const hm = (X.profiles || {}).heatmap || {};
  const zones = Object.keys(hm);
  if (!zones.length) { el('m-heatmap').closest('.card').hidden = true; return; }
  if (!hm[STATE.hmZone]) STATE.hmZone = zones[0];
  const years = hm[STATE.hmZone].years.map(String);
  if (!STATE.hmYear) STATE.hmYear = years.includes(String(+M.this_year - 1)) ? String(+M.this_year - 1) : years[years.length - 1];
  const c = el('hm-controls'); c.innerHTML = '';
  c.appendChild(selectField('hm-zone', 'Zone', zones.map(z => [z, z]), STATE.hmZone, v => { STATE.hmZone = v; renderHeatmap(); }));
  c.appendChild(selectField('hm-year', 'Year', [['all', 'All years']].concat(years.slice().reverse().map(y => [y, y + (y === M.this_year ? ' (to date)' : '')])), STATE.hmYear, v => { STATE.hmYear = v; renderHeatmap(); }));
}
function renderHeatmap() {
  const hm = ((X.profiles || {}).heatmap || {})[STATE.hmZone];
  if (!hm) return;
  const z = STATE.hmYear === 'all' ? hm.all : hm.by_year[STATE.hmYear];
  const hours = Array.from({length: 24}, (_, h) => h);
  el('hm-note').textContent = 'Average spot price by hour and month in ' + STATE.hmZone + ', ' + (STATE.hmYear === 'all' ? 'all years since ' + hm.years[0] : STATE.hmYear) +
    '. Hours are in UTC: add 1 hour for Swedish winter time and 2 for summer time. EUR/MWh.';
  plot('m-heatmap', [{type: 'heatmap', x: hours, y: MSHORT, z: z, xgap: 1, ygap: 1,
    colorscale: [[0, css('--hm0')], [0.5, css('--hm1')], [1, css('--hm2')]],
    colorbar: {tickfont: {family: css('--font-mono'), size: 13, color: css('--muted')}, title: {text: 'EUR/MWh', font: {family: css('--font-display'), size: 13, color: css('--muted')}}, outlinewidth: 0, thickness: 12},
    hovertemplate: '%{y}, %{x}:00 UTC: %{z:,.1f} EUR/MWh<extra></extra>'}],
    layout({hovermode: 'closest', yaxis: {autorange: 'reversed', showgrid: false, zeroline: false, tickformat: '', rangemode: 'normal'}, xaxis: {dtick: 2, title: {text: 'Hour of day (UTC)'}}, margin: {l: 48, r: 16, t: 12, b: 52}}),
    'Average spot price by hour and month, ' + STATE.hmZone);
  el('m-heatmap-tbl').innerHTML = table(['Month'].concat(hours.map(h => String(h).padStart(2, '0'))), MSHORT.map((m, i) => [m].concat(hours.map(h => fmt((z[i] || [])[h], 1)))));
}
// Capture by panel design (PVsyst typical-year profiles, from Track C)
const PROFILE_NAMES = {sol_syd: 'South', sol_ov: 'East–west', sol_tracker: 'Tracker'};
function renderProfileControls() {
  const cap = (X.profiles || {}).capture || {};
  const zones = Object.keys(cap);
  if (!zones.length) { el('pc-chart').closest('.card').hidden = true; return; }
  const c = el('pc-controls'); c.innerHTML = '';
  c.appendChild(selectField('pc-zone', 'Zone', zones.map(z => [z, z]), STATE.pcZone, v => { STATE.pcZone = v; renderProfiles(); }));
  el('pc-note').innerHTML = 'What each panel design would have earned at actual spot prices, using PVsyst typical-year profiles' + help('design_capture') +
    '. This is a model: the level runs 5–8 points above what actual solar earned, so read it as the difference between designs.';
}
function renderProfiles() {
  const cap = ((X.profiles || {}).capture || {})[STATE.pcZone];
  if (!cap) return;
  const keys = Object.keys(PROFILE_NAMES).filter(k => cap[k]);
  const years = (cap.sol_syd || cap[keys[0]]).yearly.map(r => r.year).filter(y => y >= 2022);
  const get = (k, y) => ((cap[k] || {}).yearly || []).find(r => r.year === y) || {};
  const south = y => get('sol_syd', y).capture;
  el('pc-table').innerHTML = table(['Year'].concat(keys.map(k => PROFILE_NAMES[k] + '<span class="u">EUR/MWh</span>')).concat(['East–west vs south<span class="u">EUR/MWh</span>', 'Tracker vs south<span class="u">EUR/MWh</span>']),
    years.slice().reverse().map(y => [String(y) + (String(y) === M.this_year ? ' <span class="muted">to date</span>' : '')].concat(keys.map(k => fmt(get(k, y).capture, 1)))
      .concat([signed(isNum(get('sol_ov', y).capture) && isNum(south(y)) ? get('sol_ov', y).capture - south(y) : null, 1), signed(isNum(get('sol_tracker', y).capture) && isNum(south(y)) ? get('sol_tracker', y).capture - south(y) : null, 1)])),
    {caption: 'Modelled capture price by panel design, ' + STATE.pcZone});
  const style = {sol_syd: [css('--s1'), ''], sol_ov: [css('--s2'), ''], sol_tracker: [css('--muted'), '/']};
  plot('pc-chart', keys.map(k => ({type: 'bar', name: PROFILE_NAMES[k], x: years.map(String), y: years.map(y => get(k, y).capture),
    marker: {color: style[k][0], pattern: {shape: style[k][1], bgcolor: css('--surface'), fgcolor: style[k][0], solidity: 0.5}}, hovertemplate: PROFILE_NAMES[k] + ': %{y:,.1f} EUR/MWh<extra></extra>'})),
    layout({barmode: 'group', xaxis: {type: 'category'}, yaxis: {title: {text: 'EUR/MWh'}}, showlegend: true, margin: {l: 60, r: 16, t: 36, b: 36}}), 'Modelled capture price by panel design, ' + STATE.pcZone);
}

// =====================================================================
// Futures
// =====================================================================
function renderFutures() {
  if (!F || !F.table) { el('f-lede').innerHTML = callout('Futures data is missing. It is loaded by the daily futures download.', 'info'); return; }
  el('f-scope').textContent = 'Latest settlement ' + dLabel(F.latest_date) + ' · prices in EUR/MWh with two decimals, as quoted';
  if (F.lede) el('f-lede').innerHTML = F.lede.replace(/(\d[\d .,]*\d|\d)/g, '<span class="num">$1</span>').replace('now trades at', 'now trades at') + help('area_price');
  el('f-flags').innerHTML = (F.flags || []).map(f => callout(esc(f))).join('');
  const hz = F.zones;
  el('f-tables').innerHTML = hz.map(z => {
    const rows = F.contracts.map(c => { const r = F.table[z][c.label]; if (!r) return null;
      const ch = key => { const x = r.changes[key]; if (!x || !isNum(x.delta)) return '<span class="muted">–</span>';
        return '<span title="Against ' + fmt(x.ref_value, 2) + ' EUR/MWh on ' + dLabel(x.ref_date) + '">' + signed(x.delta, 2) + '</span>' + (x.stale ? incMark('Nearest earlier price is from ' + dLabel(x.ref_date) + ', more than 10 days before the target date') : ''); };
      return [c.label + '<br><span class="muted">' + esc(c.delivery) + '</span>', fmt(r.value, 2) + (r.date !== F.latest_date ? incMark('Latest day with both SYS and EPAD: ' + dLabel(r.date)) : ''), ch('1v'), ch('1m'), ch('3m'), ch('12m')]; }).filter(Boolean);
    return '<div class="card"><header><div><h3>' + ZONE_NAMES[z] + '</h3><p>Area price and change since</p></div></header><div class="tablewrap">' +
      table(['Contract', 'Price<span class="u">EUR/MWh</span>', '1 week', '1 month', '3 months', '12 months'], rows, {caption: ZONE_NAMES[z] + ' area prices'}) + '</div></div>';
  }).join('');
  el('f-tables-note').innerHTML = 'Change in EUR/MWh against the last price on or before the same date earlier. ' + icon('warning-triangle') + ' marks a comparison where the nearest earlier price is more than 10 days old (a gap in the data), or a price from an earlier day because SYS or EPAD is missing today.';
  if (!STATE.contract || !F.history[STATE.contract]) STATE.contract = F.default_contract;
  const box = el('f-contracts'); box.innerHTML = '';
  box.appendChild(segmented('Contract', Object.keys(F.history).map(c => [c, c]), STATE.contract, v => { STATE.contract = v; writeHash('futures'); drawHistory(); }));
  const drawHistory = () => {
    const h = F.history[STATE.contract]; if (!h) return;
    el('f-chart-title').textContent = STATE.contract + ' (' + ((F.contract_meta[STATE.contract] || {}).delivery || '') + ') over time';
    const series = hz.map(z => ({type: 'scatter', mode: 'lines', name: z, x: h.dates, y: h[z], line: zline(z), connectgaps: false, hovertemplate: z + ': %{y:,.2f} EUR/MWh<extra></extra>'}));
    series.push({type: 'scatter', mode: 'lines', name: 'SYS', x: h.dates, y: h.SYS, line: zline('SYS', 1.5), connectgaps: false, hovertemplate: 'SYS: %{y:,.2f} EUR/MWh<extra></extra>'});
    const gaps = (F.gaps || []).map(g => ({type: 'rect', xref: 'x', yref: 'paper', x0: g.from, x1: g.to, y0: 0, y1: 1, fillcolor: css('--surface-2'), line: {width: 0}, layer: 'below'}));
    plot('f-history', series, layout({xaxis: {type: 'date', hoverformat: '%-d %b %Y'}, yaxis: {title: {text: 'EUR/MWh'}, rangemode: 'normal', tickformat: ',.0f'}, shapes: gaps, showlegend: true, margin: {l: 60, r: 16, t: 36, b: 44}}),
      STATE.contract + ' area price over time');
    el('f-history-tbl').innerHTML = table(['Date'].concat(hz).concat(['SYS']), h.dates.map((d, i) => [dLabel(d)].concat(hz.map(z => fmt(h[z][i], 2))).concat([fmt(h.SYS[i], 2)])).reverse());
  };
  draw(drawHistory);
  const cv = F.convergence || [];
  el('f-convergence').innerHTML = cv.length ? table(['Quarter'].concat([].concat(...hz.map(z => [z + ' forward<span class="u">last before delivery</span>', z + ' spot<span class="u">outcome</span>', z + ' difference<span class="u">spot − forward</span>']))),
    cv.map(r => [r.label + (r.partial ? ' <span class="muted">to ' + dShort(r.partial) + '</span>' : '')].concat([].concat(...hz.map(z => { const x = r[z] || {};
      const stale = x.forward_date && r.label && x.forward_date < addDays(deliveryStart(r.label), -10);
      return [fmt(x.forward, 2) + (x.forward_date ? ' <span class="muted">' + dShort(x.forward_date) + '</span>' : '') + (stale ? incMark('Priced ' + dLabel(x.forward_date) + ', more than 10 days before delivery, because of a gap in the data') : ''), fmt(x.realized, 2), signed(x.diff, 2)]; })))),
    {caption: 'Forward against outcome by quarter'}) : '<p class="note">No delivered quarters with futures data.</p>';
  renderNordic();
}
function deliveryStart(label) { const m = /^Q(\d)-(\d\d)$/.exec(label); if (!m) return '0000-00-00'; return '20' + m[2] + '-' + String((+m[1] - 1) * 3 + 1).padStart(2, '0') + '-01'; }
function addDays(day, n) { const d = new Date(day + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); }

// All Nordic zones (from Track C: nordic_market_data, same figures)
const NM = X.nordic;
function nmPeriod(r) { return r.kind === 'year' ? String(r.year) : r.kind === 'quarter' ? 'Q' + r.number + ' ' + r.year : MSHORT[r.number - 1] + ' ' + r.year; }
function nmHistory(zone, kind, year, number, complete) { return ((NM.history || {})[zone] || []).find(r => r.kind === kind && r.year === Number(year) && r.number === number && (!complete || !r.partial)) || null; }
function nmCurrent() { return NM.futures.find(r => r.id === STATE.ncontract && r.kind === STATE.nkind); }
function nmBase(zone, c) { return c ? nmHistory(zone, c.kind, STATE.nbench, c.number, true) : null; }
function nmPrice(c, z) { const a = c.areas[z]; return a.price == null ? '<span class="muted" title="' + (a.epad == null ? 'EPAD missing' : 'System price missing') + '">–</span><span class="vh">' + (a.epad == null ? 'EPAD missing' : 'System price missing') + '</span>' : fmt(a.price, 2); }
function renderNordic() {
  if (!NM || !NM.futures) { el('nm-card').hidden = true; el('nm-comparison').closest('.grid-2').hidden = true; return; }
  const years = Array.from(new Set((NM.history.SE3 || []).map(r => r.year))).sort();
  if (!STATE.nbench) { const done = (NM.history.SE3 || []).filter(r => r.kind === 'year' && !r.partial).map(r => r.year); STATE.nbench = done.length ? done[done.length - 1] : years[0]; }
  el('nm-status').innerHTML = 'Settlement ' + num(dLabel(NM.settlement_date)) + ' · spot history to ' + num(dLabel(NM.through)) + ' · six zones · EUR/MWh' + help('epad');
  const c = el('nm-controls'); c.innerHTML = '';
  c.appendChild(segmented('Delivery length', [['year', 'Year'], ['quarter', 'Quarter'], ['month', 'Month']], STATE.nkind, v => { STATE.nkind = v; STATE.ncontract = null; writeHash('futures'); renderNordic(); }));
  const contracts = NM.futures.filter(r => r.kind === STATE.nkind && (r.system != null || NM.zones.some(z => r.areas[z].price != null)));
  if (!contracts.some(r => r.id === STATE.ncontract)) { const next = contracts.find(r => r.start > NM.through); STATE.ncontract = next ? next.id : (contracts[0] || {}).id; }
  c.appendChild(selectField('nm-contract', 'Delivery', contracts.map(r => [r.id, nmPeriod(r) + (r.start <= NM.through ? ' (in delivery)' : '') + (NM.zones.every(z => r.areas[z].price == null) ? ' (SYS only)' : '')]), STATE.ncontract,
    v => { STATE.ncontract = v; writeHash('futures'); renderNordic(); }));
  c.appendChild(selectField('nm-bench', 'Compare with', years.map(y => [y, 'Same period ' + y]), STATE.nbench, v => { STATE.nbench = Number(v); renderNordic(); }));
  const t = el('nm-forward');
  t.innerHTML = '<caption class="vh">Forward area prices for all Nordic zones</caption><thead><tr><th scope="col">Delivery</th><th scope="col" class="n">SYS</th>' + NM.zones.map(z => '<th scope="col" class="n">' + z + '</th>').join('') + '</tr></thead><tbody>' +
    contracts.map(r => '<tr' + (r.id === STATE.ncontract ? ' class="selected"' : '') + '><th scope="row"><button type="button" class="btn lank" data-c="' + r.id + '" aria-pressed="' + (r.id === STATE.ncontract) + '">' + nmPeriod(r) + '</button>' +
      (r.start <= NM.through ? ' <span class="muted">in delivery</span>' : '') + '</th><td class="n">' + fmt(r.system, 2) + '</td>' + NM.zones.map(z => '<td class="n" title="' + (r.areas[z].price == null ? 'No complete area price' : 'EPAD ' + fmt(r.areas[z].epad, 2) + ' · volume ' + fmt(r.areas[z].volume, 0) + ' · open interest ' + fmt(r.areas[z].open_interest, 0)) + '">' + nmPrice(r, z) + '</td>').join('') + '</tr>').join('') + '</tbody>';
  t.querySelectorAll('button[data-c]').forEach(b => b.addEventListener('click', () => { STATE.ncontract = b.dataset.c; writeHash('futures'); renderNordic(); }));
  const cur = nmCurrent();
  const cmp = el('nm-comparison');
  if (!cur) { el('nm-cmp-title').textContent = 'Forward against history'; cmp.innerHTML = ''; el('nm-insight').textContent = 'No prices for this delivery length.'; return; }
  const baseLabel = nmPeriod({kind: cur.kind, year: STATE.nbench, number: cur.number});
  el('nm-cmp-title').textContent = nmPeriod(cur) + ' against ' + baseLabel;
  const diffs = [];
  cmp.innerHTML = '<caption class="vh">Forward against historical baseload</caption><thead><tr><th scope="col">Zone</th><th scope="col" class="n">Forward<span class="u">EUR/MWh</span></th><th scope="col" class="n">Baseload ' + esc(baseLabel) + '<span class="u">EUR/MWh</span></th><th scope="col" class="n">Difference<span class="u">EUR/MWh</span></th><th scope="col" class="n">Difference</th></tr></thead><tbody>' +
    NM.zones.map(z => { const a = cur.areas[z], h = nmBase(z, cur), base = h ? h.baseload : null, delta = a.price != null && base != null ? a.price - base : null, pc = delta != null && base > 0 ? delta / base * 100 : null;
      if (delta != null) diffs.push({zone: z, delta});
      return '<tr><th scope="row">' + z + '</th><td class="n">' + nmPrice(cur, z) + '</td><td class="n">' + fmt(base, 2) + (h ? '' : '<span class="vh"> no completed period</span>') + '</td><td class="n">' + signed(delta, 2) + '</td><td class="n">' + (pc == null ? '–' : signed(pc, 1) + '%') + '</td></tr>'; }).join('') + '</tbody>';
  diffs.sort((a, b) => b.delta - a.delta);
  let text = '';
  if (NM.zones.every(z => cur.areas[z].price == null)) text = 'Only the system price is quoted for ' + nmPeriod(cur) + ' (' + num(eur(cur.system, 2)) + '). Without EPAD there are no area prices to compare with history.';
  else if (diffs.length) text = nmPeriod(cur) + ' is priced furthest above ' + baseLabel + ' in <b>' + diffs[0].zone + '</b> (' + num(signed(diffs[0].delta, 2)) + ' EUR/MWh) and closest in <b>' + diffs[diffs.length - 1].zone + '</b> (' + num(signed(diffs[diffs.length - 1].delta, 2)) + ' EUR/MWh).';
  else text = 'The comparison needs a completed historical ' + cur.kind + ' with enough spot data. Choose an earlier year.';
  el('nm-insight').innerHTML = text;
  plot('nm-chart', [
    {type: 'bar', name: 'Forward ' + nmPeriod(cur), x: NM.zones, y: NM.zones.map(z => cur.areas[z].price), marker: {color: css('--s1')}, hovertemplate: 'forward %{y:,.2f} EUR/MWh<extra></extra>'},
    {type: 'bar', name: 'Baseload ' + baseLabel, x: NM.zones, y: NM.zones.map(z => { const h = nmBase(z, cur); return h ? h.baseload : null; }),
     marker: {color: css('--s-compare'), pattern: {shape: '/', bgcolor: css('--surface'), fgcolor: css('--muted'), solidity: 0.4}}, hovertemplate: 'baseload %{y:,.2f} EUR/MWh<extra></extra>'},
  ], layout({barmode: 'group', xaxis: {type: 'category'}, yaxis: {title: {text: 'EUR/MWh'}}, showlegend: true, margin: {l: 60, r: 16, t: 36, b: 36}}), 'Forward ' + nmPeriod(cur) + ' against baseload ' + baseLabel + ' by zone');
  const ac = el('nm-anchor-c'); ac.innerHTML = '';
  ac.appendChild(selectField('nm-anchor', 'Compare against', NM.zones.map(z => [z, z]), STATE.nanchor, v => { STATE.nanchor = v; renderNordic(); }));
  const anchor = STATE.nanchor, ap = cur.areas[anchor].price, ah = nmBase(anchor, cur);
  el('nm-spreads').innerHTML = '<caption class="vh">Zone spreads against ' + anchor + '</caption><thead><tr><th scope="col">Zone pair</th><th scope="col" class="n">Forward spread<span class="u">EUR/MWh</span></th><th scope="col" class="n">Historical spread<span class="u">EUR/MWh</span></th><th scope="col" class="n">Change<span class="u">EUR/MWh</span></th></tr></thead><tbody>' +
    NM.zones.filter(z => z !== anchor).map(z => { const f = cur.areas[z].price, h = nmBase(z, cur), fs = f != null && ap != null ? f - ap : null,
      hs = h && ah && h.baseload != null && ah.baseload != null ? h.baseload - ah.baseload : null, d = fs != null && hs != null ? fs - hs : null;
      return '<tr><th scope="row">' + z + ' ' + MINUS + ' ' + anchor + '</th><td class="n">' + signed(fs, 2) + '</td><td class="n">' + signed(hs, 2) + '</td><td class="n">' + signed(d, 2) + '</td></tr>'; }).join('') + '</tbody>';
}

// =====================================================================
// Battery
// =====================================================================
const ANC_NAMES = {anc_fcr_n: 'FCR-N', anc_fcr_d_up: 'FCR-D up', anc_fcr_d_down: 'FCR-D down', anc_afrr_up: 'aFRR up', anc_afrr_down: 'aFRR down', anc_mfrr_cm_up: 'mFRR-CM up', anc_mfrr_cm_down: 'mFRR-CM down'};
function renderBattery() {
  const r12 = z => ((B.per_zone || {})[z] || {}).rolling_12m || {};
  const main = (M.main_zones || []).filter(z => (B.per_zone || {})[z]);
  const best = main.slice().sort((a, b) => (r12(b).revenue_eur_mw || 0) - (r12(a).revenue_eur_mw || 0));
  if (best.length) {
    const z = best[0], o = best[1];
    el('b-lede').innerHTML = 'Over the last twelve months a 1 MW / 2 MWh battery in ' + z + ' could have earned at most <b>' + num(fmt(r12(z).revenue_eur_mw) + NN + 'EUR per MW') + '</b> from day-ahead arbitrage' +
      (o ? ' (' + o + ': ' + num(fmt(r12(o).revenue_eur_mw) + NN + 'EUR') + ')' : '') + help('arbitrage') + '. That is a ceiling with perfect knowledge of prices, not a forecast.';
  }
  el('b-scope').textContent = 'Jan 2023 to ' + dLabel(r12(main[0]).to);
  const c = el('b-controls');
  zoneChips(c, B.zones, STATE.bzones, () => { writeHash('battery'); redrawAll(); });
  draw(() => {
    const zs = activeZones(B.zones, STATE.bzones);
    const months = Array.from(new Set([].concat(...zs.map(z => Object.keys(B.per_zone[z].monthly))))).sort();
    const xa = {type: 'date', tickformat: '%Y', dtick: 'M12', hoverformat: '%b %Y'};
    plot('b-spread', zs.map(z => ({type: 'scatter', mode: 'lines', name: z, x: months.map(m => m + '-15'), y: months.map(m => (B.per_zone[z].monthly[m] || {}).spread_2h), line: zline(z), hovertemplate: z + ': %{y:,.0f} EUR/MWh<extra></extra>'})),
      layout({xaxis: xa, yaxis: {title: {text: 'EUR/MWh'}}, showlegend: true, margin: {l: 60, r: 16, t: 36, b: 44}}), 'Daily spread by month');
    el('b-spread-tbl').innerHTML = table(['Month'].concat(zs.map(z => z + '<span class="u">EUR/MWh</span>')), months.slice().reverse().map(m => [mLabel(m)].concat(zs.map(z => fmt((B.per_zone[z].monthly[m] || {}).spread_2h, 1)))));
    plot('b-rev', zs.map(z => ({type: 'scatter', mode: 'lines', name: z, x: months.map(m => m + '-15'), y: months.map(m => (B.per_zone[z].monthly[m] || {}).revenue_eur_mw), line: zline(z), hovertemplate: z + ': %{y:,.0f} EUR/MW<extra></extra>'})),
      layout({xaxis: xa, yaxis: {title: {text: 'EUR per MW'}}, showlegend: true, margin: {l: 64, r: 16, t: 36, b: 44}}), 'Arbitrage cap by month');
    el('b-rev-tbl').innerHTML = table(['Month'].concat(zs.map(z => z + '<span class="u">EUR/MW</span>')), months.slice().reverse().map(m => [mLabel(m)].concat(zs.map(z => fmt((B.per_zone[z].monthly[m] || {}).revenue_eur_mw, 0)))));
    const years = Array.from(new Set([].concat(...zs.map(z => Object.keys(B.per_zone[z].yearly))))).sort(), lastYear = years[years.length - 1];
    el('b-years').innerHTML = table(['Zone'].concat(years.map(y => y + '<span class="u">' + (y === lastYear ? 'Jan–' + dShort(r12(zs[0]).to) : 'full year') + '</span>')).concat(['Last 12 months<span class="u">EUR/MW</span>', 'Median day<span class="u">last 12 months, EUR/MW</span>', 'Daily spread<span class="u">12-month average, EUR/MWh</span>']),
      zs.map(z => [ZONE_NAMES[z]].concat(years.map(y => fmt((B.per_zone[z].yearly[y] || {}).revenue_eur_mw))).concat([fmt(r12(z).revenue_eur_mw), fmt(r12(z).daily_median), fmt(r12(z).spread_2h, 0)])), {caption: 'Arbitrage cap by year'});
  });
  const notes = [];
  main.forEach(z => { const q = (B.per_zone[z] || {}).quarter_uplift; if (q && isNum(q.uplift)) notes.push(z + ' ' + pct(q.uplift, 0, true)); });
  const zz = best[0] ? r12(best[0]) : null;
  el('b-notes').innerHTML = 'Assumptions: 1 MW / 2 MWh, at most one full charge per day, 88% round-trip efficiency, hourly prices. Not included: grid fees, degradation, ancillary services and the way more batteries narrow the spreads. ' +
    (notes.length ? 'Trading on quarter-hour prices (since 1 Oct 2025) raises the ceiling: ' + notes.join(', ') + '. ' : '') +
    (zz && isNum(zz.top10pct_share) ? 'The best 10% of days account for ' + pct(zz.top10pct_share) + ' of the revenue in ' + best[0] + ', so the revenue rests on ordinary days rather than a few peaks.' : '');
  renderAncillary();
}
function renderAncillary() {
  const A = X.ancillary || {};
  const zones = Object.keys(A);
  const card = el('anc-table').closest('.card');
  if (!zones.length) { card.hidden = true; return; }
  if (!A[STATE.ancZone]) STATE.ancZone = zones[0];
  const zs = ['SE3', 'SE4'].filter(z => A[z]);
  const keys = Object.keys(ANC_NAMES).filter(k => zs.some(z => A[z][k]));
  if (!STATE.ancKey) STATE.ancKey = keys.slice().sort((a, b) => ((A.SE3 || {})[b] || {}).last_12m - ((A.SE3 || {})[a] || {}).last_12m)[0];
  const anyZ = A[zs[0]][keys[0]];
  el('anc-note').innerHTML = 'Capacity revenue per MW, ' + mLabel(anyZ.last_12m_from) + ' to ' + mLabel(anyZ.last_12m_to) + (anyZ.last_12m_to === (M.data_end || '').slice(0, 7) ? ' (to date)' : '') + help('ancillary') + '. Source: Svenska kraftnät (Mimer).';
  el('anc-caveat').innerHTML = icon('info-circle') + '<div>An upper bound: it assumes the battery is available every hour and every bid is accepted. It cannot be added to the arbitrage cap, because the same megawatt cannot do both at once.</div>';
  el('anc-table').innerHTML = table(['Product'].concat(zs.map(z => z + '<span class="u">EUR/MW, 12 months</span>')),
    keys.map(k => ['<button type="button" class="btn lank" data-k="' + k + '" aria-pressed="' + (k === STATE.ancKey) + '">' + ANC_NAMES[k] + '</button>'].concat(zs.map(z => fmt(((A[z] || {})[k] || {}).last_12m, 0)))), {caption: 'Ancillary services, upper bound per MW'});
  el('anc-table').querySelectorAll('button[data-k]').forEach(b => b.addEventListener('click', () => { STATE.ancKey = b.dataset.k; renderAncillary(); }));
  el('anc-table').querySelectorAll('tbody tr').forEach(tr => { if (tr.querySelector('button[aria-pressed="true"]')) tr.classList.add('selected'); });
  const k = STATE.ancKey;
  const months = Array.from(new Set([].concat(...zs.map(z => (((A[z] || {})[k] || {}).monthly || []).map(r => r.month))))).sort();
  const val = (z, m) => { const r = (((A[z] || {})[k] || {}).monthly || []).find(x => x.month === m); return r ? r.eur_mw : null; };
  plot('anc-chart', zs.map(z => ({type: 'scatter', mode: 'lines', name: z, x: months.map(m => m + '-15'), y: months.map(m => val(z, m)), line: zline(z), hovertemplate: z + ': %{y:,.0f} EUR/MW<extra></extra>'})),
    layout({xaxis: {type: 'date', tickformat: '%Y', dtick: 'M12', hoverformat: '%b %Y'}, yaxis: {title: {text: 'EUR/MW'}}, showlegend: true, margin: {l: 64, r: 16, t: 36, b: 44}}), ANC_NAMES[k] + ' revenue per MW by month');
  el('anc-chart-tbl').innerHTML = table(['Month'].concat(zs.map(z => z + '<span class="u">EUR/MW</span>')), months.slice().reverse().map(m => [mLabel(m)].concat(zs.map(z => fmt(val(z, m), 0)))));
}

// =====================================================================
// Data
// =====================================================================
const LEFT_OUT = [
  ['Performance ratio (PR/PI) and weather-corrected losses', 'Irradiance (POA) runs about two hours behind production in seven of eight parks, and Hörby\'s sensor gives implausible values. PR returns once the data is corrected.'],
  ['Availability', 'The field is filled in for under 10% of quarter-hours and contains values above 100%.'],
  ['PPA revenue', 'A modelled assumption, not a contract outcome. The page shows spot value instead.'],
  ['Imbalance cost', 'Needs saved nominations and settlement data; the existing figures are simulations.'],
  ['Cannibalisation regression', 'Rests on too few points to support a decision.'],
  ['Battery investment return', 'Based on perfect foresight, it produced contradictory results (166% return on one page, 43-year payback on another).'],
];
function renderData() {
  el('d-scope').textContent = 'Checked ' + dLabel(S.ref_day);
  const n = (S.issues || []).length;
  el('d-lede').textContent = n ? n + ' known ' + (n === 1 ? 'issue affects' : 'issues affect') + ' the data. None of them changes the figures on this page, because missing data is counted as unknown rather than zero.' : 'No known issues in the data.';
  el('d-issues').innerHTML = n ? S.issues.map(i => '<li>' + callout('<strong>' + esc(i.park) + '.</strong> ' + esc(i.text)) + '</li>').join('') : '<li>' + callout('No known issues.', 'info') + '</li>';
  const rows = (S.sources || []).map(s => [esc(s.name) + ' <span class="muted">' + esc(s.source) + '</span>', dLabel(s.last), statusBadge(s.status)])
    .concat((S.parks || []).map(p => [esc(p.park) + ' <span class="muted">grid meter, Bazefield</span>', dLabel(p.last_meter), statusBadge(p.status)]));
  if (NM && NM.settlement_date) rows.push(['Futures, all Nordic zones <span class="muted">Euronext</span>', dLabel(NM.settlement_date), statusBadge('ok')]);
  el('d-sources').innerHTML = table(['Source', 'Latest data', 'Status'], rows, {num: [false, true, false], caption: 'Sources and latest data'});
  el('d-defs').innerHTML = (D.definitions || []).map(d => '<div><dt>' + esc(d[1]) + '</dt><dd>' + d[2] + '</dd></div>').join('');
  el('d-left').innerHTML = LEFT_OUT.map(d => '<div><dt>' + esc(d[0]) + '</dt><dd>' + esc(d[1]) + '</dd></div>').join('');
  el('footer').innerHTML = 'Electricity Price · generated ' + esc(D.generated) + ' by <code>generate_oversikt.py</code> from local files; data ' + esc(D.dataset) + '. Figures can be reproduced from the repository.';
}

// ---------- start ----------
readHash();
safe(renderStand);
safe(monthOptions);
safe(renderPortfolio);
safe(renderMarket);
safe(renderFutures);
safe(renderBattery);
safe(renderData);
safe(showData);
safe(() => { if (window.PrimoraTema) PrimoraTema.mount(el('tema'), {lang: 'en'}); });
safe(() => { if (window.PrimoraFeedback) PrimoraFeedback.mount(el('feedback'), {tool: 'Electricity Price', theme: 'auto', lang: 'en',
  view: () => STATE.park ? 'Portfolio › ' + P.parks[STATE.park].info.name + ' › ' + mLabel(STATE.m) : ({portfolio: 'Portfolio', market: 'Market', futures: 'Futures', battery: 'Battery', data: 'Data'})[STATE.sec] || ''}); });
if (STATE.sec === 'park' && STATE.park) openPark(STATE.park, false);
else { markNav(STATE.sec); if (location.hash) requestAnimationFrame(() => scrollToSec(STATE.sec)); }
"""


def _plotly_tag() -> str:
    source = PLOTLY_VENDOR.read_text(encoding="utf-8")
    if "</script" in source.lower():
        raise ValueError("Plotly-filen innehåller </script och kan inte bäddas in")
    return f"<script>{source}</script>"


def _body() -> str:
    return (BODY.replace("__TOOLS_URL__", TOOLS_URL)
            .replace("__LOGO_NAVY__", _logo("primora-logo-navy.png"))
            .replace("__LOGO_AQUA__", _logo("primora-logo-aqua.png")))


def _styles() -> str:
    return f"<style>{font_css()}\n{CSS}</style>"


def _scripts(data: Dict[str, Any]) -> str:
    return (
        f"{_plotly_tag()}\n"
        f"<script>{_shared('primora-feedback.js')}</script>\n"
        f"<script>const D = {script_json(data)};\nconst ICONS = {script_json(icons())};</script>\n"
        f"<script>{JS}</script>\n"
    )


def render_oversikt_fragment(data: Dict[str, Any]) -> str:
    """Sidan utan <html>/<head>/<body> — för publicering som Claude-artifact.

    Artifact-visaren lägger själv till dokumentskalet; <title> ska ligga
    först (bara de första 8 kB skannas). Växlaren körs före sidhuvudet så att
    det sparade temat gäller innan sidan ritas.
    """
    return (
        f"<title>{esc(TITLE)}</title>\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="description" content="Primora solar portfolio and Nordic electricity market: production, '
        'capture prices, futures and battery value.">\n'
        f"<script>{_shared('primora-tema.js')}</script>\n"
        f"{_styles()}\n"
        f"{_body()}\n"
        f"{_scripts(data)}"
    )


def render_oversikt(data: Dict[str, Any]) -> str:
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{esc(TITLE)}</title>\n"
        f"<script>{_shared('primora-tema.js')}</script>\n"
        f"{_styles()}\n"
        "</head>\n<body>\n"
        f"{_body()}\n"
        f"{_scripts(data)}"
        "</body>\n</html>\n"
    )
