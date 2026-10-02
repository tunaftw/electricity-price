"""Är gårdagen komplett i alla källor? Används av den automatiska synken.

``scripts/windows/elpris_sync.ps1`` kör ``scripts/datastatus_klar.py`` efter
``update_all.py`` och hämtar om tills allt är komplett (eller tiden är ute).
Design: docs/plans/2026-10-02-automatisk-datasync-design.md.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Callable, Mapping

from .config import PARK_ZONES, SWEDEN_TZ, ZONES

# ERA5 släpar alltid några dagar; äldre än så här räknas som saknad.
TEMPERATUR_MAX_DAGAR = 7

Senaste = datetime | date | None


def tacker_dagen(senaste: Senaste, dag: date) -> bool:
    """Täcker senaste lagrade värde hela ``dag`` (svensk tid)?

    En tidsstämpel med tidszon läses i svensk tid, en naiv tas som den är.
    Dagen räknas som täckt när senaste värdet ligger senare än ``dag`` eller i
    dess sista timme. Ett datum (utan klockslag) täcker dagen om det är ``dag``
    eller senare.
    """
    if senaste is None:
        return False
    if not isinstance(senaste, datetime):
        return senaste >= dag
    lokal = senaste.astimezone(SWEDEN_TZ) if senaste.tzinfo else senaste
    return lokal.date() > dag or (lokal.date() == dag and lokal.hour >= 23)


def _visa(senaste: Senaste) -> str:
    if senaste is None:
        return "ingen data"
    if isinstance(senaste, datetime):
        lokal = senaste.astimezone(SWEDEN_TZ) if senaste.tzinfo else senaste
        return f"senast {lokal:%Y-%m-%d %H:%M}"
    return f"senast {senaste.isoformat()}"


def kontrollera(
    idag: date,
    hamtare: Mapping[str, Callable[[], Senaste]],
    temperatur: Mapping[str, Callable[[], date | None]] | None = None,
) -> dict:
    """Kontrollera att gårdagen finns i varje källa.

    ``hamtare`` mappar källans namn till en funktion som ger senaste lagrade
    värde; ``temperatur`` mappar park till senaste temperaturdatum.
    """
    dag = idag - timedelta(days=1)
    saknas = [f"{namn} ({_visa(v)})" for namn, f in hamtare.items() if not tacker_dagen(v := f(), dag)]
    grans = idag - timedelta(days=TEMPERATUR_MAX_DAGAR)
    for park, f in (temperatur or {}).items():
        senast = f()
        if senast is None or senast < grans:
            saknas.append(f"Temperatur {park} ({_visa(senast)})")
    return {"dag": dag.isoformat(), "komplett": not saknas, "saknas": saknas}


def standardkallor() -> tuple[dict, dict]:
    """Källorna som Electricity Price bygger på, med repots egna läsfunktioner."""
    from . import bazefield, entsoe, esett, mimer, storage, temperature

    hamtare: dict[str, Callable[[], Senaste]] = {}
    for zon in ZONES:
        hamtare[f"Spot {zon}"] = lambda z=zon: storage.get_latest_timestamp(z)
    for zon in ZONES:
        for typ in ("solar", "wind_onshore"):
            hamtare[f"ENTSO-E {typ} {zon}"] = lambda z=zon, t=typ: entsoe.get_latest_timestamp(z, t)
    for zon in ZONES:
        hamtare[f"eSett {zon}"] = lambda z=zon: esett.get_latest_timestamp(z)
    for produkt in ("fcr", "mfrr_cm"):
        hamtare[f"Mimer {produkt}"] = lambda p=produkt: mimer.get_latest_timestamp(p)
    for park in PARK_ZONES:
        hamtare[f"Bazefield {park}"] = lambda p=park: bazefield.get_latest_synced_date(p)
    temp = {park: (lambda p=park: temperature.get_latest_stored_date(p)) for park in PARK_ZONES}
    return hamtare, temp
