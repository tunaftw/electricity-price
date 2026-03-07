"""Databeräkningsmodul för elpris-dashboard.

Aggregerar spotpriser och capture prices per zon, profil, månad och år.
Returnerar en dict redo för JSON-serialisering.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .config import DATA_DIR, QUARTERLY_DIR, ZONES
from .solar_profile import (
    SOLAR_PROFILES_DIR,
    get_quarterly_solar_weight,
    list_available_profiles,
    _pvsyst_profiles,
)
from .entsoe_profile import ENTSOE_DIR, _profile_cache, create_typical_profile

# Profiler som dashboarden visar, mappade till visningsnamn
DASHBOARD_PROFILES = {
    "south_lundby": "Syd (Lundby)",
    "ew_boda": "Öst-Väst (Böda)",
    "tracker_sweden": "Tracker (Hova)",
    "entsoe_solar_SE1": "ENTSO-E Sol SE1",
    "entsoe_solar_SE2": "ENTSO-E Sol SE2",
    "entsoe_solar_SE3": "ENTSO-E Sol SE3",
    "entsoe_solar_SE4": "ENTSO-E Sol SE4",
}


def read_quarterly_prices(zone: str) -> Iterator[dict]:
    """Läs quarterly-prisdata för en zon.

    Itererar över alla CSV-filer i data/quarterly/{zone}/ och ger
    tillbaka rader med parsad timestamp och EUR/MWh-pris.

    Args:
        zone: Elområde (SE1–SE4)

    Yields:
        dict med nycklarna:
            timestamp: datetime — periodens starttid
            year: int
            month: int
            eur_mwh: float — spotpris i EUR/MWh
    """
    zone_dir = QUARTERLY_DIR / zone
    if not zone_dir.exists():
        return

    for csv_file in sorted(zone_dir.glob("*.csv")):
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = datetime.fromisoformat(row["time_start"])
                eur_kwh = float(row["EUR_per_kWh"])
                yield {
                    "timestamp": ts,
                    "year": ts.year,
                    "month": ts.month,
                    "eur_mwh": eur_kwh * 1000,  # EUR/kWh → EUR/MWh
                }


def _ensure_profiles_loaded(profiles: dict[str, str]) -> None:
    """Förladda profildata från alternativa sökvägar vid behov.

    På Windows kan symlinks vara trasiga (sparade som textfiler).
    Denna funktion laddar PVsyst- och ENTSO-E-profiler direkt
    från Resultat/-strukturen om standardsökvägarna inte fungerar.
    """
    # Alternativa kataloger för PVsyst-profiler
    alt_pvsyst_dir = DATA_DIR.parent / "Resultat" / "profiler" / "beraknade"
    # Alternativ katalog för ENTSO-E-generering
    alt_entsoe_dir = (
        DATA_DIR.parent / "Resultat" / "marknadsdata"
        / "entsoe-produktion" / "entsoe" / "generation"
    )

    for profile_key in profiles:
        if profile_key.startswith("entsoe_"):
            # ENTSO-E-profil: entsoe_solar_SE3 → (SE3, solar)
            parts = profile_key.split("_")
            if len(parts) == 3:
                gen_type = parts[1]
                zone = parts[2]
            elif len(parts) == 4:
                gen_type = f"{parts[1]}_{parts[2]}"
                zone = parts[3]
            else:
                continue

            cache_key = (zone, gen_type)
            if cache_key not in _profile_cache:
                # Försök ladda från alternativ sökväg
                for entsoe_dir in (ENTSOE_DIR, alt_entsoe_dir):
                    zone_dir = entsoe_dir / zone
                    if zone_dir.is_dir() and list(zone_dir.glob(f"{gen_type}_*.csv")):
                        # Temporärt peka om ENTSOE_DIR och ladda
                        import elpris.entsoe_profile as ep
                        original_dir = ep.ENTSOE_DIR
                        ep.ENTSOE_DIR = entsoe_dir
                        try:
                            _profile_cache[cache_key] = create_typical_profile(
                                zone, gen_type
                            )
                        finally:
                            ep.ENTSOE_DIR = original_dir
                        break
        else:
            # PVsyst-profil
            if profile_key in _pvsyst_profiles:
                continue

            # Försök standardsökväg först
            std_path = SOLAR_PROFILES_DIR / f"{profile_key}.csv"
            if std_path.is_file():
                continue  # load_pvsyst_profile hittar den

            # Försök alternativ sökväg
            alt_path = alt_pvsyst_dir / f"{profile_key}.csv"
            if alt_path.is_file():
                _load_pvsyst_from_path(profile_key, alt_path)


def _load_pvsyst_from_path(name: str, filepath: Path) -> None:
    """Ladda en PVsyst-profil från en specifik sökväg."""
    import csv as _csv

    profile: dict[tuple, float] = {}
    with open(filepath, "r", encoding="utf-8") as f:
        reader = _csv.DictReader(f)
        for row in reader:
            key = (int(row["month"]), int(row["day"]), int(row["hour"]))
            profile[key] = float(row["power_mw"])

    _pvsyst_profiles[name] = profile


def _get_available_profiles() -> dict[str, str]:
    """Filtrera DASHBOARD_PROFILES till de som faktiskt finns tillgängliga.

    Hanterar trasiga symlinks på Windows genom att kontrollera
    flera möjliga sökvägar för profildata.
    """
    # Försök list_available_profiles() först
    try:
        available = set(list_available_profiles())
    except (FileNotFoundError, OSError):
        available = set()

    # Om den missade profiler (t.ex. pga trasiga symlinks), sök direkt
    if not available:
        available = _discover_profiles_directly()

    return {
        key: label
        for key, label in DASHBOARD_PROFILES.items()
        if key in available
    }


def _discover_profiles_directly() -> set[str]:
    """Sök efter profiler direkt i filsystemet.

    Fallback när list_available_profiles() inte fungerar,
    t.ex. vid trasiga symlinks på Windows.
    """
    found: set[str] = set()

    # PVsyst-profiler: kolla SOLAR_PROFILES_DIR och alternativa platser
    pvsyst_dirs = [
        SOLAR_PROFILES_DIR,
        DATA_DIR.parent / "Resultat" / "profiler" / "beraknade",
    ]
    for d in pvsyst_dirs:
        if d.is_dir():
            for f in d.glob("*.csv"):
                found.add(f.stem)
            break

    # ENTSO-E-profiler: kolla ENTSOE_DIR och alternativa platser
    entsoe_dirs = [
        ENTSOE_DIR,
        DATA_DIR.parent / "Resultat" / "marknadsdata" / "entsoe-produktion"
        / "entsoe" / "generation",
    ]
    for d in entsoe_dirs:
        if d.is_dir():
            try:
                for zone_dir in d.iterdir():
                    if not zone_dir.is_dir():
                        continue
                    zone = zone_dir.name
                    for gen_type in ("solar", "wind_onshore"):
                        if list(zone_dir.glob(f"{gen_type}_*.csv")):
                            found.add(f"entsoe_{gen_type}_{zone}")
            except OSError:
                continue
            break

    # Generisk profil alltid tillgänglig
    found.add("sweden")

    return found


def _round_or_none(value: float | None, decimals: int = 2) -> float | None:
    """Avrunda till givet antal decimaler, eller returnera None."""
    if value is None:
        return None
    return round(value, decimals)


def _calculate_zone_data(
    zone: str,
    profiles: dict[str, str],
) -> tuple[list[dict], list[dict]]:
    """Beräkna baseload och capture prices för en zon.

    Returnerar (yearly_rows, monthly_rows) med aggregerad data.
    """
    # Ackumulatorer per (year,) och (year, month)
    # Varje bucket håller: sum_price, count, {profil: (sum_weighted, sum_weight)}
    yearly_acc: dict[int, dict] = defaultdict(lambda: {
        "sum_price": 0.0,
        "count": 0,
        "profiles": defaultdict(lambda: {"sum_weighted": 0.0, "sum_weight": 0.0}),
    })
    monthly_acc: dict[tuple[int, int], dict] = defaultdict(lambda: {
        "sum_price": 0.0,
        "count": 0,
        "profiles": defaultdict(lambda: {"sum_weighted": 0.0, "sum_weight": 0.0}),
    })

    # Beräkna solprofilvikter för varje rad
    for row in read_quarterly_prices(zone):
        ts = row["timestamp"]
        price = row["eur_mwh"]
        year = row["year"]
        month = row["month"]

        # Uppdatera ackumulatorer
        y_acc = yearly_acc[year]
        y_acc["sum_price"] += price
        y_acc["count"] += 1

        m_key = (year, month)
        m_acc = monthly_acc[m_key]
        m_acc["sum_price"] += price
        m_acc["count"] += 1

        # Beräkna vikter för varje profil
        for profile_key in profiles:
            weight = get_quarterly_solar_weight(ts, profile_key)
            weighted_price = price * weight

            y_prof = y_acc["profiles"][profile_key]
            y_prof["sum_weighted"] += weighted_price
            y_prof["sum_weight"] += weight

            m_prof = m_acc["profiles"][profile_key]
            m_prof["sum_weighted"] += weighted_price
            m_prof["sum_weight"] += weight

    # Bygg yearly-resultat
    yearly_rows = []
    for year in sorted(yearly_acc.keys()):
        acc = yearly_acc[year]
        baseload = acc["sum_price"] / acc["count"] if acc["count"] > 0 else None

        capture = {}
        ratio = {}
        for profile_key in profiles:
            prof = acc["profiles"][profile_key]
            if prof["sum_weight"] > 0:
                cap = prof["sum_weighted"] / prof["sum_weight"]
                capture[profile_key] = _round_or_none(cap)
                ratio[profile_key] = _round_or_none(
                    cap / baseload if baseload and baseload > 0 else None
                )
            else:
                capture[profile_key] = None
                ratio[profile_key] = None

        yearly_rows.append({
            "year": year,
            "baseload": _round_or_none(baseload),
            "capture": capture,
            "ratio": ratio,
            "records": acc["count"],
        })

    # Bygg monthly-resultat
    monthly_rows = []
    for (year, month) in sorted(monthly_acc.keys()):
        acc = monthly_acc[(year, month)]
        baseload = acc["sum_price"] / acc["count"] if acc["count"] > 0 else None

        capture = {}
        ratio = {}
        for profile_key in profiles:
            prof = acc["profiles"][profile_key]
            if prof["sum_weight"] > 0:
                cap = prof["sum_weighted"] / prof["sum_weight"]
                capture[profile_key] = _round_or_none(cap)
                ratio[profile_key] = _round_or_none(
                    cap / baseload if baseload and baseload > 0 else None
                )
            else:
                capture[profile_key] = None
                ratio[profile_key] = None

        monthly_rows.append({
            "year": year,
            "month": month,
            "baseload": _round_or_none(baseload),
            "capture": capture,
            "ratio": ratio,
            "records": acc["count"],
        })

    return yearly_rows, monthly_rows


def calculate_dashboard_data() -> dict:
    """Beräkna all data som dashboarden behöver.

    Läser quarterly-prisdata för alla zoner, beräknar baseload
    och capture price per profil, månad och år.

    Returns:
        Dict med nycklar:
            generated: ISO-timestamp för beräkningstillfället
            zones: lista av zoner
            profiles: dict med profilnycklar → visningsnamn
            yearly: dict per zon → lista av årsrader
            monthly: dict per zon → lista av månadsrader
    """
    profiles = _get_available_profiles()
    _ensure_profiles_loaded(profiles)
    now = datetime.now()

    yearly_data: dict[str, list[dict]] = {}
    monthly_data: dict[str, list[dict]] = {}

    for zone in ZONES:
        zone_dir = QUARTERLY_DIR / zone
        if not zone_dir.exists():
            continue

        print(f"Beräknar {zone}...")
        yearly_rows, monthly_rows = _calculate_zone_data(zone, profiles)

        if yearly_rows:
            yearly_data[zone] = yearly_rows
        if monthly_rows:
            monthly_data[zone] = monthly_rows

    return {
        "generated": now.isoformat(timespec="seconds"),
        "zones": list(yearly_data.keys()),
        "profiles": profiles,
        "yearly": yearly_data,
        "monthly": monthly_data,
    }
