"""API client for elprisetjustnu.se."""

import time
from datetime import date
from functools import wraps
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import BASE_URL, REQUEST_DELAY


def rate_limited(min_interval: float = REQUEST_DELAY):
    """Decorator to ensure minimum time between API calls."""
    last_call = [0.0]

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_call[0]
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            result = func(*args, **kwargs)
            last_call[0] = time.time()
            return result

        return wrapper

    return decorator


def build_url(zone: str, target_date: date) -> str:
    """Build API URL for given zone and date."""
    return f"{BASE_URL}/{target_date.year}/{target_date.strftime('%m-%d')}_{zone}.json"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
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

    response = requests.get(url, timeout=30)

    if response.status_code == 404:
        return None

    response.raise_for_status()
    return response.json()
