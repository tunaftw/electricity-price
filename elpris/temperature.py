"""Lufttemperatur per solpark (Open-Meteo ERA5 reanalys).

Temperaturserier används för temperaturkorrigerad PR-beräkning: en modul
tappar ~0,3-0,4 %/K över 25 °C celltemperatur, så en varm juli ger lägre
"rå" PR utan att något är fel med anläggningen.

Primärkälla är **Open-Meteo ERA5** (``archive-api.open-meteo.com``) — gratis,
ingen API-nyckel, timupplösning, global täckning från 1940 och framåt. Vi
hämtar från 2015-01-01 så det finns tillräckligt med historik för att räkna
månadsklimatologi (se :func:`monthly_climatology`).

Varför inte Bazefield? Väderstationerna *har* en ``TempAmbient``-punkt på 7 av
8 parker (Tången saknar den helt — dess ``Temperature7``/``TempPanelAvg`` är
panel-temperatur), men serien är otjänlig som primärkälla:

* sentinelvärden runt 6537-6553 (sensorfel/skalningsfel) i hela vintermånader,
* ``NaN``-perioder,
* start först under 2025 och stora glapp per park,
* flera stationer rapporterar tydligt panelnära temperatur (t.ex. 40 °C en
  julidag) snarare än lufttemperatur i skugga.

``bazefield.py`` hämtar numera ändå in ``TempAmbient`` som ``temp_air`` i
väder-CSV:erna (med sanity-filter) så att punkten finns för framtida
korsvalidering — men PR-korrigeringen ska bygga på ERA5-serierna här.

CSV-format (``Resultat/marknadsdata/temperatur/{park}.csv``)::

    timestamp,temp_c
    2015-01-01T00:00:00+00:00,1.4
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

from .config import HTTP_TIMEOUT_QUICK, RESULTAT_DIR, UTC_TZ, parse_iso
from .http_client import rate_limited, with_retry

# Open-Meteo ERA5 arkiv-API (ingen nyckel, ingen registrering)
ERA5_URL = "https://archive-api.open-meteo.com/v1/era5"

# ERA5 finns från 1940, men 2015 räcker för klimatologi och matchar
# ENTSO-E-historiken i övriga marknadsdata.
ERA5_EARLIEST_DATE = date(2015, 1, 1)

TEMPERATURE_DATA_DIR = RESULTAT_DIR / "marknadsdata" / "temperatur"

CSV_FIELDS = ["timestamp", "temp_c"]

# Rimlighetsintervall för svensk lufttemperatur. Filtrerar bort sentinel-
# värden (Bazefield rapporterar ~6553) och NaN.
TEMP_MIN_C = -60.0
TEMP_MAX_C = 50.0

# ---------------------------------------------------------------------------
# Parkkoordinater
# ---------------------------------------------------------------------------
# Källa: latitude/longitude i elpris/park_product_data.py (SharePoint-extrakt,
# anläggningsspecifika koordinater). Varje koordinat är korsvaliderad mot
# Open-Meteo geocoding (https://geocoding-api.open-meteo.com/v1/search) på
# ortsnamnet 2026-08-22 — träffen ska ligga i rätt län och inom ~15 km.
#
# Definieras här (inte i park_config.py) så modulen är fristående.
PARK_COORDS: dict[str, tuple[float, float]] = {
    # Mjällby, Sölvesborg, Blekinge (SE4). Geocoding "Mjällby" → 56.0500/14.6833.
    "horby": (56.05, 14.67),
    # Örelycke, Bräkne-Hoby, Blekinge (SE4). Geocoding "Örelycke" → 56.1667/14.6167.
    "agerum": (56.16, 14.63),
    # Gungvala, Karlshamn, Blekinge (SE4). Geocoding "Gungvala" → 56.2333/14.8000.
    "tangen": (56.23, 14.76),
    # Enstaberga, Nyköping, Södermanland (SE3). Geocoding "Enstaberga" → 58.7500/16.8500.
    "fjallskar": (58.78, 16.84),
    # Källtorp, Gullspång/Hova, Västra Götaland (SE3). Geocoding "Hova" → 58.8536/14.2191.
    "hova": (58.85, 14.20),
    # Trödje, Gävle, Gävleborg (SE3). Geocoding "Trödje" → 60.8167/17.2000.
    "bjorke": (60.79, 17.20),
    # Skäkelbacken, södra Dalarna (SE3). Orten saknas i Open-Meteos geocoder;
    # närmaste träffar Säter 60.35/15.75 och Borlänge 60.49/15.44 bekräftar
    # att SharePoint-koordinaten ligger i Dalarna.
    "skakelbacken": (60.09, 15.05),
    # Stenstorp, Falköping, Västra Götaland (SE3). Geocoding "Stenstorp" → 58.2725/13.7145.
    "stenstorp": (58.27, 13.71),
}


def get_temperature_csv_path(park_key: str) -> Path:
    """Returnera CSV-sökväg för en parks temperaturserie."""
    return TEMPERATURE_DATA_DIR / f"{park_key}.csv"


def _format_timestamp(time_str: str) -> str:
    """Normalisera Open-Meteos ``'2024-08-01T00:00'`` till full UTC-ISO."""
    if len(time_str) == 16:  # YYYY-MM-DDTHH:MM
        time_str = f"{time_str}:00"
    if not (time_str.endswith("Z") or "+" in time_str[10:]):
        time_str = f"{time_str}+00:00"
    return time_str.replace("Z", "+00:00")


def parse_hourly_response(payload: dict) -> list[dict]:
    """Parsa Open-Meteos ``hourly``-block till CSV-rader.

    Hoppar över timmar där temperaturen saknas (``null``) eller ligger
    utanför :data:`TEMP_MIN_C`/:data:`TEMP_MAX_C` — ERA5 returnerar ``null``
    för de senaste dygnen innan reanalysen är klar.

    Returns:
        ``[{"timestamp": "2024-08-01T00:00:00+00:00", "temp_c": 17.3}, ...]``
    """
    if payload.get("error"):
        raise ValueError(f"Open-Meteo error: {payload.get('reason', 'unknown')}")

    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    temps = hourly.get("temperature_2m") or []

    rows: list[dict] = []
    for time_str, temp in zip(times, temps):
        if temp is None:
            continue
        try:
            value = float(temp)
        except (TypeError, ValueError):
            continue
        if math.isnan(value) or not (TEMP_MIN_C <= value <= TEMP_MAX_C):
            continue
        rows.append({
            "timestamp": _format_timestamp(time_str),
            "temp_c": round(value, 2),
        })
    return rows


@with_retry()
@rate_limited()
def fetch_temperature(
    latitude: float,
    longitude: float,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Hämta timvis 2 m-lufttemperatur från Open-Meteo ERA5.

    Args:
        latitude: Nordlig latitud (WGS84).
        longitude: Östlig longitud (WGS84).
        start_date: Startdatum (inklusive).
        end_date: Slutdatum (inklusive — Open-Meteo är inklusiv i båda ändar).

    Returns:
        Lista av ``{"timestamp": str, "temp_c": float}`` i UTC.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "hourly": "temperature_2m",
        "timezone": "UTC",
    }
    response = requests.get(ERA5_URL, params=params, timeout=HTTP_TIMEOUT_QUICK)
    response.raise_for_status()
    return parse_hourly_response(response.json())


def save_temperature_data(park_key: str, rows: list[dict]) -> int:
    """Merga rader in i parkens CSV på ``timestamp`` (nya värden vinner).

    Returns:
        Antal *nya* tidsstämplar som tillkom (0 om allt redan fanns).
    """
    if not rows:
        return 0

    csv_path = get_temperature_csv_path(park_key)
    TEMPERATURE_DATA_DIR.mkdir(parents=True, exist_ok=True)

    existing: dict[str, dict] = {}
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                ts = row.get("timestamp")
                if ts:
                    existing[ts] = {"timestamp": ts, "temp_c": row.get("temp_c", "")}

    before = len(existing)
    for row in rows:
        ts = row["timestamp"]
        existing[ts] = {"timestamp": ts, "temp_c": row["temp_c"]}

    sorted_rows = sorted(existing.values(), key=lambda r: r["timestamp"])
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted_rows)

    return len(existing) - before


def get_latest_stored_date(park_key: str) -> date | None:
    """Sista datum som redan finns i parkens CSV (None om filen saknas)."""
    csv_path = get_temperature_csv_path(park_key)
    if not csv_path.exists():
        return None

    last_ts = None
    with open(csv_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ts = row.get("timestamp")
            if ts:
                last_ts = ts
    if not last_ts:
        return None
    try:
        return parse_iso(last_ts).astimezone(UTC_TZ).date()
    except ValueError:
        return None


def download_park_temperature(
    park_key: str,
    start_date: date | None = None,
    end_date: date | None = None,
    verbose: bool = True,
    force: bool = False,
) -> dict:
    """Hämta och spara temperaturhistorik för en park (årsvisa chunkar).

    Args:
        park_key: Parknyckel i :data:`PARK_COORDS`.
        start_date: Start (default: dagen efter senaste sparade värde, annars
            :data:`ERA5_EARLIEST_DATE`).
        end_date: Slut inklusive (default: igår — ERA5 släpar några dygn).
        verbose: Skriv progress.
        force: Ignorera befintlig data och hämta hela historiken.

    Returns:
        ``{"park", "start_date", "end_date", "total_records", "failed_chunks",
        "status"}``
    """
    from .failure_log import log_failure

    coords = PARK_COORDS.get(park_key)
    if coords is None:
        raise KeyError(f"Okänd park: {park_key}")
    latitude, longitude = coords

    if end_date is None:
        end_date = date.today() - timedelta(days=1)

    if start_date is None:
        if force:
            start_date = ERA5_EARLIEST_DATE
        else:
            latest = get_latest_stored_date(park_key)
            # Hämta om sista dygnet: ERA5 kan fylla på timmar i efterhand.
            start_date = latest if latest else ERA5_EARLIEST_DATE

    if verbose:
        print(f"\n{park_key} ({latitude}, {longitude})")
        print("-" * 50)

    if start_date > end_date:
        if verbose:
            print("  Redan uppdaterad!")
        return {
            "park": park_key,
            "start_date": start_date,
            "end_date": end_date,
            "total_records": 0,
            "failed_chunks": [],
            "status": "up_to_date",
        }

    total = 0
    failed_chunks: list[str] = []
    current = start_date

    while current <= end_date:
        chunk_end = min(date(current.year, 12, 31), end_date)
        if verbose:
            print(f"  {current} -> {chunk_end}...", end=" ", flush=True)
        try:
            rows = fetch_temperature(latitude, longitude, current, chunk_end)
            saved = save_temperature_data(park_key, rows)
            total += saved
            if verbose:
                print(f"{len(rows)} timmar, {saved} nya")
        except Exception as e:
            if verbose:
                print(f"fel: {e}")
            failed_chunks.append(f"{current}..{chunk_end}: {e}")
            log_failure("temperatur", park_key, f"{current}..{chunk_end}", str(e))
        current = chunk_end + timedelta(days=1)

    if verbose:
        print(f"  Totalt: {total} nya timmar")

    return {
        "park": park_key,
        "start_date": start_date,
        "end_date": end_date,
        "total_records": total,
        "failed_chunks": failed_chunks,
        "status": "partial" if failed_chunks else "ok",
    }


def download_all_temperatures(
    park_keys: list[str] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    verbose: bool = True,
    force: bool = False,
) -> list[dict]:
    """Hämta temperaturhistorik för flera parker (default: alla)."""
    if park_keys is None:
        park_keys = list(PARK_COORDS.keys())

    return [
        download_park_temperature(
            park_key=park_key,
            start_date=start_date,
            end_date=end_date,
            verbose=verbose,
            force=force,
        )
        for park_key in park_keys
    ]


# ---------------------------------------------------------------------------
# Läsning
# ---------------------------------------------------------------------------

def load_park_temperature(
    park_key: str,
    start: date | datetime | None = None,
    end: date | datetime | None = None,
) -> list[dict]:
    """Läs en parks temperaturserie.

    Speglar :func:`elpris.operations_dashboard_data.load_park_15min`:
    returnerar dictar med tz-aware UTC-tidsstämpel så serierna kan joinas
    direkt på ``timestamp_utc``.

    Args:
        park_key: Parknyckel.
        start: Filtrera från och med (date = 00:00 UTC den dagen).
        end: Filtrera till och med (date = hela dygnet inkluderas).

    Returns:
        ``[{"timestamp_utc": datetime, "temp_c": float}, ...]`` sorterad
        stigande. Tom lista om filen saknas.
    """
    csv_path = get_temperature_csv_path(park_key)
    if not csv_path.exists():
        return []

    start_dt = _as_utc_datetime(start, end_of_day=False)
    end_dt = _as_utc_datetime(end, end_of_day=True)

    records: list[dict] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ts_raw = row.get("timestamp")
            temp_raw = row.get("temp_c")
            if not ts_raw or temp_raw in (None, ""):
                continue
            try:
                ts = parse_iso(ts_raw).astimezone(UTC_TZ)
                temp = float(temp_raw)
            except ValueError:
                continue
            if start_dt and ts < start_dt:
                continue
            if end_dt and ts > end_dt:
                continue
            records.append({"timestamp_utc": ts, "temp_c": temp})

    records.sort(key=lambda r: r["timestamp_utc"])
    return records


def _as_utc_datetime(value, end_of_day: bool) -> datetime | None:
    """Normalisera date/datetime till tz-aware UTC-datetime (None → None)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC_TZ)
        return value.astimezone(UTC_TZ)
    # date
    if end_of_day:
        return datetime(value.year, value.month, value.day, 23, 59, 59, tzinfo=UTC_TZ)
    return datetime(value.year, value.month, value.day, tzinfo=UTC_TZ)


def load_park_temperature_map(
    park_key: str,
    start: date | datetime | None = None,
    end: date | datetime | None = None,
) -> dict[datetime, float]:
    """Som :func:`load_park_temperature` men som uppslagstabell per timme.

    Nyckeln är timmen i UTC (minuter/sekunder nollställda), så 15-min-poster
    från Bazefield kan slås upp med ``ts.replace(minute=0, second=0,
    microsecond=0)``.
    """
    return {
        rec["timestamp_utc"].replace(minute=0, second=0, microsecond=0): rec["temp_c"]
        for rec in load_park_temperature(park_key, start, end)
    }


def monthly_climatology(park_key: str) -> dict[int, float]:
    """Medeltemperatur per kalendermånad över alla *hela* år i serien.

    "Helt år" = år där alla 12 kalendermånader har minst en observation.
    Varje kalendermånad medelvärdesbildas först inom sitt år och sedan
    över åren, så ett år med fler observationer inte får extra vikt.

    Faller tillbaka på hela serien (alla år) om inget år är komplett — annars
    skulle en nystartad serie ge en tom klimatologi.

    Returns:
        ``{1: -1.8, 2: -1.5, ..., 12: 1.2}`` (°C). Tom dict om data saknas.
    """
    records = load_park_temperature(park_key)
    if not records:
        return {}

    # (år, månad) → [summa, antal]
    buckets: dict[tuple[int, int], list[float]] = defaultdict(lambda: [0.0, 0.0])
    for rec in records:
        ts = rec["timestamp_utc"]
        bucket = buckets[(ts.year, ts.month)]
        bucket[0] += rec["temp_c"]
        bucket[1] += 1

    months_per_year: dict[int, set[int]] = defaultdict(set)
    for year, month in buckets:
        months_per_year[year].add(month)

    complete_years = {y for y, months in months_per_year.items() if len(months) == 12}
    if not complete_years:
        complete_years = set(months_per_year)

    monthly_means: dict[int, list[float]] = defaultdict(list)
    for (year, month), (total, count) in buckets.items():
        if year in complete_years and count:
            monthly_means[month].append(total / count)

    return {
        month: round(sum(values) / len(values), 2)
        for month, values in sorted(monthly_means.items())
    }
