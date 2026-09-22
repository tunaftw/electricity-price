"""Zonal forward history: SYS + EPAD per zone and contract, per trading date.

Small, dependency-free loader for dashboards. Reads the futures CSVs in
``Resultat/marknadsdata/nasdaq/futures/`` (Nasdaq history + Euronext
settlements, see :mod:`elpris.nasdaq`) and pairs the SYS leg with the zone's
EPAD leg **on the same trading date**. A date where either leg is missing
yields no zonal observation — the system price is never passed off as a zone
price.

Example::

    >>> from elpris.futures_zonal import load_zonal_forward_history
    >>> fwd = load_zonal_forward_history(zones=("SE3",))
    >>> fwd["contracts"]["YR-27"]
    {'kind': 'YR', 'delivery_start': '2027-01-01', 'delivery_end': '2027-12-31'}
    >>> fwd["zones"]["SE3"]["YR-27"][-1]
    ('2026-09-22', 59.95, 64.65, -4.7)
"""

from __future__ import annotations

import calendar
import csv
import re
from pathlib import Path

from .config import NASDAQ_DATA_DIR

SYS_FILE = "sys_baseload.csv"
EPAD_FILES = {
    "SE1": "epad_se1_lul.csv",
    "SE2": "epad_se2_sun.csv",
    "SE3": "epad_se3_sto.csv",
    "SE4": "epad_se4_mal.csv",
}

_MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN",
           "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
_LABEL_RE = re.compile(r"(YR|Q[1-4]|M(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC))-(\d{2})$")


def parse_contract_label(symbol: str) -> dict | None:
    """Contract metadata from a symbol or label.

    ``"ENOFUTBLYR-27"`` / ``"YR-27"`` -> ``{"label": "YR-27", "kind": "YR",
    "delivery_start": "2027-01-01", "delivery_end": "2027-12-31"}``.
    Quarters (``Q4-26``) and months (``MOCT-26``, Euronext-era symbols) are
    supported; anything else returns None. The label is the same for the SYS
    symbol and every EPAD symbol of the same delivery period.
    """
    match = _LABEL_RE.search(symbol or "")
    if not match:
        return None
    period, yy = match.groups()
    year = 2000 + int(yy)
    if period == "YR":
        kind, first, last = "YR", 1, 12
    elif period.startswith("Q"):
        kind = "Q"
        first = (int(period[1]) - 1) * 3 + 1
        last = first + 2
    else:
        kind = "M"
        first = last = _MONTHS.index(period[1:]) + 1
    end_day = calendar.monthrange(year, last)[1]
    return {
        "label": f"{period}-{yy}",
        "kind": kind,
        "delivery_start": f"{year}-{first:02d}-01",
        "delivery_end": f"{year}-{last:02d}-{end_day:02d}",
    }


def _read_settlements(path: Path) -> dict[str, dict[str, float]]:
    """{label: {date: settlement}} from one futures CSV (unparseable rows skipped)."""
    out: dict[str, dict[str, float]] = {}
    if not path.exists():
        return out
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            meta = parse_contract_label(row.get("contract", ""))
            fix = (row.get("daily_fix_eur") or "").strip()
            day = (row.get("date") or "").strip()
            if not meta or not fix or not day:
                continue
            try:
                out.setdefault(meta["label"], {})[day] = float(fix)
            except ValueError:
                continue
    return out


def load_zonal_forward_history(
    zones: tuple[str, ...] | list[str] = ("SE3", "SE4"),
    data_dir: Path | None = None,
) -> dict:
    """Per zone and contract: the zonal forward (SYS + EPAD) per trading date.

    Args:
        zones: bidding zones to build (keys of :data:`EPAD_FILES`).
        data_dir: futures CSV directory (default ``NASDAQ_DATA_DIR``).

    Returns::

        {
          "zones": {
            "SE3": {"YR-27": [(date, zonal_eur_mwh, sys_eur_mwh, epad_eur_mwh), ...],
                    ...},
            ...
          },
          "contracts": {"YR-27": {"kind": "YR", "delivery_start": "2027-01-01",
                                  "delivery_end": "2027-12-31"}, ...},
        }

    Observation lists are sorted by date (ISO strings) and only contain dates
    where BOTH legs settled; ``zonal`` is rounded to 2 decimals. ``contracts``
    covers every label that has at least one zonal observation in any zone.
    Contracts or zones without overlap are simply absent.
    """
    data_dir = Path(data_dir) if data_dir is not None else NASDAQ_DATA_DIR
    sys_by_label = _read_settlements(data_dir / SYS_FILE)

    result_zones: dict[str, dict[str, list[tuple[str, float, float, float]]]] = {}
    used_labels: set[str] = set()
    for zone in zones:
        if zone not in EPAD_FILES:
            raise ValueError(f"Unknown zone {zone!r} (expected one of {sorted(EPAD_FILES)})")
        epad_by_label = _read_settlements(data_dir / EPAD_FILES[zone])
        per_label: dict[str, list[tuple[str, float, float, float]]] = {}
        for label, epad_series in epad_by_label.items():
            sys_series = sys_by_label.get(label)
            if not sys_series:
                continue
            common = sorted(set(sys_series) & set(epad_series))
            if not common:
                continue
            per_label[label] = [
                (d, round(sys_series[d] + epad_series[d], 2), sys_series[d], epad_series[d])
                for d in common
            ]
            used_labels.add(label)
        result_zones[zone] = dict(sorted(
            per_label.items(),
            key=lambda kv: (parse_contract_label(kv[0])["delivery_start"], kv[0]),
        ))

    contracts = {}
    for label in sorted(used_labels, key=lambda l: (parse_contract_label(l)["delivery_start"], l)):
        meta = parse_contract_label(label)
        contracts[label] = {
            "kind": meta["kind"],
            "delivery_start": meta["delivery_start"],
            "delivery_end": meta["delivery_end"],
        }
    return {"zones": result_zones, "contracts": contracts}
