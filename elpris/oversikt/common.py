"""Gemensamma laddare för Översikt: spotpriser och ENTSO-E-sol per kvart.

Allt tidsindexeras med UTC-epoksekunder (int) — kompakt och snabbt att
slå upp — och bokförs på svensk lokaltid (``local_month``/``local_date``),
eftersom elmarknaden avräknas i CET/CEST.

Priser läses i sin ursprungliga upplösning (timme t.o.m. 2025-09-30,
kvart därefter) och fördelas ut på kvartar. Ett timpris gäller då för
alla fyra kvartarna i timmen — det är samma pris, inte fyra observationer.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..config import RESULTAT_DIR, SWEDEN_TZ, UTC_TZ

SPOT_DIR = RESULTAT_DIR / "marknadsdata" / "spotpriser"
ENTSOE_GEN_DIR = RESULTAT_DIR / "marknadsdata" / "entsoe" / "generation"

QUARTER_S = 900
HOUR_S = 3600

# Zonordning = färgordning i alla diagram (färgen följer zonen, aldrig rangen).
ALL_ZONES = ("SE3", "SE4", "SE1", "SE2", "DK1", "DK2")
MAIN_ZONES = ("SE3", "SE4")


def available_zones() -> List[str]:
    """Zoner som har spotprisfiler, i fast ordning."""
    return [z for z in ALL_ZONES if (SPOT_DIR / z).is_dir() and any((SPOT_DIR / z).glob("*.csv"))]


def _epoch(ts: datetime) -> int:
    return int(ts.timestamp())


def local_dt(epoch: int) -> datetime:
    return datetime.fromtimestamp(epoch, SWEDEN_TZ)


@lru_cache(maxsize=None)
def _month_bounds(year: int, month: int) -> Tuple[int, int]:
    start = datetime(year, month, 1, tzinfo=SWEDEN_TZ)
    nxt = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=SWEDEN_TZ)
    return _epoch(start), _epoch(nxt)


def month_bounds(month_key: str) -> Tuple[int, int]:
    """[start, end) i epoksekunder för en lokal månad 'YYYY-MM'."""
    y, m = month_key.split("-")
    return _month_bounds(int(y), int(m))


def local_month(epoch: int) -> str:
    d = datetime.fromtimestamp(epoch, SWEDEN_TZ)
    return f"{d.year:04d}-{d.month:02d}"


def local_date(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, SWEDEN_TZ).strftime("%Y-%m-%d")


def month_keys(first: str, last: str) -> List[str]:
    y, m = map(int, first.split("-"))
    ly, lm = map(int, last.split("-"))
    out = []
    while (y, m) <= (ly, lm):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


class LocalCalendar:
    """Snabb epok → lokal månad/dag via förberäknade gränser.

    Utanför det förberäknade intervallet räknas dagen fram direkt, så att
    inget år någonsin hamnar i fel hink.
    """

    def __init__(self, first_year: int = 2015, last_year: int = date.today().year + 2):
        self._day_starts: List[int] = []
        self._day_keys: List[str] = []
        d = date(first_year, 1, 1)
        end = date(last_year + 1, 1, 1)
        while d < end:
            self._day_starts.append(_epoch(datetime(d.year, d.month, d.day, tzinfo=SWEDEN_TZ)))
            self._day_keys.append(d.isoformat())
            d += timedelta(days=1)
        self._end = _epoch(datetime(end.year, end.month, end.day, tzinfo=SWEDEN_TZ))

    def day(self, epoch: int) -> str:
        from bisect import bisect_right
        if not self._day_starts[0] <= epoch < self._end:
            return datetime.fromtimestamp(epoch, SWEDEN_TZ).strftime("%Y-%m-%d")
        i = bisect_right(self._day_starts, epoch) - 1
        return self._day_keys[i]

    def month(self, epoch: int) -> str:
        return self.day(epoch)[:7]


CAL = LocalCalendar()


# ---------------------------------------------------------------------------
# Spotpriser
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def load_spot_intervals(zone: str) -> Tuple[Tuple[int, int, float], ...]:
    """Spotpriser i ursprunglig upplösning: (start_epoch, längd_s, EUR/MWh).

    Längden härleds ur nästa intervalls start (max en timme) — filernas
    ``time_end`` är opålitlig kring sommartidsbytet. Dubbletter: sista
    raden vinner.
    """
    zone_dir = SPOT_DIR / zone
    by_start: Dict[int, float] = {}
    for path in sorted(zone_dir.glob("*.csv")):
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                raw = row.get("EUR_per_kWh")
                if raw in (None, ""):
                    continue
                try:
                    price = float(raw) * 1000.0
                except ValueError:
                    continue
                start = _epoch(datetime.fromisoformat(row["time_start"]))
                by_start[start] = price
    starts = sorted(by_start)
    out = []
    for i, s in enumerate(starts):
        if i + 1 < len(starts):
            length = min(starts[i + 1] - s, HOUR_S)
        else:
            length = out[-1][1] if out else HOUR_S
        if length <= 0:
            continue
        out.append((s, length, by_start[s]))
    return tuple(out)


@lru_cache(maxsize=None)
def quarter_prices(zone: str) -> Dict[int, float]:
    """Pris per kvart (EUR/MWh), nyckel = kvartens start i epoksekunder."""
    out: Dict[int, float] = {}
    for start, length, price in load_spot_intervals(zone):
        for k in range(max(1, length // QUARTER_S)):
            out[start + k * QUARTER_S] = price
    return out


def spot_end_epoch(zone: str) -> Optional[int]:
    iv = load_spot_intervals(zone)
    if not iv:
        return None
    s, length, _ = iv[-1]
    return s + length


@lru_cache(maxsize=None)
def hourly_prices(zone: str) -> Dict[int, float]:
    """Pris per timme (EUR/MWh): kvartspriser medelvärdesbildas till timmen.

    Används för batteriindikatorerna så att hela tidsserien har samma
    upplösning före och efter 15-minutersbytet 2025-10-01.
    """
    sums: Dict[int, float] = {}
    counts: Dict[int, int] = {}
    for q, price in quarter_prices(zone).items():
        h = q - (q % HOUR_S)
        sums[h] = sums.get(h, 0.0) + price
        counts[h] = counts.get(h, 0) + 1
    return {h: sums[h] / counts[h] for h in sums if counts[h] == 4}


# ---------------------------------------------------------------------------
# ENTSO-E solproduktion
# ---------------------------------------------------------------------------

# ENTSO-E utelämnar punkter vars värde är samma som föregående (curveType
# A03), och de äldre filerna är hämtade utan att luckorna fylldes. En lucka
# betyder därför oftast "samma värde som innan" — typiskt nattens nolla i
# många timmar. Regel: efter ett lågt värde (natt) fylls luckor upp till ett
# dygn; efter ett högt värde bara några timmar, eftersom solproduktion inte
# står still länge — en längre lucka där är ett avbrott och räknas som saknad.
MAX_FILL_LOW_S = 24 * HOUR_S
MAX_FILL_HIGH_S = 3 * HOUR_S
LOW_SHARE_OF_MAX = 0.05


@lru_cache(maxsize=None)
def solar_quarters(zone: str) -> Dict[int, float]:
    """Faktisk solproduktion i zonen per kvart (MW), från ENTSO-E (B16)."""
    zone_dir = ENTSOE_GEN_DIR / zone
    points: Dict[int, Tuple[float, int]] = {}
    for path in sorted(zone_dir.glob("solar_*.csv")):
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    mw = float(row["generation_mw"])
                    res = int(float(row.get("resolution_minutes") or 60)) * 60
                except (TypeError, ValueError):
                    continue
                start = _epoch(datetime.fromisoformat(row["time_start"].replace("Z", "+00:00")))
                points[start] = (mw, res)
    if not points:
        return {}
    peak = max(mw for mw, _ in points.values()) or 1.0
    out: Dict[int, float] = {}
    starts = sorted(points)
    for i, s in enumerate(starts):
        mw, res = points[s]
        nxt = starts[i + 1] if i + 1 < len(starts) else s + res
        span = nxt - s
        limit = MAX_FILL_LOW_S if mw <= LOW_SHARE_OF_MAX * peak else MAX_FILL_HIGH_S
        if span > limit:
            span = res
        q = s
        while q < s + span:
            out[q] = mw
            q += QUARTER_S
    return out


@lru_cache(maxsize=None)
def park_records(park: str) -> Tuple[dict, ...]:
    """Parkdata (strikt energiregel) — cachad så att varje park läses en gång."""
    from ..operations_dashboard_data import load_park_15min
    return tuple(load_park_15min(park))


def fmt_period_end(epoch: int) -> str:
    """Sista dag med data, t.ex. '21 sep 2026' (epoch = exklusivt slut)."""
    d = datetime.fromtimestamp(epoch - 1, SWEDEN_TZ)
    return f"{d.day} {SV_MONTHS_SHORT[d.month - 1]} {d.year}"


SV_MONTHS = ["januari", "februari", "mars", "april", "maj", "juni", "juli",
             "augusti", "september", "oktober", "november", "december"]
SV_MONTHS_SHORT = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug",
                   "sep", "okt", "nov", "dec"]


def month_label(month_key: str, short: bool = False) -> str:
    y, m = month_key.split("-")
    names = SV_MONTHS_SHORT if short else SV_MONTHS
    return f"{names[int(m) - 1]} {y}"
