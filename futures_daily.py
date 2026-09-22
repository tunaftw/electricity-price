#!/usr/bin/env python3
"""Daily Euronext futures settlement fetch (SYS + EPAD SE1-SE4).

Fetches the dated settlements of every listed quarter/year/month maturity
from Euronext Nord Pool Power Futures and merges them into
Resultat/marknadsdata/nasdaq/futures/*.csv. Rows are keyed on (trading date,
contract), so running twice the same evening changes nothing, and each run
re-reads every session since the newest stored one (at least 10) — missed
days heal themselves on the next run, as long as the contract still trades.

Logs to Resultat/logs/futures_daily_YYYYMMDD.log (Stockholm date).
Exit code 1 on any fetch error, when nothing was fetched, or when the newest
SYS settlement is more than MAX_STALE_WEEKDAYS behind the expected one.

Usage:
    python3 futures_daily.py                  # since newest stored day (daily job)
    python3 futures_daily.py --sessions 30    # wider catch-up window
    python3 futures_daily.py --backfill       # all Euronext history + re-date
                                              # legacy fetch-dated snapshot rows

Scheduled Mon-Fri 19:15 by scripts/se.elpris.futures-daily.plist.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone

from elpris.config import SWEDEN_TZ
from elpris.failure_log import LOG_DIR, log_failure
from elpris.nasdaq import (
    EURONEXT_BACKFILL_SESSIONS,
    EURONEXT_DAILY_SESSIONS,
    backfill_euronext_history,
    settlement_date_for_fetch,
    update_euronext_futures,
)

SYS_FILE = "sys_baseload.csv"
# More than this many weekdays between the newest SYS settlement and the one
# the publication rule expects => the source is stale, fail the run. One or
# two days behind is logged as a warning only (exchange holiday or late
# publication); the next run re-reads the window anyway.
MAX_STALE_WEEKDAYS = 3


def _weekdays_between(older: date, newer: date) -> int:
    """Number of weekdays in (older, newer]."""
    n, d = 0, older
    while d < newer:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--sessions", type=int, default=None,
                        help=f"sessions per maturity (default: since newest stored day, "
                             f"min {EURONEXT_DAILY_SESSIONS}; --backfill {EURONEXT_BACKFILL_SESSIONS})")
    parser.add_argument("--backfill", action="store_true",
                        help="fetch all available history and re-date legacy snapshot rows")
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc)
    local_now = now.astimezone(SWEDEN_TZ)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"futures_daily_{local_now:%Y%m%d}.log"
    log_file = open(log_path, "a", encoding="utf-8")

    def log(msg: str) -> None:
        line = f"{datetime.now(SWEDEN_TZ):%Y-%m-%d %H:%M:%S} {msg}"
        print(line, flush=True)
        log_file.write(line + "\n")
        log_file.flush()

    mode = "backfill" if args.backfill else "daily"
    # Daily mode: None lets update_euronext_futures size the window from the
    # newest stored settlement, so a week-long pause is caught up in one run.
    sessions = args.sessions or (EURONEXT_BACKFILL_SESSIONS if args.backfill else None)
    expected = settlement_date_for_fetch(now)
    log(f"START futures_daily mode={mode} sessions={sessions or 'auto'} "
        f"expected_settlement={expected.isoformat()}")

    try:
        if args.backfill:
            summary, errors = backfill_euronext_history(n_sessions=sessions, log=log)
        else:
            summary, errors = update_euronext_futures(n_sessions=sessions, log=log)
    except Exception as e:  # noqa: BLE001 — any crash is a failed run
        log(f"FAILED: {type(e).__name__}: {e}")
        log_failure("euronext", "futures_daily", local_now.date().isoformat(), str(e))
        log_file.close()
        return 1

    exit_code = 0
    for err in errors:
        log(f"ERROR {err}")
    if errors:
        log_failure("euronext", "futures_daily", local_now.date().isoformat(),
                    f"{len(errors)} fetch error(s): {errors[0]}")
        exit_code = 1

    for filename, info in sorted(summary.items()):
        latest = info.get("latest", "")
        log(f"  {filename}: {info['rows']} rows ({info['new']:+d})"
            + (f", newest session {latest}" if latest else ""))
        for g in info.get("report", []):
            log(f"    re-dated snapshot {g['snapshot_date']} -> {g['trading_date']} "
                f"({g['rows']} rows, {g['compared']} compared"
                f"{', ambiguous' if g['ambiguous'] else ''}"
                f"{', %d dropped' % g['dropped'] if g['dropped'] else ''})")

    if SYS_FILE not in summary:
        log("FAILED: no SYS settlements fetched")
        exit_code = 1
    else:
        from elpris.nasdaq import load_futures_csv
        from elpris.config import NASDAQ_DATA_DIR

        sys_latest = max(r["date"] for r in load_futures_csv(NASDAQ_DATA_DIR / SYS_FILE))
        behind = _weekdays_between(date.fromisoformat(sys_latest), expected)
        if behind > MAX_STALE_WEEKDAYS:
            log(f"FAILED: newest SYS settlement {sys_latest} is {behind} weekdays "
                f"behind expected {expected}")
            exit_code = 1
        elif behind:
            log(f"WARNING: newest SYS settlement {sys_latest}, expected {expected} "
                f"({behind} weekday(s) behind — holiday or not yet published)")
        else:
            log(f"OK newest SYS settlement {sys_latest}")

    log(f"END exit={exit_code}")
    log_file.close()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
