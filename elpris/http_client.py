"""Shared HTTP client utilities: rate limiting + retry decorators.

Used across all API clients (api.py, entsoe.py, esett.py, mimer.py, nasdaq.py,
bazefield.py) so retry behavior, backoff, and rate limiting stay consistent.
Before this module each client copy-pasted its own ``_rate_limited`` and
``@retry`` decorators with subtle drift (e.g. nasdaq.py was missing ``min=2``).
"""

from __future__ import annotations

import time
from functools import wraps
from typing import Callable

from tenacity import (
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import REQUEST_DELAY


class NonRetryableAPIError(Exception):
    """Base class for API errors that should fail fast instead of retrying."""


def rate_limited(min_interval: float = REQUEST_DELAY) -> Callable:
    """Decorator: enforce ``min_interval`` seconds between successive calls.

    Each decorated function gets its own per-function rate limiter (closure
    state), so different clients do not contend on the same bucket. Apply this
    *innermost* — i.e. closest to the function — so each retry attempt is
    rate-limited too::

        @with_retry()
        @rate_limited()
        def fetch(...): ...
    """
    def decorator(func):
        last_call = [0.0]

        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_call[0]
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            try:
                return func(*args, **kwargs)
            finally:
                last_call[0] = time.time()

        return wrapper

    return decorator


def with_retry(
    attempts: int = 3,
    min_wait: float = 2,
    max_wait: float = 10,
) -> Callable:
    """Decorator: retry on exception with exponential backoff.

    Standard policy across all clients: 3 attempts, 2-10 s exponential
    backoff. Apply this *outermost* so it wraps any rate limiting::

        @with_retry()
        @rate_limited()
        def fetch(...): ...
    """
    return retry(
        retry=retry_if_not_exception_type(NonRetryableAPIError),
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
    )
