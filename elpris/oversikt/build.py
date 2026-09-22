"""Sätter ihop all data för Översikt till en JSON-bar struktur."""

from __future__ import annotations

import sys
import time
from datetime import datetime
from typing import Any, Callable, Dict

from ..config import SWEDEN_TZ
from .batteri import build_batteri_data
from .common import spot_end_epoch
from .datastatus import build_datastatus
from .marknad import build_marknad_data
from .portfolj import build_portfolj_data
from .terminer import build_terminer_data

DEFINITIONS = [
    ("Produktion",
     "Uppmätt leverans till elnätet, summerad kvart för kvart. Elmätaren gäller. Invertervärdet används bara när "
     "mätaren saknas <i>och</i> invertern visar levande värden. Kvartar där ingen signal går att lita på (död mätare, "
     "fastfrusen inverter) räknas inte. De är okända, inte noll. Natt räknas alltid som noll."),
    ("Datatäckning",
     "Andel av dagsljuset (solhöjd över 5°) som har en trovärdig mätning. Varje kvart vägs med solhöjden, så att en "
     "saknad middag väger mer än en saknad gryning."),
    ("Mot budget",
     "Produktion jämfört med PVsyst-budgeten för <i>samma tid som har mätdata</i>. Månadsbudgeten fördelas över "
     "månadens kvartar med samma solhöjdsvikt. Visas bara när datatäckningen är minst 80 %. Portföljens värde "
     "räknas på de parker som klarar gränsen, och vilka som ingår står alltid bredvid. Kontroll på 57 kompletta "
     "park-månader: när 6 slumpvisa dygn tas bort hamnar jämförelsen i median 2 procentenheter från facit "
     "(90 % inom 6). Utan justeringen blir felet 19 procentenheter."),
    ("Specifik yield",
     "Produktion per installerad DC-effekt (kWh/kWp). Jämför parker av olika storlek. Under 95 % täckning är "
     "värdet för lågt och märks med ⚠."),
    ("Spotvärde",
     "Produktionen multiplicerad med spotpriset i parkens elområde, kvart för kvart. Det är vad elen var värd på "
     "day-ahead-marknaden, inte fakturerad intäkt (PPA-villkor, avgifter och obalans ingår inte)."),
    ("Capturepris och capture-kvot",
     "Capturepris = spotvärde / produktion, alltså vad en MWh var värd i snitt. Capture-kvot = capturepris / "
     "genomsnittligt spotpris (dygnet runt) i samma zon under de dygn parken har mätdata. För portföljen vägs "
     "zonernas spotpris med produktionen."),
    ("Solens capture rate (marknaden)",
     "Spotpriset viktat med zonens <i>faktiska</i> solproduktion enligt ENTSO-E, delat med spotpriset för samma "
     "period. Vi använder faktisk produktion, inte en typårsprofil, eftersom soliga dagar också är billiga dagar. "
     "PVsyst-profilen ger 5–8 procentenheter för hög kvot, en generisk profil 12–15."),
    ("Områdespris (terminer)",
     "Systempris (SYS) + områdestillägg (EPAD) för samma kontrakt och samma dag. Saknas ett av benen visas inget "
     "pris; det ersätts aldrig med SYS ensamt."),
    ("Dagsspread och arbitrage-tak",
     "Dagsspread = snittpriset under dygnets 2 dyraste timmar minus snittet under de 2 billigaste. Arbitrage-tak = "
     "vad ett batteri på 1 MW / 2 MWh hade tjänat med en full cykel per dygn, 88 % verkningsgrad och perfekt "
     "kännedom om dygnets priser. Det är ett tak, inte en prognos."),
    ("Tid och valuta",
     "Månader och dygn följer svensk tid (CET/CEST). Alla priser i EUR/MWh. Timpriser före 1 okt 2025 gäller "
     "för alla fyra kvartar i timmen."),
]


def _step(label: str, fn: Callable[[], Any]) -> Any:
    t0 = time.time()
    out = fn()
    print(f"  {label}: {time.time() - t0:.1f} s", file=sys.stderr)
    return out


def build_oversikt_data() -> Dict[str, Any]:
    portfolj = _step("portfölj", build_portfolj_data)
    marknad = _step("marknad", build_marknad_data)
    market_end = min(e for e in (spot_end_epoch(z) for z in ("SE3", "SE4")) if e)
    batteri = _step("batteri", lambda: build_batteri_data(market_end))
    terminer = _step("terminer", lambda: build_terminer_data(market_end))
    ref_day = max(portfolj["data_end"], marknad["data_end"])
    datastatus = _step("datastatus", lambda: build_datastatus(ref_day, portfolj, terminer))
    now = datetime.now(SWEDEN_TZ)
    return {
        "generated": now.strftime("%Y-%m-%d %H:%M"),
        "dataset": f"parker t.o.m. {portfolj['data_end']}, spot t.o.m. {marknad['data_end']}",
        "portfolj": portfolj,
        "marknad": marknad,
        "terminer": terminer,
        "batteri": batteri,
        "datastatus": datastatus,
        "definitions": DEFINITIONS,
    }
