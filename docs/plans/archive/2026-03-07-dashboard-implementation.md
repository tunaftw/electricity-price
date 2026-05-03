# Elpris Dashboard v1 — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bygg ett Python-skript som genererar en självständig HTML-dashboard med Plotly.js för att visualisera svenska elpriser och capture prices.

**Architecture:** Python-skript (`generate_dashboard.py`) läser quarterly-prisdata och solprofiler via befintliga moduler (`elpris/capture.py`, `elpris/solar_profile.py`), beräknar baseload- och capture-priser per månad/år/zon/profil, serialiserar till JSON och bäddar in i en HTML-template med Plotly.js (CDN). Output: en enda HTML-fil i `Resultat/rapporter/`.

**Tech Stack:** Python 3, Plotly.js (CDN), HTML/CSS/JS, befintliga elpris-moduler.

---

### Task 1: Databeräkningsmodul (`elpris/dashboard_data.py`)

Skapar modulen som aggregerar all data dashboarden behöver. Återanvänder `capture.py` och `solar_profile.py`.

**Files:**
- Create: `elpris/dashboard_data.py`
- Read: `elpris/capture.py`, `elpris/solar_profile.py`, `elpris/config.py`

**Step 1: Skapa `elpris/dashboard_data.py` med databeräkning**

Modulen ska:
1. Läsa quarterly-prisdata per zon (EUR_per_kWh → EUR/MWh)
2. Beräkna baseload-pris per månad och år
3. Beräkna capture price per månad och år för varje solprofil
4. Returnera allt som en dict redo för JSON-serialisering

```python
"""Dashboard data aggregation — beräknar baseload och capture prices."""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path

from .config import ZONES, QUARTERLY_DIR
from .solar_profile import get_quarterly_solar_weight, list_available_profiles

# Profiler att inkludera i dashboarden
DASHBOARD_PROFILES = {
    "south_lundby": "Syd (Lundby)",
    "ew_boda": "Öst-Väst (Böda)",
    "tracker_sweden": "Tracker (Hova)",
    "entsoe_solar_SE1": "ENTSO-E Sol SE1",
    "entsoe_solar_SE2": "ENTSO-E Sol SE2",
    "entsoe_solar_SE3": "ENTSO-E Sol SE3",
    "entsoe_solar_SE4": "ENTSO-E Sol SE4",
}


def read_quarterly_prices(zone: str) -> list[dict]:
    """Läs all quarterly-prisdata för en zon."""
    zone_dir = QUARTERLY_DIR / zone
    if not zone_dir.exists():
        return []

    records = []
    for csv_file in sorted(zone_dir.glob("*.csv")):
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = datetime.fromisoformat(row["time_start"])
                records.append({
                    "timestamp": ts,
                    "eur_mwh": float(row["EUR_per_kWh"]) * 1000,
                })
    return records


def calculate_dashboard_data() -> dict:
    """
    Beräkna all data som dashboarden behöver.

    Returns:
        Dict med structure:
        {
            "generated": "2026-03-07T12:00:00",
            "zones": ["SE1", "SE2", "SE3", "SE4"],
            "profiles": {"south_lundby": "Syd (Lundby)", ...},
            "yearly": {
                "SE1": [
                    {"year": 2022, "baseload": 45.2,
                     "capture": {"south_lundby": 38.1, ...},
                     "ratio": {"south_lundby": 0.84, ...},
                     "records": 8760}
                ]
            },
            "monthly": {
                "SE1": [
                    {"year": 2022, "month": 1, "baseload": 52.3,
                     "capture": {"south_lundby": 42.1, ...},
                     "ratio": {"south_lundby": 0.81, ...},
                     "records": 744}
                ]
            }
        }
    """
    # Filtrera profiler till de som faktiskt finns tillgängliga
    available = set(list_available_profiles())
    profiles = {k: v for k, v in DASHBOARD_PROFILES.items() if k in available}

    result = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "zones": list(ZONES),
        "profiles": profiles,
        "yearly": {},
        "monthly": {},
    }

    for zone in ZONES:
        print(f"  Beräknar {zone}...")
        records = read_quarterly_prices(zone)
        if not records:
            continue

        # Gruppera per år och månad
        monthly_buckets = defaultdict(lambda: {
            "prices": [],
            "weighted": defaultdict(float),
            "weights": defaultdict(float),
        })

        for rec in records:
            ts = rec["timestamp"]
            price = rec["eur_mwh"]
            key = (ts.year, ts.month)

            bucket = monthly_buckets[key]
            bucket["prices"].append(price)

            for profile_name in profiles:
                w = get_quarterly_solar_weight(ts, profile_name)
                bucket["weighted"][profile_name] += price * w
                bucket["weights"][profile_name] += w

        # Bygg månadsdata
        monthly_list = []
        for (year, month) in sorted(monthly_buckets.keys()):
            bucket = monthly_buckets[(year, month)]
            n = len(bucket["prices"])
            baseload = sum(bucket["prices"]) / n if n > 0 else 0

            capture = {}
            ratio = {}
            for p_name in profiles:
                w_sum = bucket["weights"][p_name]
                if w_sum > 0:
                    cap = bucket["weighted"][p_name] / w_sum
                    capture[p_name] = round(cap, 2)
                    ratio[p_name] = round(cap / baseload, 3) if baseload > 0 else None
                else:
                    capture[p_name] = None
                    ratio[p_name] = None

            monthly_list.append({
                "year": year,
                "month": month,
                "baseload": round(baseload, 2),
                "capture": capture,
                "ratio": ratio,
                "records": n,
            })

        result["monthly"][zone] = monthly_list

        # Bygg årsdata (aggregera månaderna)
        yearly_buckets = defaultdict(lambda: {
            "prices": [],
            "weighted": defaultdict(float),
            "weights": defaultdict(float),
        })

        for (year, month) in monthly_buckets:
            bucket = monthly_buckets[(year, month)]
            yb = yearly_buckets[year]
            yb["prices"].extend(bucket["prices"])
            for p_name in profiles:
                yb["weighted"][p_name] += bucket["weighted"][p_name]
                yb["weights"][p_name] += bucket["weights"][p_name]

        yearly_list = []
        for year in sorted(yearly_buckets.keys()):
            yb = yearly_buckets[year]
            n = len(yb["prices"])
            baseload = sum(yb["prices"]) / n if n > 0 else 0

            capture = {}
            ratio = {}
            for p_name in profiles:
                w_sum = yb["weights"][p_name]
                if w_sum > 0:
                    cap = yb["weighted"][p_name] / w_sum
                    capture[p_name] = round(cap, 2)
                    ratio[p_name] = round(cap / baseload, 3) if baseload > 0 else None
                else:
                    capture[p_name] = None
                    ratio[p_name] = None

            yearly_list.append({
                "year": year,
                "baseload": round(baseload, 2),
                "capture": capture,
                "ratio": ratio,
                "records": n,
            })

        result["yearly"][zone] = yearly_list

    return result
```

**Step 2: Testa modulen manuellt**

Run: `cd "C:/Users/PontusSkog/Developer/electricity prices" && python3 -c "from elpris.dashboard_data import calculate_dashboard_data; import json; d = calculate_dashboard_data(); print(json.dumps({k: v for k, v in d.items() if k != 'monthly' and k != 'yearly'}, indent=2)); print(f'Zoner med data: {list(d[\"yearly\"].keys())}'); print(f'Antal år SE3: {len(d[\"yearly\"].get(\"SE3\", []))}')"`

Expected: Utskrift med genererat datum, zoner, profiler, och bekräftelse att SE3 har 5-6 år data.

**Step 3: Commit**

```bash
git add elpris/dashboard_data.py
git commit -m "feat: add dashboard data aggregation module"
```

---

### Task 2: HTML-dashboard generator (`generate_dashboard.py`)

Skapar Python-skriptet som genererar den självständiga HTML-filen.

**Files:**
- Create: `generate_dashboard.py`
- Read: `elpris/dashboard_data.py` (Task 1)

**Step 1: Skapa `generate_dashboard.py`**

Skriptet ska:
1. Anropa `calculate_dashboard_data()` för att hämta all data
2. Bädda in datan som JSON i en HTML-template
3. Inkludera Plotly.js via CDN
4. Generera tre sektioner: Årsöversikt, Månadsvy, Trendanalys
5. Spara till `Resultat/rapporter/dashboard_elpris_YYYYMMDD.html`

HTML-strukturen:
- Responsiv layout med CSS Grid
- Mörkt/ljust tema (professionellt)
- Navigation mellan sektioner med tabs
- Plotly-grafer med hover, zoom, pan
- Tabeller med färgkodning
- Dropdown-filter för zon och profil

```python
"""Generate self-contained electricity price dashboard as HTML."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from elpris.dashboard_data import calculate_dashboard_data
from elpris.config import PROJECT_ROOT


def generate_html(data: dict) -> str:
    """Generera komplett HTML-dashboard med inbäddad data."""

    data_json = json.dumps(data, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Elpris Dashboard — Sverige</title>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <!-- Styles and scripts will be extensive — see implementation -->
</head>
<body>
    <!-- Full dashboard implementation -->
    <script>
    const DATA = {data_json};
    // Dashboard initialization and rendering
    </script>
</body>
</html>"""


def main():
    print("Genererar dashboard...")
    print("Steg 1: Beräknar data...")
    data = calculate_dashboard_data()

    print("Steg 2: Genererar HTML...")
    html = generate_html(data)

    output_dir = PROJECT_ROOT / "Resultat" / "rapporter"
    output_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d")
    output_path = output_dir / f"dashboard_elpris_{date_str}.html"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Dashboard sparad: {output_path}")
    size_kb = output_path.stat().st_size / 1024
    print(f"Filstorlek: {size_kb:.0f} KB")


if __name__ == "__main__":
    main()
```

**Step 2: Implementera komplett HTML/CSS/JS**

Den fullständiga HTML-filen ska innehålla:

**CSS (inbäddad):**
- Professionell typografi (system fonts)
- Färgpalett: blå/teal primärfärger, vit bakgrund, grå tabeller
- Responsiv layout med CSS Grid (sidebar + main)
- Tab-navigation (Årsöversikt / Månadsvy / Trendanalys)
- Färgkodade tabeller (grön=bra capture ratio, röd=dålig)
- Print-vänlig

**JS — Sektion 1: Årsöversikt:**
- Tabell: År × Zon med baseload, capture (default syd), capture ratio
- Plotly grupperat stapeldiagram: baseload vs capture per år, alla zoner
- Dropdown för att byta solprofil i tabellen

**JS — Sektion 2: Månadsvy:**
- Dropdown: välj år (ett eller flera), välj zon
- Tabell: Månad × (baseload, capture syd, capture öv, capture tracker, ratio)
- Plotly linjediagram: baseload + alla capture-profiler per månad
- Möjlighet att jämföra år (overlay-läge)

**JS — Sektion 3: Trendanalys:**
- Plotly linjediagram: capture price och ratio över hela historiken (månad för månad)
- Dropdown: välj zon, välj profil(er)
- Baseload som referenslinje
- Capture ratio som sekundär y-axel

**Step 3: Testa generering och öppna i webbläsare**

Run: `cd "C:/Users/PontusSkog/Developer/electricity prices" && python3 generate_dashboard.py`

Expected: HTML-fil genererad i `Resultat/rapporter/`, öppna i webbläsaren och verifiera att:
- Alla tre sektioner renderar
- Tabeller har data för SE1-SE4
- Grafer är interaktiva (hover, zoom)
- Dropdown-filter fungerar

**Step 4: Commit**

```bash
git add generate_dashboard.py
git commit -m "feat: add dashboard HTML generator with Plotly.js"
```

---

### Task 3: Årsöversikt — tabell och graf

Implementera den fullständiga årsöversikten med interaktiv tabell och Plotly-graf.

**Files:**
- Modify: `generate_dashboard.py` (HTML/CSS/JS)

**Step 1: Implementera årsöversiktens tabell**

- Kolumner: År, Zon, Baseload (EUR/MWh), Capture Syd, Capture ÖV, Capture Tracker, Ratio Syd
- Färgkodning: capture ratio > 0.9 = grön, 0.7-0.9 = gul, < 0.7 = röd
- Dropdown ovanför tabellen för att välja vilken profil som visas som primär

**Step 2: Implementera årsöversiktens graf**

- Plotly grupperat stapeldiagram
- X-axel: år, grupperat per zon
- Y-axel: EUR/MWh
- Staplar: baseload (blå), capture syd (orange), capture tracker (grön)
- Hover: visa exakta värden + ratio

**Step 3: Testa**

Run: `python3 generate_dashboard.py`
Verifiera i webbläsaren att tabell + graf renderar korrekt med rätt data.

**Step 4: Commit**

```bash
git add generate_dashboard.py
git commit -m "feat: implement yearly overview with table and chart"
```

---

### Task 4: Månadsvy — jämförelse och filtrering

**Files:**
- Modify: `generate_dashboard.py`

**Step 1: Implementera månadsvy med filter**

- Dropdown: Välj zon (SE1-SE4)
- Dropdown/checkboxes: Välj år att visa (multi-select)
- Tabell: Jan-Dec med baseload + capture per profil
- Plotly linjediagram: en linje per profil, x=månad, y=EUR/MWh
- Overlay-läge: jämför samma månad över olika år

**Step 2: Testa interaktivitet**

Verifiera att:
- Byta zon uppdaterar tabell + graf
- Välja olika år fungerar
- Grafen visar rätt data

**Step 3: Commit**

```bash
git add generate_dashboard.py
git commit -m "feat: implement monthly view with zone/year filtering"
```

---

### Task 5: Trendanalys — historisk linjegraf

**Files:**
- Modify: `generate_dashboard.py`

**Step 1: Implementera trendanalys**

- Plotly linjediagram med alla månader i kronologisk ordning (x-axel: 2021-11 → 2026-03)
- Y1: EUR/MWh (baseload + capture price)
- Y2: Capture ratio (sekundär y-axel)
- Dropdown: välj zon, välj profil(er) att visa
- Baseload som tjock referenslinje

**Step 2: Testa**

Verifiera att trendgrafen visar koherent data, zoom fungerar, och profiler kan togglas.

**Step 3: Commit**

```bash
git add generate_dashboard.py
git commit -m "feat: implement trend analysis with dual-axis chart"
```

---

### Task 6: Visuell polish och pedagogiska element

**Files:**
- Modify: `generate_dashboard.py`

**Step 1: Lägg till pedagogiska element**

- Header med titel, genereringsdatum, och kort beskrivning
- Info-ikoner/tooltips som förklarar begrepp (baseload, capture price, capture ratio)
- Förklarande text under varje sektion
- Footer med datakällor och metodik

**Step 2: Visuell polish**

- Konsekvent färgpalett genom hela dashboarden
- Snygga tabellhuvuden med sticky header
- Animerade transitions mellan tabs
- Responsiv design (fungerar på laptop och stor skärm)
- Plotly-tema: clean, minimalistiskt, konsekventa färger

**Step 3: Sluttest**

Generera dashboarden en sista gång och verifiera:
- Helhetsintryck: professionellt och pedagogiskt
- All data korrekt (stickprova mot befintlig capture-rapport)
- Fungerar i Chrome, Edge
- Filstorlek rimlig (bör vara < 5 MB med all data inbäddad)

**Step 4: Commit**

```bash
git add generate_dashboard.py
git commit -m "feat: add visual polish and pedagogical elements to dashboard"
```

---

### Task 7: Integration med update-kedjan

**Files:**
- Modify: `update_all.py`
- Modify: `CLAUDE.md` (dokumentation)

**Step 1: Lägg till dashboard-generering i `update_all.py`**

Lägg till som sista steg efter Excel-rapporter:
```python
# Step 9: Generate dashboard
print("Steg 9: Genererar dashboard...")
from generate_dashboard import main as generate_dashboard
generate_dashboard()
```

**Step 2: Uppdatera CLAUDE.md**

Lägg till `generate_dashboard.py` i projektstrukturen och kommandon.

**Step 3: Commit**

```bash
git add update_all.py CLAUDE.md
git commit -m "feat: integrate dashboard generation into update pipeline"
```

---

## Sammanfattning

| Task | Beskrivning | Beroende |
|------|-------------|----------|
| 1 | Databeräkningsmodul | — |
| 2 | HTML-generator (skelett) | Task 1 |
| 3 | Årsöversikt (tabell + graf) | Task 2 |
| 4 | Månadsvy (filter + jämförelse) | Task 2 |
| 5 | Trendanalys (linjegraf) | Task 2 |
| 6 | Visuell polish | Task 3, 4, 5 |
| 7 | Integration med update-kedjan | Task 6 |

Tasks 3, 4, 5 kan köras parallellt efter Task 2.
