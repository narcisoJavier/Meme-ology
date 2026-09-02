"""User-Agent rotation pool, polite request headers, and backoff utility."""

import asyncio
import random
import time
from typing import Dict, Optional, Mapping

# Realistic Desktop and Mobile User-Agent Pool
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1",
]


def get_random_user_agent() -> str:
    """Return a randomly chosen User-Agent string from the pool."""
    return random.choice(USER_AGENTS)


def get_request_headers(
    user_agent: Optional[str] = None,
    custom_user_agent: Optional[str] = None,
    accept: str = "application/json, application/rss+xml, text/xml, text/html, */*;q=0.9",
) -> Dict[str, str]:
    """Generate standard, polite HTTP request headers with rotating User-Agent."""
    selected_ua = user_agent or custom_user_agent or get_random_user_agent()
    return {
        "User-Agent": selected_ua,
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }


def calculate_backoff_delay(
    attempt: int,
    response_headers: Optional[Mapping[str, str]] = None,
    base: float = 1.0,
    max_backoff: float = 16.0,
) -> float:
    """Calculate exponential backoff delay with jitter and Retry-After support.

    Delay formula: min(max_backoff, base * 2^attempt + jitter)
    """
    if response_headers:
        # Check standard Retry-After header
        retry_after = response_headers.get("Retry-After") or response_headers.get("retry-after")
        if retry_after:
            try:
                delay = float(retry_after)
                if delay > 0:
                    return min(delay, max_backoff)
            except (ValueError, TypeError):
                pass

        # Check Reddit specific rate limit headers
        ratelimit_reset = response_headers.get("x-ratelimit-reset")
        if ratelimit_reset:
            try:
                delay = float(ratelimit_reset)
                if delay > 0:
                    return min(delay, max_backoff)
            except (ValueError, TypeError):
                pass

    jitter = random.uniform(0.1, 0.5)
    delay = base * (2 ** max(0, attempt)) + jitter
    return min(delay, max_backoff)


class PoliteRateLimiter:
    """Per-domain rate limiter to enforce polite crawling intervals."""

    def __init__(self, min_interval_seconds: float = 1.0) -> None:
        self.min_interval_seconds = min_interval_seconds
        self._last_request_time: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def throttle(self, domain: str) -> None:
        """Wait if necessary to ensure minimum interval between requests to domain."""
        async with self._lock:
            now = time.monotonic()
            last = self._last_request_time.get(domain, 0.0)
            elapsed = now - last
            if elapsed < self.min_interval_seconds:
                wait_time = self.min_interval_seconds - elapsed
                await asyncio.sleep(wait_time)
            self._last_request_time[domain] = time.monotonic()
