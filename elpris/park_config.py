"""Parkmetadata och budgetkonfiguration för Svea Solars solparker.

Utökar elpris.config med displaynamn, platsinformation, anläggningsdata
och PVsyst-baserad budgetberäkning per park och månad.

Parkmetadata byggs dynamiskt från ``park_product_data.PARK_PRODUCT_DATA``
som är källan för teknisk parkinformation (moduler, växelriktare, geometri,
PVsyst-förväntningar m.m.). Se ``elpris/park_product_data.py``.
"""

import csv
from functools import lru_cache
from pathlib import Path
from typing import Optional

from .config import (
    PARK_CAPACITY_KWP,
    PARK_EXPORT_LIMIT,
    PARK_ZONES,
    RESULTAT_DIR,
)
from .park_product_data import PARK_PRODUCT_DATA

# --- Profilkatalog ---
PVSYST_PROFILE_DIR = RESULTAT_DIR / "profiler" / "beraknade"

# --- PVsyst-profil → filnamn ---
PVSYST_PROFILE_MAP: dict[str, str] = {
    "south": "south_lundby.csv",
    "ew": "ew_boda.csv",
    "tracker": "tracker_sweden.csv",
}

# --- Specifik årsproduktion per profiltyp (kWh/kWp/år, TMY) ---
SPECIFIC_YIELD_KWH_KWP: dict[str, float] = {
    "south": 1012.0,
    "ew": 911.0,
    "tracker": 1202.0,
}


# ---------------------------------------------------------------------------
# Bygg PARK_METADATA dynamiskt från PARK_PRODUCT_DATA
# ---------------------------------------------------------------------------

# Mappning: exact_location_name → svenskt län (för visning i rapporter).
_LOCATION_COUNTY: dict[str, str] = {
    "Mjällby": "Blekinge",
    "Enstaberga": "Södermanland",
    "Trödje": "Gävleborg",
    "Örelycke": "Blekinge",
    "Källtorp": "Västra Götaland",
    "Skäkelbacken (Skackelbacken_SC)": "Dalarna",
    "Stenstorp": "Västra Götaland",
    "Gungvala": "Blekinge",
}

# Rensade visningsnamn för platser där SharePoint-namnet är "smutsigt".
_LOCATION_DISPLAY: dict[str, str] = {
    "Skäkelbacken (Skackelbacken_SC)": "Skäkelbacken",
}


def _build_metadata() -> dict[str, dict]:
    """Bygg PARK_METADATA från PARK_PRODUCT_DATA.

    Lägger till visningsvänlig plats (``"Ort, Län"``) och profiltyp som
    matchar ``PVSYST_PROFILE_MAP``. Alla tekniska fält kopieras igenom
    så att rapportgeneratorn kan läsa dem direkt från metadata-dicten.
    """
    metadata: dict[str, dict] = {}
    for park_key, pd in PARK_PRODUCT_DATA.items():
        exact_name = pd["exact_location_name"]
        location_clean = _LOCATION_DISPLAY.get(exact_name, exact_name)
        county = _LOCATION_COUNTY.get(exact_name, "")
        location = f"{location_clean}, {county}" if county else location_clean

        # Profiltyp: tracker om parken har något tracker-system, annars south.
        profile_type = "tracker" if pd["tracking_type"] != "fixed" else "south"

        metadata[park_key] = {
            # --- Visningsfält (rapporthuvud) ---
            "display_name": pd["park_name"],
            "location": location,

            # --- Modulspecifikation ---
            "module_type": pd["module_type"],
            "module_wp": pd["module_wp"],
            "num_modules": pd["num_modules"],

            # --- Växelriktare ---
            "inverter_model": pd["inverter_model"],
            "inverter_manufacturer": pd["inverter_manufacturer"],
            "num_inverters": pd["num_inverters"],

            # --- Geometri ---
            "tilt_angle": pd["tilt_angle"],
            "azimuth": pd["azimuth"],
            "tracking": pd["tracking_type"] != "fixed",
            "tracking_type": pd["tracking_type"],

            # --- Effekt ---
            "ac_capacity_mwac": pd["ac_capacity_mwac"],
            "grid_limit_mwac": pd["grid_limit_mwac"],

            # --- BoS / transformator ---
            "transformer_capacity_kva": pd["transformer_capacity_kva"],
            "transformer_count": pd["transformer_count"],

            # --- Datum ---
            "commissioning_date": pd["commissioning_date"],

            # --- Prestandareferens (parkspecifik, inte generisk 0.80) ---
            "standard_pr": pd["expected_pr_pct"] / 100,
            "expected_annual_yield_kwh_kwp": pd["expected_annual_yield_kwh_kwp"],

            # --- PVsyst-profilmappning ---
            "profile_type": profile_type,
        }

    return metadata


PARK_METADATA: dict[str, dict] = _build_metadata()


# --- Manuella budgetöverstyrningar per park/månad ---
# Nyckel: park_key → "YYYY-MM" → dict med energy_mwh, irradiation_kwh_m2, pr_pct
PARK_BUDGET_OVERRIDES: dict[str, dict[str, dict]] = {
    # Exempel:
    # "horby": {
    #     "2026-03": {"energy_mwh": 1200.0, "irradiation_kwh_m2": 130.0, "pr_pct": 82.0}
    # }
}


# ---------------------------------------------------------------------------
# Intern: ladda PVsyst TMY-profil
# ---------------------------------------------------------------------------

@lru_cache(maxsize=8)
def _load_pvsyst_monthly_energy(profile_type: str) -> dict[int, float]:
    """Ladda PVsyst TMY-CSV och summera energi per månad.

    Returnerar dict {månad (1-12): energy_mwh} normaliserat till 1 MW DC.
    power_mw-kolumnen i CSV:n är redan normaliserad till 1 MW,
    så summan av alla timvärden per månad ger MWh för den månaden.
    """
    filename = PVSYST_PROFILE_MAP.get(profile_type)
    if filename is None:
        raise ValueError(f"Okänd profiltyp: {profile_type!r}. "
                         f"Tillgängliga: {list(PVSYST_PROFILE_MAP.keys())}")

    filepath = PVSYST_PROFILE_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(
            f"PVsyst-profil saknas: {filepath}. "
            f"Kör 'python process.py' för att generera profiler."
        )

    monthly_energy: dict[int, float] = {}
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            month = int(row["month"])
            power_mw = float(row["power_mw"])
            # Varje rad = 1 timme → power_mw * 1h = MWh
            monthly_energy[month] = monthly_energy.get(month, 0.0) + power_mw

    return monthly_energy


def _load_pvsyst_budget(
    park_key: str,
    capacity_kwp: float,
    month: int,
) -> dict:
    """Beräkna månadsbudget från PVsyst TMY-profil + parkspecifik yield/PR.

    Använder parkens egna förväntade årsproduktion (kWh/kWp) och PR
    från ``PARK_PRODUCT_DATA``, men skalar fördelningen mellan månader
    enligt PVsyst TMY-profilen som är kopplad till parken (``profile_type``).

    Args:
        park_key: Parknyckel (används för att slå upp parkspecifik yield/PR)
        capacity_kwp: Installerad DC-kapacitet i kWp
        month: Månad (1-12)

    Returns:
        dict med:
            energy_mwh: Förväntad produktion i MWh
            irradiation_kwh_m2: Uppskattad instrålning i kWh/m²
            pr_pct: Parkspecifik Performance Ratio (%)
    """
    if not 1 <= month <= 12:
        raise ValueError(f"Ogiltig månad: {month}. Måste vara 1-12.")

    meta = PARK_METADATA.get(park_key)
    if meta is None:
        raise ValueError(
            f"Okänd park: {park_key!r}. "
            f"Tillgängliga: {list(PARK_METADATA.keys())}"
        )

    profile_type = meta["profile_type"]
    park_pr = meta["standard_pr"]  # parkspecifik, t.ex. 0.85 för Hörby
    park_annual_yield = meta["expected_annual_yield_kwh_kwp"]  # t.ex. 1036 för Hörby

    # Ladda PVsyst månadsfördelning (MWh per 1 MW installerat).
    monthly_energy = _load_pvsyst_monthly_energy(profile_type)
    annual_per_mw = sum(monthly_energy.values())

    if annual_per_mw == 0:
        return {
            "energy_mwh": 0.0,
            "irradiation_kwh_m2": 0.0,
            "pr_pct": round(park_pr * 100, 2),
        }

    # Andel av årsproduktionen som infaller i denna månad enligt TMY.
    month_fraction = monthly_energy.get(month, 0.0) / annual_per_mw

    # Använd parkens egna årsproduktion istället för profilens generiska.
    park_annual_energy_mwh = park_annual_yield * capacity_kwp / 1000.0
    month_energy_mwh = park_annual_energy_mwh * month_fraction

    # Uppskatta instrålning: E = Irr * PR * (kWp/1000)
    # → Irr = E / (PR * kWp/1000) [kWh/m²]
    capacity_mw = capacity_kwp / 1000.0
    if capacity_mw > 0 and park_pr > 0:
        irradiation_kwh_m2 = month_energy_mwh / (park_pr * capacity_mw)
    else:
        irradiation_kwh_m2 = 0.0

    return {
        "energy_mwh": round(month_energy_mwh, 2),
        "irradiation_kwh_m2": round(irradiation_kwh_m2, 2),
        "pr_pct": round(park_pr * 100, 2),
    }


# ---------------------------------------------------------------------------
# Publika funktioner
# ---------------------------------------------------------------------------

def get_park_metadata(park_key: str) -> Optional[dict]:
    """Hämta sammanslagen metadata för en park.

    Slår ihop PARK_METADATA med PARK_CAPACITY_KWP, PARK_ZONES och
    PARK_EXPORT_LIMIT från config.py.

    Args:
        park_key: Parknyckel (t.ex. "horby", "hova")

    Returns:
        dict med all metadata, eller None om parken inte finns.
    """
    meta = PARK_METADATA.get(park_key)
    if meta is None:
        return None

    # Kopiera för att inte mutera originalet
    result = dict(meta)
    result["park_key"] = park_key
    result["capacity_kwp"] = PARK_CAPACITY_KWP.get(park_key)
    result["zone"] = PARK_ZONES.get(park_key)
    result["export_limit"] = PARK_EXPORT_LIMIT.get(park_key)

    return result


def get_budget(park_key: str, year: int, month: int) -> dict:
    """Hämta månadsbudget för en park.

    Kontrollerar först PARK_BUDGET_OVERRIDES, faller sedan tillbaka
    på PVsyst TMY-beräkning med parkspecifik yield/PR.

    Args:
        park_key: Parknyckel (t.ex. "horby")
        year: År (används för budget-override-nyckel)
        month: Månad (1-12)

    Returns:
        dict med energy_mwh, irradiation_kwh_m2, pr_pct

    Raises:
        ValueError: Om parken inte finns i konfigurationen
    """
    # Kolla manuell överstyrning
    overrides = PARK_BUDGET_OVERRIDES.get(park_key, {})
    month_key = f"{year:04d}-{month:02d}"
    if month_key in overrides:
        return dict(overrides[month_key])

    # Hämta metadata (för att validera att parken finns)
    meta = PARK_METADATA.get(park_key)
    if meta is None:
        raise ValueError(
            f"Okänd park: {park_key!r}. "
            f"Tillgängliga: {list(PARK_METADATA.keys())}"
        )

    capacity_kwp = PARK_CAPACITY_KWP.get(park_key)
    if capacity_kwp is None:
        raise ValueError(
            f"Kapacitet saknas för park {park_key!r} i PARK_CAPACITY_KWP"
        )

    return _load_pvsyst_budget(park_key, capacity_kwp, month)


def list_parks() -> list[str]:
    """Returnera alla konfigurerade parknycklar i alfabetisk ordning."""
    return sorted(PARK_METADATA.keys())
