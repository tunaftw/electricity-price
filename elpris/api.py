"""API client for elprisetjustnu.se."""

from datetime import date
from typing import Optional

import requests

from .config import BASE_URL, HTTP_TIMEOUT_QUICK
from .http_client import rate_limited, with_retry


def build_url(zone: str, target_date: date) -> str:
    """Build API URL for given zone and date."""
    return f"{BASE_URL}/{target_date.year}/{target_date.strftime('%m-%d')}_{zone}.json"


@with_retry()
@rate_limited()
def fetch_day_prices(zone: str, target_date: date) -> Optional[list[dict]]:
    """
    Fetch price data for a specific zone and date.

    Returns:
        List of price records or None if not available (404).

    Raises:
        requests.HTTPError: For non-404 HTTP errors.
    """
    url = build_url(zone, target_date)

    response = requests.get(url, timeout=HTTP_TIMEOUT_QUICK)

    if response.status_code == 404:
        return None

    response.raise_for_status()
    return response.json()
