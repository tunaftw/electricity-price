"""Structured failure logging for download scripts.

Writes failed download chunks to ``Resultat/logs/failed_chunks.csv`` so
operators can audit data gaps after running ``update_all.py`` from cron.

Before this module the only record of a failed API chunk was a one-line
print to stdout (which cron may or may not capture). After a failure the
data simply had a hole that nobody noticed until manual inspection via
``status.py``. With ``log_failure`` each gap leaves a paper trail that
can be tailed, grepped, or re-tried.

Schema (CSV columns):

* ``recorded_at`` — UTC ISO-8601 timestamp when the failure was logged
* ``source`` — which downloader (``spotpriser``, ``entsoe``, ``esett``,
  ``mimer``, ``nasdaq``, ``installed``, ``bazefield``)
* ``scope`` — zone or product (``SE3``, ``fcr``, ``epad_se``, ``solar``)
* ``chunk`` — human-readable chunk identifier (``2024-01-01..2024-12-31``,
  ``2026-04-15``, ``backfill``)
* ``error`` — short error message, truncated to 500 chars
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import RESULTAT_DIR

LOG_DIR = RESULTAT_DIR / "logs"
FAILURE_LOG = LOG_DIR / "failed_chunks.csv"

_FIELDS = ["recorded_at", "source", "scope", "chunk", "error"]
_MAX_ERROR_LEN = 500

# Process-lokal räknare över antal loggade fel. Låter download-scripts avgöra
# exit-kod även när felen loggas djupt inne i en klient (t.ex. nasdaq
# get_price_history) istället för att bubbla upp till main().
_failure_count = 0


def failure_count() -> int:
    """Antal fel som loggats via log_failure/log_chunk_failures denna process.

    Ta en snapshot före ett download-block och jämför efteråt för att avgöra
    om något chunk misslyckades (delta > 0 → exit 1).
    """
    return _failure_count


def log_failure(source: str, scope: str, chunk: str, error: str) -> None:
    """Append one failure record to the CSV log.

    Args:
        source: Download family (``'spotpriser'``, ``'entsoe'``, ``'esett'``,
            ``'mimer'``, ``'nasdaq'``, ``'installed'``, ``'bazefield'``).
        scope: Zone or product (``'SE3'``, ``'fcr'``, ``'epad_se3'``).
        chunk: Date range or identifier of the failed chunk.
        error: Error message; truncated to 500 chars.
    """
    global _failure_count
    _failure_count += 1
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    is_new = not FAILURE_LOG.exists()
    with open(FAILURE_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow({
            "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": source,
            "scope": scope,
            "chunk": chunk,
            "error": (error or "")[:_MAX_ERROR_LEN],
        })


def log_chunk_failures(source: str, scope: str, chunks: list[str]) -> int:
    """Bulk-log failures from a downloader's ``failed_chunks`` list.

    The downloaders in ``elpris.{esett,entsoe,mimer}`` return strings like
    ``"2024-01-01..2024-03-31: HTTPError 503"`` in their ``failed_chunks``
    list. This helper splits each on the first ``": "`` to separate the
    chunk identifier from the error message before logging.

    Args:
        source: Download family.
        scope: Zone or product.
        chunks: List of formatted ``"<chunk>: <error>"`` strings.

    Returns:
        Number of records written.
    """
    for entry in chunks:
        chunk, _, err = entry.partition(": ")
        log_failure(source, scope, chunk, err)
    return len(chunks)


def recent_failures(hours: int = 24) -> list[dict[str, Any]]:
    """Return failures recorded within the last ``hours`` hours.

    Convenient for ``update_all.py`` end-of-run summaries. Returns an
    empty list if the log does not yet exist.
    """
    if not FAILURE_LOG.exists():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    out: list[dict[str, Any]] = []
    with open(FAILURE_LOG, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                ts = datetime.fromisoformat(row["recorded_at"])
            except (KeyError, ValueError):
                continue
            if ts >= cutoff:
                out.append(row)
    return out
