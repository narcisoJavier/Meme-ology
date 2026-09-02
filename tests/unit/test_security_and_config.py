"""Unit tests for security, headers, rate limiting, and configuration."""

import pytest
import time
import asyncio
from app.core.security import (
    USER_AGENTS,
    get_random_user_agent,
    get_request_headers,
    calculate_backoff_delay,
    PoliteRateLimiter,
)
from app.config import Settings


def test_user_agent_pool():
    """Verify user agent pool contains valid browser strings."""
    assert len(USER_AGENTS) >= 5
    ua = get_random_user_agent()
    assert ua in USER_AGENTS
    assert "Mozilla" in ua


def test_get_request_headers():
    """Verify standard headers generation."""
    headers = get_request_headers()
    assert "User-Agent" in headers
    assert "Accept" in headers
    assert "Accept-Language" in headers
    assert "Connection" in headers

    custom_headers = get_request_headers(custom_user_agent="CustomBot/1.0")
    assert custom_headers["User-Agent"] == "CustomBot/1.0"


def test_calculate_backoff_delay():
    """Verify exponential backoff calculation and header support."""
    # Standard backoff without headers
    delay_0 = calculate_backoff_delay(attempt=0)
    assert 1.0 <= delay_0 <= 2.0

    delay_2 = calculate_backoff_delay(attempt=2)
    assert 4.0 <= delay_2 <= 5.0

    # With Retry-After header
    headers = {"Retry-After": "5"}
    retry_delay = calculate_backoff_delay(attempt=0, response_headers=headers)
    assert retry_delay == 5.0

    # With x-ratelimit-reset header
    reddit_headers = {"x-ratelimit-reset": "8.5"}
    reset_delay = calculate_backoff_delay(attempt=0, response_headers=reddit_headers)
    assert reset_delay == 8.5


@pytest.mark.asyncio
async def test_polite_rate_limiter():
    """Verify PoliteRateLimiter enforces minimum delay between calls."""
    limiter = PoliteRateLimiter(min_interval_seconds=0.05)
    t0 = time.monotonic()
    await limiter.throttle("test.domain.com")
    await limiter.throttle("test.domain.com")
    elapsed = time.monotonic() - t0
    assert elapsed >= 0.045


def test_settings_list_parsing():
    """Verify Settings parses list fields from strings and arrays."""
    # Test default
    settings = Settings()
    assert isinstance(settings.REDDIT_SUBREDDITS, list)
    assert "memes" in settings.REDDIT_SUBREDDITS

    # Test JSON string parsing
    settings_json = Settings(REDDIT_SUBREDDITS='["test_sub1", "test_sub2"]')
    assert settings_json.REDDIT_SUBREDDITS == ["test_sub1", "test_sub2"]

    # Test comma-separated string parsing
    settings_csv = Settings(REDDIT_SUBREDDITS="sub_a, sub_b, sub_c")
    assert settings_csv.REDDIT_SUBREDDITS == ["sub_a", "sub_b", "sub_c"]
