"""Configuration constants for the electricity price downloader."""

from datetime import date
from pathlib import Path

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
RAW_DIR = DATA_DIR / "raw"
QUARTERLY_DIR = DATA_DIR / "quarterly"

# CSV fieldnames
CSV_FIELDS = ["time_start", "time_end", "SEK_per_kWh", "EUR_per_kWh", "EXR"]
