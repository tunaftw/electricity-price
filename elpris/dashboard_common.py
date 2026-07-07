"""Delade renderar-helpers för de tre HTML-renderarna (K2).

Delas av ``unified_dashboard_v3_html`` (Track C), ``rework_dashboard_html``
(Nordic Clarity) och ``performance_report_html`` (månadsrapport):

* :func:`esc` — HTML-escape för text som splattas in i skalet.
* :func:`script_json` — JSON för inbäddning i inline ``<script>``: kompakta
  separatorer, ``default=str`` (datum → ISO-strängar) och ``</`` → ``<\\/``
  så en datasträng som innehåller ``</script>`` inte terminerar blocket.
* :data:`JS_HELPERS` — client-side ``htmlEsc``/``fmtNum`` (sv-SE, NBSP →
  vanligt mellanslag, null → '–') som injiceras i dashboard-skalen.

Medvetet INTE delat: Plotly-basteman och CSS-tokens. De är inte duplicering
utan identitet — Track C (Geist/JetBrains Mono, varmt papper) och Nordic
Clarity (Inter, kall ink) delar nästan ingen struktur, och att parametrisera
ihop dem vore sämre än två tydliga definitioner. Tabellsortering finns bara
i rework — inte heller duplicerad.
"""

from __future__ import annotations

import json
from typing import Any


def esc(s: Any) -> str:
    """HTML-escape (& < > " ') för text i skal/attribut. None → ''."""
    if s is None:
        return ""
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;"))


def script_json(obj: Any) -> str:
    """JSON-serialisera för inbäddning i ett inline ``<script>``-block.

    Kompakta separatorer (payload-storlek), ``default=str`` (datum m.m.),
    ``ensure_ascii=False`` (åäö oescapade) samt ``</`` → ``<\\/`` — en giltig
    JSON-escape som hindrar att ``</script>`` i en datasträng terminerar
    script-blocket i förtid.
    """
    out = json.dumps(obj, default=str, ensure_ascii=False,
                     separators=(",", ":"))
    return out.replace("</", "<\\/")


# Client-side helpers som injiceras i dashboard-skalen (unified + rework).
# htmlEsc/fmtNum är de mest defensiva av de tidigare tre varianterna:
# fmtNum hanterar null/undefined/''/NaN → '–' och normaliserar sv-SE:s
# NBSP-tusentalsavgränsare till vanligt mellanslag (kopierbara siffror,
# konsekvent rendering mellan dashboards).
JS_HELPERS = """
function htmlEsc(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/[&<>"']/g, function(c) {
        return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c];
    });
}
function fmtNum(v, d) {
    if (v === null || v === undefined || v === '' || isNaN(v)) return '–';
    var n = Number(v);
    return n.toLocaleString('sv-SE', {
        minimumFractionDigits: d == null ? 0 : d,
        maximumFractionDigits: d == null ? 0 : d,
    }).replace(/\\u00a0/g, ' ');
}
"""
