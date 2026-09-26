"""Tester för huvudversionens renderare (Electricity Price, byggd på Översikt).

Kontrollerar det verktygsstandarden kräver (sidhuvud, växlare, Ge feedback,
engelska, ikoner, textstorlekar och talformat) och att det som förts över
från Track C räknas som i Track C. Standard:
SveaSolarObsidianv2/Projects/Primora-Energy/verktygsstandard.md.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from elpris.oversikt import render, tillagg  # noqa: E402
from elpris.oversikt.render import BODY, CSS, JS, render_oversikt, render_oversikt_fragment  # noqa: E402

EMPTY = {"generated": "2026-09-26 12:00", "dataset": "", "portfolj": {}, "marknad": {}, "terminer": None,
         "batteri": {}, "datastatus": {}, "tillagg": {}, "definitions": []}
NATTARIFFER_WEB = ROOT.parent / "SveaSolar" / "Nattariffer" / "web"


@pytest.fixture(scope="module")
def page() -> str:
    return render_oversikt(EMPTY)


def test_header_has_logo_link_title_toggle_and_feedback(page):
    assert f'href="{render.TOOLS_URL}"' in page
    assert 'aria-label="Primora, to Primora Tools"' in page
    assert "<h1>Electricity Price</h1>" in page
    assert 'id="tema"' in page and 'id="feedback"' in page
    assert "PrimoraTema.mount(el('tema'), {lang: 'en'})" in JS
    assert "PrimoraFeedback.mount(el('feedback'), {tool: 'Electricity Price', theme: 'auto', lang: 'en'" in JS
    assert "logo-light" in page and "logo-dark" in page and "data:image/png;base64," in page


def test_theme_script_runs_before_header_and_page_is_english(page):
    assert page.index("primora-tema.js") < page.index('<header class="band">')
    assert '<html lang="en">' in page
    assert "document.documentElement.lang = 'en'" in JS
    frag = render_oversikt_fragment(EMPTY)
    assert frag.startswith("<title>Electricity Price</title>")
    assert frag.index("PrimoraTema") < frag.index('<header class="band">')


def test_shared_files_are_baked_in_and_identical_to_master():
    for name in ("primora-tema.js", "primora-feedback.js"):
        ours = (render.WEB / name).read_bytes()
        assert b"electricity prices/elpris/oversikt/web" in ours      # kopian står i filhuvudet
        if NATTARIFFER_WEB.exists():
            master = (NATTARIFFER_WEB / name).read_bytes()
            assert hashlib.sha256(ours).digest() == hashlib.sha256(master).digest(), name


# Ord som visar att svensk text läckt in i gränssnittet. Ortnamn (Luleå, Malmö,
# Hörby …) kommer ur datan och får innehålla å, ä och ö.
SWEDISH = ["Portföljen", "Elmarknaden", "Terminer", "Batteri", "Datastatus", "Månad", "Visa siffrorna", "Datatäckning",
           "Produktion", "mot budget", "Hittills i år", "Så räknar vi", "Stäng", "t.o.m."]
# Statusnycklarna ok/gammal/saknas kommer ur datan (datastatus.py) och översätts i renderaren.


def test_interface_text_is_english():
    text = BODY + JS
    for word in SWEDISH:
        assert word not in text, word
    stripped = re.sub(r"Luleå|Malmö|Hörby|Björke|Fjällskär|Tången|Skäkelbacken|Hova|Svenska kraftnät", "", text)
    stripped = re.sub(r"//[^\n]*", "", stripped)              # kommentarer får vara svenska
    hit = re.search(r"[åäöÅÄÖ]", stripped)
    assert not hit, stripped[max(0, hit.start() - 40):hit.end() + 20]


def test_no_unicode_symbols_as_icons_and_no_uppercase():
    text = BODY + JS + CSS
    for ch in "⚠▲▼●✕✓†◀▶":
        assert ch not in text, ch
    assert "text-transform: uppercase" not in CSS and "uppercase" not in CSS
    assert "letter-spacing: .0" not in CSS                     # ingen spärrning på etiketter


def test_every_icon_used_exists():
    used = set(re.findall(r"icon\('([a-z-]+)'\)", JS))
    used |= set(re.findall(r"\['(?:ok|warn|crit)', '([a-z-]+)', '", JS))           # statusmärkena
    used |= set(re.findall(r"icon\(kind === 'info' \? '([a-z-]+)' : '([a-z-]+)'\)", JS)[0])
    assert used, "hittade inga ikoner"
    for name in used:
        assert name in render.ICON_NAMES, name
        assert (render.ASSETS / "iconoir" / f"{name}.svg").exists(), name
    assert (render.ASSETS / "iconoir" / "LICENSE").exists()
    assert all(name in render.icons() for name in render.ICON_NAMES)


def test_text_is_never_smaller_than_13px():
    sizes = [float(s) for s in re.findall(r"font-size:\s*([\d.]+)px", CSS)]
    assert sizes and min(sizes) >= 13
    assert re.search(r"body \{[^}]*font-size: 16px", CSS)
    js_sizes = [int(s) for s in re.findall(r"size: (\d+)", JS)]
    assert min(js_sizes) >= 5  # markörstorlekar; textstorlekar kontrolleras nedan
    assert not re.search(r"font: \{[^}]*size: (1[0-2]|[0-9])\b", JS)


def test_themes_follow_the_standard():
    assert ':root:not([data-theme="light"])' in CSS and ':root[data-theme="dark"]' in CSS
    assert CSS.count("color-scheme: dark") >= 2
    assert "window.addEventListener('primora-tema'" in JS


def test_plotly_is_inlined_and_page_has_no_external_scripts(page):
    assert "plotly.js (cartesian" in page
    assert '<script src="' not in page
    assert "fonts.googleapis.com" not in page
    assert page.count("@font-face") == len(render.FONTS)


def test_data_cannot_close_the_script_block():
    html = render_oversikt(dict(EMPTY, dataset="</script><b>x"))
    assert "<\\/script><b>x" in html


def _node():
    node = shutil.which("node")
    if not node:
        pytest.skip("node saknas")
    return node


def test_page_javascript_parses(tmp_path):
    path = tmp_path / "page.js"
    path.write_text("const D = {};\nconst ICONS = {};\n" + JS, encoding="utf-8")
    subprocess.run([_node(), "--check", str(path)], check=True)


def test_number_format_is_english(tmp_path):
    """Decimalpunkt, smalt mellanslag som tusentalsavgränsare och U+2212 som minus."""
    start = JS.index("const NN =")
    end = JS.index("function callout(")
    script = JS[start:end] + """
    const out = {a: fmt(1234567.891, 1), b: fmt(-3.14, 2), c: signed(3.1, 1), d: pct(0.0312, 1, true), e: pct(-0.12, 0, true),
      f: eur(49.83), g: money(429501), h: fmt(null), i: dLabel('2026-09-21'), j: mLabel('2026-08', true), k: fmt(-0.004, 2),
      l: words(3.14, 1, '%', 'above', 'below'), m: words(-2, 1, '%', 'above', 'below')};
    console.log(JSON.stringify(out));
    """
    path = tmp_path / "fmt.js"
    path.write_text(script, encoding="utf-8")
    res = json.loads(subprocess.run([_node(), str(path)], check=True, capture_output=True, text=True, encoding="utf-8").stdout)
    assert res == {"a": "1 234 567.9", "b": "−3.14", "c": "+3.1", "d": "+3.1%", "e": "−12%",
                   "f": "49.8 EUR/MWh", "g": "429 501 EUR", "h": "–", "i": "21 Sep 2026", "j": "August 2026",
                   "k": "0.00", "l": "3.1% above", "m": "2.0% below"}


# ---------------------------------------------------------------------------
# Det som förs över från Track C
# ---------------------------------------------------------------------------

def test_ancillary_last_12m_matches_track_c_rule():
    months = [{"year": 2025, "month": m, "baseload": None, "capture": 100.0 * m} for m in range(1, 13)]
    assert tillagg.anc_last_12m(months) == sum(100.0 * m for m in range(1, 13))
    eight = months[:8]
    assert tillagg.anc_last_12m(eight) == pytest.approx(sum(100.0 * m for m in range(1, 9)) / 8 * 12)
    assert tillagg.anc_last_12m(months[:5]) is None
    with_base = [{"year": 2025, "month": 1, "baseload": 5.0, "capture": 99.0}] * 12
    assert tillagg.anc_last_12m(with_base) == 60.0
# Regeln ovan är kontrollerad mot Track C:s ancLast12mRevenue i
# unified_dashboard_v3_html.py (git-taggen arkiv/track-c-2026-09) och mot
# Track C:s data för samma dag: alla 12-månaderstal var identiska.
