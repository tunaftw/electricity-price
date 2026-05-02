"""Datakvalitets-validering för spotpris-CSV:er.

Kör kontroller på nedladdad elprisdata och rapporterar problem. Tanken är att
detta körs efter varje nedladdning (eller ad-hoc) för att fånga upp:

- Luckor i tidsserier (gaps)
- Duplikater (samma timestamp flera gånger)
- Prisextremer (orimligt höga/låga priser)
- Oorsaksliga EXR-värden
- Saknade år

Svåra fel är sällsynta men värda att fånga innan de sprids vidare in i
dashboard/rapporter.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from .config import RAW_DIR, ZONES, EARLIEST_DATE, FIFTEEN_MIN_START


# Thresholds (EUR/kWh — inte MWh!)
PRICE_MIN_EUR_PER_KWH = -0.5   # –500 EUR/MWh
PRICE_MAX_EUR_PER_KWH = 3.0    # 3000 EUR/MWh (extremt dyrt, men möjligt)
EXR_MIN = 5.0
EXR_MAX = 20.0


@dataclass
class QualityIssue:
    """En enskild upptäckt datakvalitets-brist."""
    severity: str           # "error" | "warning" | "info"
    zone: str
    year: int | None
    kind: str               # "gap" | "duplicate" | "extreme_price" | ...
    message: str
    details: dict = field(default_factory=dict)

    def format(self) -> str:
        tag = {"error": "ERR", "warning": "WRN", "info": "INF"}[self.severity]
        yr = f"/{self.year}" if self.year else ""
        base = f"[{tag}] {self.zone}{yr} {self.kind}: {self.message}"
        # Visa gap-detaljer inline (max 5 rader)
        if self.kind == "gap" and self.details.get("gaps"):
            lines = [base]
            for g in self.details["gaps"][:5]:
                lines.append(
                    f"       {g['from']} → {g['to']} ({g['delta_minutes']:+.0f} min)"
                )
            return "\n".join(lines)
        return base


@dataclass
class ZoneQualityReport:
    zone: str
    years_checked: list[int] = field(default_factory=list)
    issues: list[QualityIssue] = field(default_factory=list)
    total_rows: int = 0

    @property
    def n_errors(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def n_warnings(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def ok(self) -> bool:
        return self.n_errors == 0


def _expected_resolution(ts: datetime) -> int:
    """Returnerar förväntad upplösning i minuter (60 eller 15)."""
    return 15 if ts.date() >= FIFTEEN_MIN_START else 60


def _parse_row_timestamps(row: dict) -> tuple[datetime, datetime]:
    """Parse time_start and time_end from a CSV row."""
    ts_start = datetime.fromisoformat(row["time_start"])
    ts_end = datetime.fromisoformat(row["time_end"])
    return ts_start, ts_end


def check_spot_price_file(
    path: Path, zone: str, year: int,
) -> tuple[list[QualityIssue], int]:
    """Check a single spot-price CSV file. Returns (issues, row_count)."""
    issues: list[QualityIssue] = []
    rows = []

    if not path.exists():
        issues.append(QualityIssue(
            severity="error", zone=zone, year=year, kind="missing_file",
            message=f"fil saknas: {path.name}",
        ))
        return issues, 0

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_idx, row in enumerate(reader, 2):  # start at line 2 (after header)
            try:
                ts_start, ts_end = _parse_row_timestamps(row)
                price_eur = float(row["EUR_per_kWh"])
                exr = float(row["EXR"])
                rows.append({
                    "line": row_idx,
                    "ts_start": ts_start,
                    "ts_end": ts_end,
                    "price_eur": price_eur,
                    "exr": exr,
                })
            except (KeyError, ValueError) as e:
                issues.append(QualityIssue(
                    severity="error", zone=zone, year=year, kind="parse_error",
                    message=f"rad {row_idx}: {e}",
                ))

    if not rows:
        return issues, 0

    # Sortera efter timestamp för att hitta gap/duplikat i rätt ordning
    rows.sort(key=lambda r: r["ts_start"])

    # Check 1: duplikater (samma timestamp)
    seen_ts = {}
    for r in rows:
        if r["ts_start"] in seen_ts:
            issues.append(QualityIssue(
                severity="error", zone=zone, year=year, kind="duplicate",
                message=f"duplicerad timestamp {r['ts_start'].isoformat()} "
                        f"(rader {seen_ts[r['ts_start']]} och {r['line']})",
                details={"timestamp": r["ts_start"].isoformat()},
            ))
        else:
            seen_ts[r["ts_start"]] = r["line"]

    # Check 2: gaps. Klassificera DST-artefakter separat från riktiga luckor.
    # DST höst-övergång ger en apparent -60 min "gap" pga CSV-labelling där
    # en rad får ts_end märkt med nästa offset. Vår-övergång ger 0.
    # Riktiga luckor = positiv delta som INTE är exakt 60 min DST-hop.
    real_gaps = []
    dst_artifacts = 0
    for i in range(1, len(rows)):
        prev = rows[i - 1]
        cur = rows[i]
        expected_next = prev["ts_end"]
        if cur["ts_start"] != expected_next:
            gap_delta = (cur["ts_start"] - expected_next).total_seconds() / 60
            # -60 min = DST fall-back labeling quirk
            if gap_delta == -60:
                dst_artifacts += 1
                continue
            # +60 min vid midnatt på en "vanlig" dag är en riktig lucka
            real_gaps.append({
                "from": expected_next.isoformat(),
                "to": cur["ts_start"].isoformat(),
                "delta_minutes": gap_delta,
            })

    if real_gaps:
        total_gap_minutes = sum(g["delta_minutes"] for g in real_gaps)
        severity = "error" if total_gap_minutes > 120 else "warning"
        issues.append(QualityIssue(
            severity=severity, zone=zone, year=year, kind="gap",
            message=f"{len(real_gaps)} riktig(a) lucka/luckor, "
                    f"total {total_gap_minutes:+.0f} min",
            details={"gaps": real_gaps[:10]},
        ))
    if dst_artifacts > 2:
        # Fler än 2 DST-artefakter är ovanligt (max 1 vår + 1 höst per år)
        issues.append(QualityIssue(
            severity="info", zone=zone, year=year, kind="dst_multiple",
            message=f"{dst_artifacts} DST-labeling-artefakter",
        ))

    # Check 3: prisextremer
    for r in rows:
        if not (PRICE_MIN_EUR_PER_KWH <= r["price_eur"] <= PRICE_MAX_EUR_PER_KWH):
            # Konvertera till EUR/MWh för läsbar rapport
            price_mwh = r["price_eur"] * 1000
            issues.append(QualityIssue(
                severity="warning", zone=zone, year=year, kind="extreme_price",
                message=f"{r['ts_start'].date()} {r['ts_start'].time()}: "
                        f"{price_mwh:+.1f} EUR/MWh",
                details={"timestamp": r["ts_start"].isoformat(),
                         "price_eur_mwh": price_mwh},
            ))

    # Check 4: orimlig EXR
    exr_values = [r["exr"] for r in rows]
    bad_exr = [v for v in exr_values if not (EXR_MIN <= v <= EXR_MAX)]
    if bad_exr:
        min_bad = min(bad_exr)
        max_bad = max(bad_exr)
        issues.append(QualityIssue(
            severity="warning", zone=zone, year=year, kind="exr_out_of_range",
            message=f"{len(bad_exr)} EXR-värden utanför [{EXR_MIN}, {EXR_MAX}]: "
                    f"min={min_bad:.2f}, max={max_bad:.2f}",
        ))

    # Check 5: förväntade timezone-offsets (svenska data har +01/+02 pga DST).
    # Flagga bara om det finns offsets UTANFÖR {+01, +02}.
    EXPECTED_OFFSETS_SEC = {3600, 7200}  # +01:00 och +02:00
    bad_offsets = set()
    for r in rows:
        tz = r["ts_start"].tzinfo
        if tz is None:
            bad_offsets.add("none")
            continue
        offset_sec = tz.utcoffset(r["ts_start"]).total_seconds()
        if offset_sec not in EXPECTED_OFFSETS_SEC:
            bad_offsets.add(f"{offset_sec/3600:+.0f}:00")
    if bad_offsets:
        issues.append(QualityIssue(
            severity="warning", zone=zone, year=year, kind="timezone_unexpected",
            message=f"oväntad timezone-offset: {bad_offsets} "
                    f"(förväntat +01:00/+02:00)",
        ))

    return issues, len(rows)


def check_zone(zone: str, raw_dir: Path | None = None) -> ZoneQualityReport:
    """Kör alla kontroller för en zon (alla år)."""
    if raw_dir is None:
        raw_dir = RAW_DIR

    zone_dir = raw_dir / zone
    report = ZoneQualityReport(zone=zone)

    if not zone_dir.exists():
        report.issues.append(QualityIssue(
            severity="error", zone=zone, year=None, kind="missing_directory",
            message=f"zonkatalog saknas: {zone_dir}",
        ))
        return report

    # Identifiera år i katalogen
    year_files = sorted(zone_dir.glob("*.csv"))
    for csv_file in year_files:
        try:
            year = int(csv_file.stem)
        except ValueError:
            continue
        report.years_checked.append(year)
        file_issues, n_rows = check_spot_price_file(csv_file, zone, year)
        report.issues.extend(file_issues)
        report.total_rows += n_rows

    # Check 6: Kontrollera att förväntade år finns (från EARLIEST_DATE till nu)
    current_year = datetime.now().year
    expected_years = list(range(EARLIEST_DATE.year, current_year + 1))
    missing_years = set(expected_years) - set(report.years_checked)
    if missing_years:
        report.issues.append(QualityIssue(
            severity="warning", zone=zone, year=None, kind="missing_year",
            message=f"år saknas: {sorted(missing_years)}",
        ))

    return report


def check_all_spot_prices() -> dict[str, ZoneQualityReport]:
    """Kör kvalitetskontroll på alla zoner."""
    return {zone: check_zone(zone) for zone in ZONES}


def format_report(reports: dict[str, ZoneQualityReport]) -> str:
    """Formatera en läsbar rapport från alla zoner."""
    lines = []
    lines.append("=" * 80)
    lines.append("DATAKVALITETS-RAPPORT: Spotpriser")
    lines.append("=" * 80)

    total_errors = 0
    total_warnings = 0
    total_rows = 0

    for zone in sorted(reports):
        report = reports[zone]
        status = "OK" if report.ok else "FEL"
        lines.append(
            f"\n{zone}: {status} — {len(report.years_checked)} år, "
            f"{report.total_rows:,} rader, "
            f"{report.n_errors} fel, {report.n_warnings} varningar"
        )
        total_errors += report.n_errors
        total_warnings += report.n_warnings
        total_rows += report.total_rows

        if report.issues:
            for issue in report.issues[:20]:  # max 20 per zon i output
                lines.append(f"  {issue.format()}")
            if len(report.issues) > 20:
                lines.append(f"  ... och {len(report.issues) - 20} fler")

    lines.append("\n" + "=" * 80)
    lines.append(
        f"TOTALT: {total_rows:,} rader, "
        f"{total_errors} fel, {total_warnings} varningar"
    )
    lines.append("=" * 80)
    return "\n".join(lines)
