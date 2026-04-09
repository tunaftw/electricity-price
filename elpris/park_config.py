"""Parkmetadata och budgetkonfiguration för Svea Solars solparker.

Utökar elpris.config med displaynamn, platsinformation, anläggningsdata
och PVsyst-baserad budgetberäkning per park och månad.
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

# --- Parkmetadata ---
PARK_METADATA: dict[str, dict] = {
    "horby": {
        "display_name": "Hörby",
        "location": "Hörby, Skåne",
        "module_type": "TBD",
        "module_wp": None,
        "num_modules": None,
        "inverter_model": "TBD",
        "num_inverters": None,
        "tilt_angle": None,
        "tracking": False,
        "standard_pr": 0.80,
        "profile_type": "south",
    },
    "fjallskar": {
        "display_name": "Fjällskär",
        "location": "Fjällskär, Ångermanland",
        "module_type": "TBD",
        "module_wp": None,
        "num_modules": None,
        "inverter_model": "TBD",
        "num_inverters": None,
        "tilt_angle": None,
        "tracking": False,
        "standard_pr": 0.80,
        "profile_type": "south",
    },
    "bjorke": {
        "display_name": "Björke",
        "location": "Björke, Västra Götaland",
        "module_type": "TBD",
        "module_wp": None,
        "num_modules": None,
        "inverter_model": "TBD",
        "num_inverters": None,
        "tilt_angle": None,
        "tracking": False,
        "standard_pr": 0.80,
        "profile_type": "south",
    },
    "agerum": {
        "display_name": "Agerum",
        "location": "Agerum, Blekinge",
        "module_type": "TBD",
        "module_wp": None,
        "num_modules": None,
        "inverter_model": "TBD",
        "num_inverters": None,
        "tilt_angle": None,
        "tracking": False,
        "standard_pr": 0.80,
        "profile_type": "south",
    },
    "hova": {
        "display_name": "Hova",
        "location": "Hova, Västra Götaland",
        "module_type": "TBD",
        "module_wp": None,
        "num_modules": None,
        "inverter_model": "TBD",
        "num_inverters": None,
        "tilt_angle": None,
        "tracking": True,
        "standard_pr": 0.80,
        "profile_type": "tracker",
    },
    "skakelbacken": {
        "display_name": "Skäkelbacken",
        "location": "Skäkelbacken, Västra Götaland",
        "module_type": "TBD",
        "module_wp": None,
        "num_modules": None,
        "inverter_model": "TBD",
        "num_inverters": None,
        "tilt_angle": None,
        "tracking": False,
        "standard_pr": 0.80,
        "profile_type": "south",
    },
    "stenstorp": {
        "display_name": "Stenstorp",
        "location": "Stenstorp, Västra Götaland",
        "module_type": "TBD",
        "module_wp": None,
        "num_modules": None,
        "inverter_model": "TBD",
        "num_inverters": None,
        "tilt_angle": None,
        "tracking": False,
        "standard_pr": 0.80,
        "profile_type": "south",
    },
    "tangen": {
        "display_name": "Tången",
        "location": "Tången, Halland",
        "module_type": "TBD",
        "module_wp": None,
        "num_modules": None,
        "inverter_model": "TBD",
        "num_inverters": None,
        "tilt_angle": None,
        "tracking": False,
        "standard_pr": 0.80,
        "profile_type": "south",
    },
}

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
    profile_type: str,
    capacity_kwp: float,
    month: int,
) -> dict:
    """Beräkna månadsbudget från PVsyst TMY-profil.

    Args:
        profile_type: Profiltyp ("south", "ew", "tracker")
        capacity_kwp: Installerad DC-kapacitet i kWp
        month: Månad (1-12)

    Returns:
        dict med:
            energy_mwh: Förväntad produktion i MWh
            irradiation_kwh_m2: Uppskattad instrålning i kWh/m²
            pr_pct: Standard Performance Ratio (%)
    """
    if not 1 <= month <= 12:
        raise ValueError(f"Ogiltig månad: {month}. Måste vara 1-12.")

    monthly_energy = _load_pvsyst_monthly_energy(profile_type)
    # Energi per MW installerat
    energy_per_mw = monthly_energy.get(month, 0.0)
    # Skala till parkens kapacitet (kWp → MW)
    capacity_mw = capacity_kwp / 1000.0
    energy_mwh = energy_per_mw * capacity_mw

    # Uppskatta instrålning: E = Irr * PR * (kWp/1000)
    # → Irr = E / (PR * capacity_mw) [kWh/kWp]
    # Vi rapporterar kWh/m² ≈ kWh/kWp (approximation vid STC)
    standard_pr = 0.80
    if capacity_mw > 0 and standard_pr > 0:
        irradiation_kwh_m2 = energy_per_mw / (standard_pr * 1.0)  # per MW → per kWp = /1000*1000
    else:
        irradiation_kwh_m2 = 0.0

    return {
        "energy_mwh": round(energy_mwh, 2),
        "irradiation_kwh_m2": round(irradiation_kwh_m2, 2),
        "pr_pct": standard_pr * 100.0,
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
    på PVsyst TMY-beräkning.

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

    # Hämta metadata
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

    profile_type = meta["profile_type"]
    return _load_pvsyst_budget(profile_type, capacity_kwp, month)


def list_parks() -> list[str]:
    """Returnera alla konfigurerade parknycklar i alfabetisk ordning."""
    return sorted(PARK_METADATA.keys())
