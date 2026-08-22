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
# ---------------------------------------------------------------------------
# Manuella budgetöverstyrningar per park och månad
# ---------------------------------------------------------------------------
#
# Hur denna dict används:
#   1. get_budget(park_key, year, month) kollar här FÖRST
#   2. Om inget värde hittas → fallback till _load_pvsyst_budget() som
#      använder parkens verkliga expected_annual_yield_kwh_kwp och
#      expected_pr_pct från PARK_PRODUCT_DATA, skalat med säsongs-
#      fördelning från PVsyst-profilen (south/ew/tracker)
#
# När ska du använda overrides?
#   - När du har PARKSPECIFIK månadsdata från PVsyst SRC Forecast-rapporten
#     (tillgänglig i SharePoint per park, t.ex. "14102025_Hörby PVsyst_SRC
#     Forecast 12 MW [SLC_weighted].pdf"). Där finns månadsvärden för
#     energy, irradiation, PR som är mycket mer exakta än att skala en
#     generisk PVsyst-profil.
#   - När du vill lägga in degradations-kompensation år-för-år
#     (typiskt -0.5% per år efter COD)
#   - När du har PPA-kontrakterade målvärden (för avtalsrapportering)
#
# Format (alla tre värden krävs):
#   {
#       "park_key": {
#           "YYYY-MM": {
#               "energy_mwh": float,           # Förväntad produktion
#               "irradiation_kwh_m2": float,   # Förväntad POA-instrålning
#               "pr_pct": float,               # Förväntad PR (0-100)
#           },
#           ...
#       }
#   }
#
# Status: IFYLLD 2026-08 för alla 8 parker med månadsvärden direkt ur
# "Balances and main results"-tabellen i respektive PVsyst SRC Forecast-rapport
# (SharePoint: Utilityhub / Asset Management Library / Projects in operation /
# {park} / 03 - Technical Documentation / 01 - Yield Assessment / 01 - PVsyst).
# Se docs/plans/2026-04-10-cowork-monthly-budget-prompt.md.
#
# Enheter (som de står i PDF:erna → som de lagras här):
#   E_Grid   kWh      → energy_mwh          (dividerat med 1000)
#   GlobInc  kWh/m²   → irradiation_kwh_m2  (oförändrat)
#   PR       ratio    → pr_pct              (× 100)
#
# Alla rapporter är TMY-simuleringar (PVsyst "simuleringsår 1") utan kalenderår.
# Nyckeln "2026-MM" betyder därför "typisk månad MM", inte "år 2026" — samma
# värden gäller alla år tills en ny PVsyst-körning görs. Ingen degradering är
# inbakad (se PARK_DEGRADATION_PCT_PER_YEAR nedan).
#
# OBS om månads-PR: PR är LÄGRE på vintern än på sommaren i samtliga åtta
# rapporter (t.ex. Skäkelbacken 8,9 % i december mot 88,6 % i augusti). Det är
# inte ett läsfel — PVsyst lägger tung smuts-/snöförlust på vintermånaderna
# (Hova: 8 % i januari, 10 % i december) och lågljusförlusterna dominerar över
# den temperaturvinst kalla moduler ger på nordliga breddgrader. Varje
# månadsvärde är verifierat mot identiteten PR = E_Grid / (GlobInc × kWp)
# (maxavvikelse 0,2 procentenheter, vilket är avrundningen i GlobInc).
PARK_BUDGET_OVERRIDES: dict[str, dict[str, dict]] = {
    # Källa: 14102025_Hörby PVsyst_SRC Forecast 12 MW [SLC_weighted].pdf
    #   PVsyst V7.4.8, variant "240307 - Hörby - Forecast SRC 12MW", TMY (Solcast).
    "horby": {
        "2026-01": {"energy_mwh": 202.349, "irradiation_kwh_m2": 18.6, "pr_pct": 59.9},
        "2026-02": {"energy_mwh": 519.699, "irradiation_kwh_m2": 37.9, "pr_pct": 75.7},
        "2026-03": {"energy_mwh": 1564.765, "irradiation_kwh_m2": 95.6, "pr_pct": 90.3},
        "2026-04": {"energy_mwh": 2347.099, "irradiation_kwh_m2": 150.3, "pr_pct": 86.2},
        "2026-05": {"energy_mwh": 2941.197, "irradiation_kwh_m2": 190.9, "pr_pct": 85.1},
        "2026-06": {"energy_mwh": 2942.198, "irradiation_kwh_m2": 195.0, "pr_pct": 83.3},
        "2026-07": {"energy_mwh": 2834.510, "irradiation_kwh_m2": 183.4, "pr_pct": 85.3},
        "2026-08": {"energy_mwh": 2427.821, "irradiation_kwh_m2": 152.7, "pr_pct": 87.7},
        "2026-09": {"energy_mwh": 1725.757, "irradiation_kwh_m2": 106.1, "pr_pct": 89.8},
        "2026-10": {"energy_mwh": 862.046, "irradiation_kwh_m2": 54.8, "pr_pct": 86.8},
        "2026-11": {"energy_mwh": 269.307, "irradiation_kwh_m2": 20.9, "pr_pct": 71.1},
        "2026-12": {"energy_mwh": 133.948, "irradiation_kwh_m2": 12.3, "pr_pct": 60.2},
    },
    # Källa: 15102025_PVsyst Fjällskär SRC Forecast [SLC].pdf
    #   PVsyst V7.4.8, variant "240502 - Fjällskär - SRC Forecast", TMY (Solcast).
    "fjallskar": {
        "2026-01": {"energy_mwh": 162.496, "irradiation_kwh_m2": 22.2, "pr_pct": 35.3},
        "2026-02": {"energy_mwh": 578.672, "irradiation_kwh_m2": 44.4, "pr_pct": 62.9},
        "2026-03": {"energy_mwh": 1906.061, "irradiation_kwh_m2": 109.2, "pr_pct": 84.1},
        "2026-04": {"energy_mwh": 2653.532, "irradiation_kwh_m2": 152.3, "pr_pct": 84.0},
        "2026-05": {"energy_mwh": 3219.227, "irradiation_kwh_m2": 186.0, "pr_pct": 83.4},
        "2026-06": {"energy_mwh": 3287.933, "irradiation_kwh_m2": 189.9, "pr_pct": 83.4},
        "2026-07": {"energy_mwh": 3039.040, "irradiation_kwh_m2": 176.7, "pr_pct": 82.9},
        "2026-08": {"energy_mwh": 2634.446, "irradiation_kwh_m2": 148.2, "pr_pct": 85.7},
        "2026-09": {"energy_mwh": 1915.975, "irradiation_kwh_m2": 105.5, "pr_pct": 87.5},
        "2026-10": {"energy_mwh": 923.979, "irradiation_kwh_m2": 56.6, "pr_pct": 78.7},
        "2026-11": {"energy_mwh": 272.215, "irradiation_kwh_m2": 22.2, "pr_pct": 59.2},
        "2026-12": {"energy_mwh": 82.863, "irradiation_kwh_m2": 14.3, "pr_pct": 27.9},
    },
    # Källa: 15102025_PVsyst Björke Bifacial SRC Forecast 4MW [SLC].pdf
    #   PVsyst V7.4.8, variant "240307 - Björke SRC Forecast - Bifacial cos(phi)",
    #   TMY (Solcast). 4 MW-varianten vald — matchar parkens ac_capacity_mwac.
    "bjorke": {
        "2026-01": {"energy_mwh": 23.939, "irradiation_kwh_m2": 17.0, "pr_pct": 20.3},
        "2026-02": {"energy_mwh": 146.345, "irradiation_kwh_m2": 38.7, "pr_pct": 54.5},
        "2026-03": {"energy_mwh": 546.949, "irradiation_kwh_m2": 100.6, "pr_pct": 78.3},
        "2026-04": {"energy_mwh": 832.705, "irradiation_kwh_m2": 146.1, "pr_pct": 82.1},
        "2026-05": {"energy_mwh": 978.614, "irradiation_kwh_m2": 175.5, "pr_pct": 80.3},
        "2026-06": {"energy_mwh": 971.119, "irradiation_kwh_m2": 179.6, "pr_pct": 77.9},
        "2026-07": {"energy_mwh": 959.333, "irradiation_kwh_m2": 175.6, "pr_pct": 78.7},
        "2026-08": {"energy_mwh": 769.660, "irradiation_kwh_m2": 139.3, "pr_pct": 79.6},
        "2026-09": {"energy_mwh": 530.305, "irradiation_kwh_m2": 91.0, "pr_pct": 84.0},
        "2026-10": {"energy_mwh": 268.796, "irradiation_kwh_m2": 50.1, "pr_pct": 77.2},
        "2026-11": {"energy_mwh": 52.886, "irradiation_kwh_m2": 17.0, "pr_pct": 44.9},
        "2026-12": {"energy_mwh": 8.749, "irradiation_kwh_m2": 11.4, "pr_pct": 11.0},
    },
    # Källa: 15102025_PVsyst Agerum SRC Forecast [SLC].pdf
    #   PVsyst V7.4.8, variant "240307 - Agerum - Forecast 6MW", TMY (Solcast).
    "agerum": {
        "2026-01": {"energy_mwh": 106.864, "irradiation_kwh_m2": 20.9, "pr_pct": 57.8},
        "2026-02": {"energy_mwh": 295.620, "irradiation_kwh_m2": 41.8, "pr_pct": 79.9},
        "2026-03": {"energy_mwh": 773.464, "irradiation_kwh_m2": 99.6, "pr_pct": 87.8},
        "2026-04": {"energy_mwh": 1126.752, "irradiation_kwh_m2": 151.8, "pr_pct": 83.9},
        "2026-05": {"energy_mwh": 1437.539, "irradiation_kwh_m2": 189.8, "pr_pct": 85.6},
        "2026-06": {"energy_mwh": 1385.689, "irradiation_kwh_m2": 188.0, "pr_pct": 83.3},
        "2026-07": {"energy_mwh": 1365.583, "irradiation_kwh_m2": 179.6, "pr_pct": 85.9},
        "2026-08": {"energy_mwh": 1153.807, "irradiation_kwh_m2": 151.5, "pr_pct": 86.1},
        "2026-09": {"energy_mwh": 841.904, "irradiation_kwh_m2": 108.7, "pr_pct": 87.6},
        "2026-10": {"energy_mwh": 445.026, "irradiation_kwh_m2": 59.1, "pr_pct": 85.1},
        "2026-11": {"energy_mwh": 144.921, "irradiation_kwh_m2": 22.8, "pr_pct": 71.8},
        "2026-12": {"energy_mwh": 65.181, "irradiation_kwh_m2": 13.3, "pr_pct": 55.4},
    },
    # Källa: 15102025_Hova_PVsyst SRC Forecast 5MW [SLC].pdf
    #   (finns även lokalt i Resultat/sol-kalldata/)
    #   PVsyst V7.4.8, variant "240423 - Hova - Forecast SRC 5MW", TMY (Solcast).
    #   Enda parken med tracker → högst PR i portföljen.
    "hova": {
        "2026-01": {"energy_mwh": 62.550, "irradiation_kwh_m2": 14.4, "pr_pct": 73.3},
        "2026-02": {"energy_mwh": 175.848, "irradiation_kwh_m2": 33.5, "pr_pct": 88.8},
        "2026-03": {"energy_mwh": 569.748, "irradiation_kwh_m2": 102.2, "pr_pct": 94.2},
        "2026-04": {"energy_mwh": 933.245, "irradiation_kwh_m2": 172.9, "pr_pct": 91.2},
        "2026-05": {"energy_mwh": 1147.464, "irradiation_kwh_m2": 217.6, "pr_pct": 89.1},
        "2026-06": {"energy_mwh": 1287.917, "irradiation_kwh_m2": 245.6, "pr_pct": 88.6},
        "2026-07": {"energy_mwh": 1143.080, "irradiation_kwh_m2": 218.7, "pr_pct": 88.3},
        "2026-08": {"energy_mwh": 873.457, "irradiation_kwh_m2": 164.7, "pr_pct": 89.6},
        "2026-09": {"energy_mwh": 549.343, "irradiation_kwh_m2": 102.0, "pr_pct": 91.0},
        "2026-10": {"energy_mwh": 267.636, "irradiation_kwh_m2": 50.8, "pr_pct": 89.0},
        "2026-11": {"energy_mwh": 71.092, "irradiation_kwh_m2": 15.4, "pr_pct": 78.2},
        "2026-12": {"energy_mwh": 29.132, "irradiation_kwh_m2": 8.5, "pr_pct": 57.8},
    },
    # Källa: 15102025_PVsyst Skakelbacken SRC Forecast [SLC].pdf
    #   PVsyst V7.4.8, variant "Skakelbacken - 6.5MW_SRC", TMY (Solcast).
    "skakelbacken": {
        "2026-01": {"energy_mwh": 30.401, "irradiation_kwh_m2": 21.7, "pr_pct": 21.6},
        "2026-02": {"energy_mwh": 162.626, "irradiation_kwh_m2": 43.7, "pr_pct": 57.3},
        "2026-03": {"energy_mwh": 568.365, "irradiation_kwh_m2": 104.9, "pr_pct": 83.3},
        "2026-04": {"energy_mwh": 819.426, "irradiation_kwh_m2": 144.5, "pr_pct": 87.2},
        "2026-05": {"energy_mwh": 954.311, "irradiation_kwh_m2": 165.1, "pr_pct": 88.9},
        "2026-06": {"energy_mwh": 994.117, "irradiation_kwh_m2": 173.2, "pr_pct": 88.3},
        "2026-07": {"energy_mwh": 912.593, "irradiation_kwh_m2": 159.2, "pr_pct": 88.2},
        "2026-08": {"energy_mwh": 754.096, "irradiation_kwh_m2": 131.0, "pr_pct": 88.6},
        "2026-09": {"energy_mwh": 522.983, "irradiation_kwh_m2": 91.2, "pr_pct": 88.3},
        "2026-10": {"energy_mwh": 270.860, "irradiation_kwh_m2": 53.3, "pr_pct": 78.2},
        "2026-11": {"energy_mwh": 66.533, "irradiation_kwh_m2": 19.7, "pr_pct": 52.0},
        "2026-12": {"energy_mwh": 8.315, "irradiation_kwh_m2": 14.3, "pr_pct": 8.9},
    },
    # Källa: 05052025_Stenstorp_Bifacial PVsyst RH SRC [MTNM]_Corrected.pdf
    #   (ligger i .../08 - Stenstorp/.../01 - PVsyst/archive/)
    #   PVsyst V7.4.8, variant "240605 - Stenstorp - GH - Bifacial_Corrected",
    #   TMY (Meteonorm). Avviker från de övriga sju som alla är oktober-2025-
    #   batchen med Solcast-väder.
    #   VARFÖR den äldre rapporten: det är den som ligger bakom parkens
    #   expected_annual_yield_kwh_kwp = 1008 och expected_pr_pct = 81.74 i
    #   park_product_data. Nyare rapport finns —
    #   "15102025_Stenstorp PVsyst Forecast Bifacial [SLC].pdf", variant
    #   "240605 - Stenstorp - RH - Bifacial_Corrected" — men den ger 956
    #   kWh/kWp och PR 82.50 %, dvs -5.2 % årsproduktion. Att använda den här
    #   skulle göra budgeten inkonsistent med park_product_data. Uppdatera BÅDA
    #   ställena samtidigt om portföljen ska byta till Solcast-underlaget.
    "stenstorp": {
        "2026-01": {"energy_mwh": 6.196, "irradiation_kwh_m2": 18.6, "pr_pct": 29.5},
        "2026-02": {"energy_mwh": 27.683, "irradiation_kwh_m2": 43.2, "pr_pct": 56.5},
        "2026-03": {"energy_mwh": 97.881, "irradiation_kwh_m2": 113.1, "pr_pct": 76.4},
        "2026-04": {"energy_mwh": 149.141, "irradiation_kwh_m2": 149.4, "pr_pct": 88.1},
        "2026-05": {"energy_mwh": 178.547, "irradiation_kwh_m2": 178.0, "pr_pct": 88.6},
        "2026-06": {"energy_mwh": 180.342, "irradiation_kwh_m2": 182.2, "pr_pct": 87.4},
        "2026-07": {"energy_mwh": 174.983, "irradiation_kwh_m2": 178.6, "pr_pct": 86.5},
        "2026-08": {"energy_mwh": 145.496, "irradiation_kwh_m2": 146.3, "pr_pct": 87.8},
        "2026-09": {"energy_mwh": 110.172, "irradiation_kwh_m2": 118.1, "pr_pct": 82.4},
        "2026-10": {"energy_mwh": 54.638, "irradiation_kwh_m2": 68.5, "pr_pct": 70.4},
        "2026-11": {"energy_mwh": 14.858, "irradiation_kwh_m2": 27.4, "pr_pct": 47.9},
        "2026-12": {"energy_mwh": 2.324, "irradiation_kwh_m2": 10.2, "pr_pct": 20.1},
    },
    # Källa: 15102025_PVsyst Tången SRC Forecast [SLC].pdf
    #   PVsyst V7.4.8, variant "250916 - As-built simulation_AM_SRC final",
    #   TMY (Solcast). Enda rapporten som är en as-built-simulering.
    "tangen": {
        "2026-01": {"energy_mwh": 67.708, "irradiation_kwh_m2": 18.8, "pr_pct": 53.6},
        "2026-02": {"energy_mwh": 187.147, "irradiation_kwh_m2": 38.7, "pr_pct": 71.9},
        "2026-03": {"energy_mwh": 546.281, "irradiation_kwh_m2": 94.1, "pr_pct": 86.3},
        "2026-04": {"energy_mwh": 885.187, "irradiation_kwh_m2": 148.6, "pr_pct": 88.5},
        "2026-05": {"energy_mwh": 1086.176, "irradiation_kwh_m2": 187.1, "pr_pct": 86.3},
        "2026-06": {"energy_mwh": 1062.814, "irradiation_kwh_m2": 188.3, "pr_pct": 83.9},
        "2026-07": {"energy_mwh": 1029.536, "irradiation_kwh_m2": 178.8, "pr_pct": 85.6},
        "2026-08": {"energy_mwh": 864.187, "irradiation_kwh_m2": 147.9, "pr_pct": 86.9},
        "2026-09": {"energy_mwh": 633.828, "irradiation_kwh_m2": 106.1, "pr_pct": 88.8},
        "2026-10": {"energy_mwh": 305.700, "irradiation_kwh_m2": 54.6, "pr_pct": 83.2},
        "2026-11": {"energy_mwh": 99.910, "irradiation_kwh_m2": 20.8, "pr_pct": 71.6},
        "2026-12": {"energy_mwh": 42.623, "irradiation_kwh_m2": 11.8, "pr_pct": 53.8},
    },
}


# --- Modul-degradering ---
# Årlig effektförlust efter COD, i procent av föregående års kapacitet.
# 0,5 %/år är branschstandard för de N-typ TOPCon-moduler portföljen använder
# och ligger i linje med degraderingsantagandena i PVsyst-rapporterna.
#
# ANVÄNDS INTE ÄNNU. PARK_BUDGET_OVERRIDES ovan är rena TMY-värden för
# simuleringsår 1 — ingen degradering är inbakad. Konstanten ligger här för
# nästa våg, där budgeten ska skalas med (1 - d)^(år sedan COD).
PARK_DEGRADATION_PCT_PER_YEAR: float = 0.5


# ---------------------------------------------------------------------------
# PPA-konfiguration per park
# ---------------------------------------------------------------------------
#
# Källa: Asset Value Master (project_info-fliken). Pris i SEK/MWh (native
# kontraktsvaluta). Konvertering till EUR sker per 15-min med samma EXR
# som spotpriserna (kolumn EXR i quarterly-CSV:erna), så att PPA-värdering
# ligger i samma valutavärld som realiserad spot-revenue.
#
# Hur den används:
#   * unified_dashboard räknar ut två varianter av realiserad intäkt:
#       - "spot"  : volym × spotpris  (100% spot, ingen PPA-hedge)
#       - "ppa"   : volym × (share × ppa_eur(t) + (1-share) × spotpris(t))
#         där ppa_eur(t) = price_sek_mwh / EXR(t).
#   * Toggle i dashboarden växlar mellan dessa två. Default = PPA på när
#     parken har en post här (annars spot).
#   * PPA är knuten till FAKTISK genererad volym — ingen volym = ingen PPA-
#     ersättning (downtime/curtailment trycker ner båda).
#   * Pris är fast SEK/MWh hela perioden (ingen indexering/inflation).
#     Varierande EUR-tal i rapporter beror på FX-fluktuationer.
#
# Format:
#   "park_key": {
#       "price_sek_mwh": <fast PPA-pris i SEK per MWh>,
#       "share_pct":     <andel av producerad volym, 0-100>,
#   }
# Sätt None / utelämna parken / share_pct=0 för att tvinga 100% spot.
PARK_PPA: dict[str, dict] = {
    # Pris i bilden från Asset Value Master är SEK/kWh → ×1000 = SEK/MWh.
    "fjallskar":    {"price_sek_mwh": 465.0, "share_pct": 70.0},
    "horby":        {"price_sek_mwh": 525.0, "share_pct": 70.0},
    "bjorke":       {"price_sek_mwh": 614.0, "share_pct": 70.0},
    "agerum":       {"price_sek_mwh": 819.0, "share_pct": 70.0},
    "hova":         {"price_sek_mwh": 645.0, "share_pct": 70.0},
    "skakelbacken": {"price_sek_mwh": 619.0, "share_pct": 100.0},
    "tangen":       {"price_sek_mwh": 582.0, "share_pct": 70.0},
    # Stenstorp har inget PPA-kontrakt enligt master → 100% spot.
    # "stenstorp": {...},
}


def get_ppa(park_key: str) -> Optional[dict]:
    """Returnera PPA-konfig för en park, eller None om inget kontrakt.

    Returvärde:
        ``{"price_sek_mwh": float, "share_pct": float}`` eller ``None``.
    """
    p = PARK_PPA.get(park_key)
    if p is None:
        return None
    share = float(p.get("share_pct", 0.0) or 0.0)
    if share <= 0:
        return None
    price = p.get("price_sek_mwh")
    if price is None:
        return None
    return {
        "price_sek_mwh": float(price),
        "share_pct": share,
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
