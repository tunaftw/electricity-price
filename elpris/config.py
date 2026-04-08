"""Configuration constants for the electricity price downloader."""

from datetime import date
from pathlib import Path
from typing import Optional

# API configuration
BASE_URL = "https://www.elprisetjustnu.se/api/v1/prices"

# Swedish electricity zones
ZONES = ["SE1", "SE2", "SE3", "SE4"]

# Data availability
EARLIEST_DATE = date(2021, 11, 1)  # First available data
FIFTEEN_MIN_START = date(2025, 10, 1)  # When 15-minute data starts

# Rate limiting
REQUEST_DELAY = 0.5  # Seconds between API calls

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RESULTAT_DIR = PROJECT_ROOT / "Resultat"
QUARTERLY_DIR = DATA_DIR / "quarterly"


def _resolve_data_path(symlink_path: Path, resultat_path: Path,
                       test_child: Optional[str] = None) -> Path:
    """Resolve a data path, handling broken symlinks on Windows.

    On Mac/Linux, Git symlinks in data/ work natively as directories.
    On Windows, they're stored as text files — fall back to Resultat/.

    Args:
        symlink_path: The symlink-based path (data/raw/...)
        resultat_path: The direct path (Resultat/marknadsdata/...)
        test_child: Optional child to test (e.g. "SE3") to verify
                    the symlink actually works as a real directory.
    """
    if symlink_path.is_dir():
        if test_child:
            child = symlink_path / test_child
            if not child.is_dir():
                if resultat_path.is_dir():
                    return resultat_path
        else:
            return symlink_path
    if resultat_path.is_dir():
        return resultat_path
    return symlink_path


# Raw spot price data
RAW_DIR = _resolve_data_path(
    DATA_DIR / "raw",
    RESULTAT_DIR / "marknadsdata" / "spotpriser",
    test_child="SE3",
)

# ENTSO-E generation data
ENTSOE_DATA_DIR = _resolve_data_path(
    DATA_DIR / "raw" / "entsoe",
    RESULTAT_DIR / "marknadsdata" / "entsoe",
    test_child="generation",
)

# Mimer regulation prices
MIMER_DATA_DIR = _resolve_data_path(
    DATA_DIR / "raw" / "mimer",
    RESULTAT_DIR / "marknadsdata" / "mimer",
    test_child="fcr",
)

# eSett imbalance prices
ESETT_DATA_DIR = _resolve_data_path(
    DATA_DIR / "raw" / "esett",
    RESULTAT_DIR / "marknadsdata" / "esett",
    test_child="imbalance",
)

# Installed capacity
INSTALLED_DATA_DIR = _resolve_data_path(
    DATA_DIR / "raw" / "installed",
    RESULTAT_DIR / "marknadsdata" / "installerad",
)

# Nasdaq futures
NASDAQ_DATA_DIR = RESULTAT_DIR / "marknadsdata" / "nasdaq" / "futures"

# Park production profiles (Bazefield actual data)
PARKS_PROFILE_DIR = RESULTAT_DIR / "profiler" / "parker"

# CSV fieldnames
CSV_FIELDS = ["time_start", "time_end", "SEK_per_kWh", "EUR_per_kWh", "EXR"]
