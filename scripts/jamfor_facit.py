#!/usr/bin/env python3
"""Jämför Översikts data mot ett sparat facit (--save-data) och visar skillnader i tal.

Textfält (inledningar, flaggor, etiketter, definitioner) får ändras när
gränssnittet översätts; talen får inte ändras. Nya nycklar i den nya datan
(t.ex. ``tillagg``) rapporteras men räknas inte som avvikelser.

    python scripts/jamfor_facit.py facit.json ny.json
"""

from __future__ import annotations

import json
import sys

TEXT_KEYS = {"generated", "dataset", "definitions", "lede", "flags", "text", "delivery", "data_end_label",
             "group", "name", "source", "park"}


def walk(a, b, path, out):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in a:
            if k in TEXT_KEYS:
                continue
            if k not in b:
                out.append(f"{path}/{k}: saknas i nya datan")
                continue
            walk(a[k], b[k], f"{path}/{k}", out)
        return
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: längd {len(a)} → {len(b)}")
            return
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, f"{path}[{i}]", out)
        return
    if isinstance(a, str) and isinstance(b, str):
        return  # strängar i listor (t.ex. parknamn i issues) jämförs inte
    if a != b:
        out.append(f"{path}: {a!r} → {b!r}")


def main() -> int:
    facit = json.load(open(sys.argv[1], encoding="utf-8"))
    ny = json.load(open(sys.argv[2], encoding="utf-8"))
    out: list[str] = []
    for key in facit:
        if key in TEXT_KEYS:
            continue
        walk(facit[key], ny.get(key), key, out)
    extra = sorted(set(ny) - set(facit))
    print(f"Nya nycklar: {extra}")
    if out:
        print(f"{len(out)} avvikelser:")
        print("\n".join(out[:60]))
        return 1
    print("Talen är oförändrade mot facit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
