#!/usr/bin/env python3
"""Discover all inverter objects in Bazefield and generate inverter_registry.py.

Engångsskript som hämtar hela object-strukturen från Bazefield,
filtrerar ut alla inverter-objekt (HRB-TS1-INV04 etc.), grupperar per
park, och genererar `elpris/inverter_registry.py` med en statisk
`PARK_INVERTERS` dict.

Körs:
    python discover_inverters.py

Ska köras en gång initialt och vid nya parker eller inverter-ändringar.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

import requests

from elpris.bazefield import BAZEFIELD_BASE_URL, BAZEFIELD_API_KEY, PARKS
from elpris.park_product_data import PARK_PRODUCT_DATA


# Rated kW per invertermodell (från datablad)
INVERTER_RATED_KW: dict[str, float] = {
    "Sineng SP-275K-H1": 275.0,
    "Huawei SUN2000-330KTL-H1": 330.0,
    "Sungrow SG350HX-15A": 350.0,
}

# Inverter-namngivning (t.ex. "HRB-TS1-INV04")
_INVERTER_PATTERN = re.compile(r"^[A-Z]+-TS\d+-INV\d+$")
_TS_PATTERN = re.compile(r"^([A-Z]+)-(TS\d+)-INV\d+$")


def fetch_structure(root_object_id: str) -> list[dict]:
    """Hämta hela object-strukturen från Bazefield.

    Returnerar alla objekt (oavsett trädposition) som platt lista med
    attributes inklusive objectId, objectKey, parentId.
    """
    headers = {
        "Authorization": f"Bearer {BAZEFIELD_API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    url = f"{BAZEFIELD_BASE_URL}/json/reply/ObjectStructureGetRequest"
    r = requests.post(url, json={"ObjectId": root_object_id}, headers=headers, timeout=60)
    r.raise_for_status()
    data = r.json()
    return data.get("data", [])


def discover() -> dict[str, list[dict]]:
    """Bygg PARK_INVERTERS-mappning genom discovery.

    1. Hämta hela strukturen (via Hörbys park-ID som rot — API:t returnerar
       alla objekt oavsett rot-ID)
    2. Bygg parent-mapping: objectId → parentId
    3. Filtrera inverter-objekt via regex
    4. För varje inverter, följ parent-kedjan: INV → TS → park
    5. Mappa park_id → park_key via PARKS
    6. Slå upp rated_kw från park_product_data
    7. Sortera inverter-listan alfabetiskt per park
    """
    print("Hämtar object-struktur från Bazefield...")
    horby_id = PARKS["horby"]["id"]
    all_objects = fetch_structure(horby_id)
    print(f"  {len(all_objects)} objekt totalt i systemet")

    # Bygg lookup: objectId → attributes
    obj_by_id: dict[str, dict] = {}
    for obj in all_objects:
        attrs = obj.get("attributes", {})
        oid = obj.get("objectId") or attrs.get("objectId")
        if oid:
            obj_by_id[oid] = attrs

    # Bygg park_id → park_key mapping
    park_id_to_key = {park["id"]: key for key, park in PARKS.items()}

    # Filtrera inverter-objekt
    # För inverter-objekt: parentId = parkens ID direkt, immediateParentId = TS
    inverters_raw: list[dict] = []
    for obj in all_objects:
        attrs = obj.get("attributes", {})
        key = attrs.get("objectKey", "")
        if _INVERTER_PATTERN.match(key):
            oid = obj.get("objectId") or attrs.get("objectId")
            if oid:
                # Använd ratedPower från Bazefield om tillgängligt
                rated_str = attrs.get("ratedPower", "0")
                try:
                    rated_kw_from_attr = float(rated_str) if rated_str else 0.0
                except (ValueError, TypeError):
                    rated_kw_from_attr = 0.0

                inverters_raw.append({
                    "id": oid,
                    "name": key,
                    "park_id": attrs.get("parentId"),  # Parken direkt!
                    "ts_id": attrs.get("immediateParentId"),  # TS-objektet
                    "rated_kw_bazefield": rated_kw_from_attr,
                })

    print(f"  {len(inverters_raw)} inverter-objekt hittade")

    # Gruppera per park — parentId pekar direkt på parken för inverter-objekt
    result: dict[str, list[dict]] = {key: [] for key in PARKS}
    unresolved = 0
    for inv in inverters_raw:
        park_key = park_id_to_key.get(inv["park_id"])
        if not park_key:
            unresolved += 1
            print(f"  [WARN] Kunde inte mappa {inv['name']} till park (park_id={inv['park_id']})")
            continue

        # Extrahera transformer-grupp från namnet
        m = _TS_PATTERN.match(inv["name"])
        transformer = m.group(2) if m else ""

        # Rated kW: använd Bazefield-attributet om rimligt, annars lookup via modell
        rated_kw = inv["rated_kw_bazefield"]
        if rated_kw <= 0 or rated_kw > 1000:
            product = PARK_PRODUCT_DATA.get(park_key, {})
            inverter_model = product.get("inverter_model", "")
            rated_kw = INVERTER_RATED_KW.get(inverter_model, 0.0)

        result[park_key].append({
            "name": inv["name"],
            "id": inv["id"],
            "transformer": transformer,
            "rated_kw": rated_kw,
        })

    if unresolved:
        print(f"  [WARN] {unresolved} invertrar kunde inte mappas till park")

    # Sortera varje parks lista alfabetiskt på namn
    for park_key in result:
        result[park_key].sort(key=lambda inv: inv["name"])

    return result


def validate(registry: dict[str, list[dict]]) -> bool:
    """Validera count per park mot PARK_PRODUCT_DATA.num_inverters."""
    all_ok = True
    print("\nValidering mot park_product_data.num_inverters:")
    for park_key in PARKS:
        actual = len(registry.get(park_key, []))
        expected = PARK_PRODUCT_DATA.get(park_key, {}).get("num_inverters", 0)
        status = "OK" if actual == expected else "MISMATCH"
        marker = "[OK]" if actual == expected else "[!!]"
        print(f"  {marker} {park_key:15s}: {actual:3d} faktiska vs {expected:3d} förväntade  {status}")
        if actual != expected:
            all_ok = False
    return all_ok


def render_module(registry: dict[str, list[dict]]) -> str:
    """Rendera Python-modul som sträng."""
    today = date.today().isoformat()

    lines = [
        '"""Inverter registry för Svea Solars solparker.',
        "",
        f"Auto-genererad av discover_inverters.py den {today}.",
        "Redigera inte för hand — regenerera via:",
        "    python discover_inverters.py",
        "",
        "Mappar varje park till en lista av inverter-objekt med deras",
        "Bazefield object_id, namn, transformator-grupp och rated capacity.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "# Rated power (kW) per invertermodell (från datablad)",
        "INVERTER_RATED_KW: dict[str, float] = {",
    ]
    for model, kw in INVERTER_RATED_KW.items():
        lines.append(f'    "{model}": {kw},')
    lines.append("}")
    lines.append("")
    lines.append("")
    lines.append("PARK_INVERTERS: dict[str, list[dict]] = {")

    for park_key in PARKS:  # Använd PARKS-ordning för konsistent output
        inverters = registry.get(park_key, [])
        if not inverters:
            lines.append(f'    "{park_key}": [],')
            continue
        lines.append(f'    "{park_key}": [')
        for inv in inverters:
            lines.append(
                f'        {{"name": "{inv["name"]}", '
                f'"id": "{inv["id"]}", '
                f'"transformer": "{inv["transformer"]}", '
                f'"rated_kw": {inv["rated_kw"]}}},'
            )
        lines.append("    ],")

    lines.append("}")
    lines.append("")
    lines.append("")
    lines.append("def get_inverters(park_key: str) -> list[dict]:")
    lines.append('    """Returnera lista av inverter-dicts för en park."""')
    lines.append("    return PARK_INVERTERS.get(park_key, [])")
    lines.append("")
    lines.append("")
    lines.append("def count_inverters(park_key: str) -> int:")
    lines.append('    """Returnera antal invertrar för en park."""')
    lines.append("    return len(PARK_INVERTERS.get(park_key, []))")
    lines.append("")
    lines.append("")
    lines.append("def total_inverters() -> int:")
    lines.append('    """Returnera totalt antal invertrar över alla parker."""')
    lines.append("    return sum(len(invs) for invs in PARK_INVERTERS.values())")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    if not BAZEFIELD_API_KEY:
        print("FEL: BAZEFIELD_API_KEY saknas. Sätt i .env eller miljövariabel.")
        return 1

    print("=" * 60)
    print("Svea Solar — Inverter Discovery")
    print("=" * 60)
    print()

    registry = discover()

    total = sum(len(invs) for invs in registry.values())
    print(f"\nDiscovery klar: {total} invertrar över {len(PARKS)} parker")

    all_ok = validate(registry)

    # Skriv ut modulen
    output_path = Path(__file__).parent / "elpris" / "inverter_registry.py"
    content = render_module(registry)
    output_path.write_text(content, encoding="utf-8")
    print(f"\nSkrev {output_path}")
    print(f"  {len(content)} bytes, {content.count(chr(10))} rader")

    if not all_ok:
        print("\n[WARN] Validering misslyckades — kontrollera antal invertrar manuellt")
        return 2

    print("\n[OK] Allt validerat OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
