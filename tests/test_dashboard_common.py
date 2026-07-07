"""Tester för dashboard_common — delade renderar-helpers (K2).

Escape + script-säker JSON delas av alla tre renderare. script_json fixar
den latenta buggen att '</script>' i en datasträng skulle terminera det
inbäddade <script>-blocket (rework hade skyddet, unified/performance inte).
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris.dashboard_common import JS_HELPERS, esc, script_json  # noqa: E402


# ---------------------------------------------------------------------------
# esc
# ---------------------------------------------------------------------------

def test_esc_escapes_all_five():
    assert esc('<a href="x">&\'') == "&lt;a href=&quot;x&quot;&gt;&amp;&#39;"


def test_esc_none_is_empty():
    assert esc(None) == ""


def test_esc_plain_text_unchanged():
    assert esc("2026-07-07 06:00") == "2026-07-07 06:00"


# ---------------------------------------------------------------------------
# script_json
# ---------------------------------------------------------------------------

def test_script_json_compact_separators():
    assert script_json({"a": 1, "b": [1, 2]}) == '{"a":1,"b":[1,2]}'


def test_script_json_escapes_script_terminator():
    out = script_json({"label": "x</script><script>alert(1)"})
    assert "</" not in out
    assert "<\\/" in out


def test_script_json_roundtrips_through_js_unescape():
    """<\\/ är giltig JSON-escape för </ — parsning ger originalsträngen."""
    original = {"label": "a</b>"}
    assert json.loads(script_json(original)) == original


def test_script_json_stringifies_dates():
    assert script_json({"d": date(2026, 7, 7)}) == '{"d":"2026-07-07"}'


def test_script_json_keeps_swedish_chars():
    assert script_json({"s": "åäö"}) == '{"s":"åäö"}'


# ---------------------------------------------------------------------------
# JS_HELPERS (smoke — riktiga verifieringen är byte-diff + preview)
# ---------------------------------------------------------------------------

def test_js_helpers_define_shared_functions():
    assert "function htmlEsc(" in JS_HELPERS
    assert "function fmtNum(" in JS_HELPERS
