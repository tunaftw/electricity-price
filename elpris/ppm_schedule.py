"""Preventive Maintenance (PPM) schema för solparker.

Innehåller statisk konfiguration av förebyggande underhållstasks som
visas i månadsrapportens sektion 16 som en kalendermatris.

Datakällan är generisk — baserat på standarder för solparker i Sverige
och vad som visades i K-energy/Anayia-referensrapporten. Kan utökas med
parkspecifika overrides om det behövs (t.ex. tracker-kalibrering för Hova).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Default PPM-tasks (gäller alla parker om inga overrides finns)
# ---------------------------------------------------------------------------

# Varje task har:
#   task:      Beskrivning på svenska
#   frequency: "biannual" (halvårsvis) eller "annual" (årligen)
#   months:    Lista med månadsnummer (1-12) då task är schemalagd
PPM_TASKS_DEFAULT: list[dict] = [
    # --- Halvårsvisa tasks (mars + september typiskt) ---
    {
        "task": "Visuell inspektion paneler",
        "frequency": "biannual",
        "months": [3, 9],
    },
    {
        "task": "Vegetationskontroll och gräsklippning",
        "frequency": "biannual",
        "months": [5, 9],
    },
    {
        "task": "Kontroll staket, grindar och skalskydd",
        "frequency": "biannual",
        "months": [4, 10],
    },
    {
        "task": "Väderstation och sensorer — kalibrering",
        "frequency": "biannual",
        "months": [3, 9],
    },
    {
        "task": "Kontroll mekaniska komponenter",
        "frequency": "biannual",
        "months": [4, 10],
    },
    {
        "task": "Kontroll elektriska anslutningar och panelkablage",
        "frequency": "biannual",
        "months": [3, 9],
    },
    # --- Årliga tasks ---
    {
        "task": "Termografi MV/HV-anläggning (IEC 62446)",
        "frequency": "annual",
        "months": [6],
    },
    {
        "task": "Inverter-underhåll",
        "frequency": "annual",
        "months": [10],
    },
    {
        "task": "Transformator-underhåll (MV-switchgear)",
        "frequency": "annual",
        "months": [10],
    },
    {
        "task": "Brandskyddskontroll (släckare)",
        "frequency": "annual",
        "months": [6],
    },
    {
        "task": "Inspektion byggnader, ställverk och RTU",
        "frequency": "annual",
        "months": [3],
    },
]


# ---------------------------------------------------------------------------
# Parkspecifika overrides (valfritt — för parker med extra underhållsbehov)
# ---------------------------------------------------------------------------

# Tracker-park som Hova har extra underhållstasks för rörliga delar.
# Övriga parker använder default-listan.
PARK_PPM_OVERRIDES: dict[str, list[dict]] = {
    "hova": PPM_TASKS_DEFAULT + [
        {
            "task": "Tracker — mekanisk kontroll och smörjning",
            "frequency": "biannual",
            "months": [4, 10],
        },
        {
            "task": "Tracker — styrsystem och backtracking-verifiering",
            "frequency": "annual",
            "months": [5],
        },
    ],
}


# ---------------------------------------------------------------------------
# Publika funktioner
# ---------------------------------------------------------------------------

def get_ppm_schedule(park_key: str) -> list[dict]:
    """Hämta PPM-schemat för en specifik park.

    Returnerar parkspecifik lista om det finns en override, annars
    default-listan.

    Args:
        park_key: Parknyckel (t.ex. "horby", "hova")

    Returns:
        Lista med PPM-tasks, var och en är dict med task, frequency, months.
    """
    return PARK_PPM_OVERRIDES.get(park_key, PPM_TASKS_DEFAULT)


def is_scheduled(task: dict, month: int) -> bool:
    """Kontrollera om en task är schemalagd för en given månad."""
    return month in task.get("months", [])
