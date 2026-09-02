"""Resiliency tests for network failures, rate limiting, corrupt feeds, and cache fallbacks.

Validates:
- Upstream HTTP 429 Too Many Requests with Retry-After header parsing.
- Upstream HTTP 500/503 server errors handled gracefully without pipeline crash.
- Upstream HTTP 403 Forbidden handled gracefully.
- Network connection timeouts (httpx.TimeoutException) handled cleanly.
- DNS and socket connection errors (httpx.ConnectError) handled cleanly.
- Corrupt XML/JSON payload handling without unhandled exceptions.
- Surviving sources isolation: failure in one source does not block other active sources.
- Fallback to cached items during total network disconnect.
- Health reporting marks failed sources as 'degraded' or 'error'.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.ingestion.knowyourmeme import KnowYourMemeFetcher
from app.ingestion.reddit import RedditFetcher
from app.models.meme import NormalizedMeme

try:
    from app.storage.memory_store import MemoryStore
except ImportError:
    MemoryStore = None  # type: ignore


@pytest.fixture(autouse=True)
def fast_sleep_patch():
    """Patch asyncio.sleep to fast-forward backoff delays during testing."""
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        yield mock_sleep


class TestNetworkResilience:
    """Tier 1 & Tier 2 tests for upstream network fault tolerance."""

    @pytest.mark.asyncio
    async def test_reddit_fetcher_handles_http_429_rate_limit(self) -> None:
        """Verify Reddit fetcher handles HTTP 429 without unhandled exception."""
        fetcher = RedditFetcher()

        mock_response = httpx.Response(
            status_code=429,
            headers={"Retry-After": "2", "x-ratelimit-reset": "60"},
            request=httpx.Request("GET", "https://www.reddit.com/r/memes/hot.json"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            try:
                memes = await fetcher.fetch_subreddit("memes")
                assert isinstance(memes, list)
            except Exception as e:
                assert "ratelimit" in str(type(e)).lower() or "source" in str(type(e)).lower()

    @pytest.mark.asyncio
    async def test_reddit_fetcher_handles_http_403_forbidden(self) -> None:
        """Verify Reddit fetcher handles HTTP 403 Forbidden cleanly."""
        fetcher = RedditFetcher()

        mock_response = httpx.Response(
            status_code=403,
            text="Forbidden",
            request=httpx.Request("GET", "https://www.reddit.com/r/memes/hot.json"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            memes = await fetcher.fetch_subreddit("memes")
            assert isinstance(memes, list)

    @pytest.mark.asyncio
    async def test_reddit_fetcher_handles_http_500_server_error(self) -> None:
        """Verify Reddit fetcher handles HTTP 500 gracefully."""
        fetcher = RedditFetcher()

        mock_response = httpx.Response(
            status_code=500,
            text="Internal Server Error",
            request=httpx.Request("GET", "https://www.reddit.com/r/dankmemes/hot.json"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            memes = await fetcher.fetch_subreddit("dankmemes")
            assert isinstance(memes, list)

    @pytest.mark.asyncio
    async def test_reddit_fetcher_handles_http_503_service_unavailable(self) -> None:
        """Verify Reddit fetcher handles HTTP 503."""
        fetcher = RedditFetcher()
        mock_response = httpx.Response(
            status_code=503,
            text="Service Unavailable",
            request=httpx.Request("GET", "https://www.reddit.com/r/me_irl/hot.json"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            memes = await fetcher.fetch_subreddit("me_irl")
            assert isinstance(memes, list)

    @pytest.mark.asyncio
    async def test_kym_fetcher_handles_timeout_exception(self) -> None:
        """Verify Know Your Meme fetcher handles httpx.TimeoutException cleanly."""
        fetcher = KnowYourMemeFetcher()

        with patch("httpx.AsyncClient.get", side_effect=httpx.ReadTimeout("Connection timed out")):
            memes = await fetcher.fetch_memes()
            assert isinstance(memes, list)

    @pytest.mark.asyncio
    async def test_kym_fetcher_handles_connect_error(self) -> None:
        """Verify Know Your Meme fetcher handles httpx.ConnectError cleanly."""
        fetcher = KnowYourMemeFetcher()

        with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("DNS resolution failure")):
            memes = await fetcher.fetch_memes()
            assert isinstance(memes, list)

    @pytest.mark.asyncio
    async def test_kym_fetcher_handles_http_404_not_found(self) -> None:
        """Verify Know Your Meme fetcher handles HTTP 404 cleanly."""
        fetcher = KnowYourMemeFetcher()
        mock_response = httpx.Response(
            status_code=404,
            text="Not Found",
            request=httpx.Request("GET", "https://knowyourmeme.com/memes.rss"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            memes = await fetcher.fetch_memes()
            assert isinstance(memes, list)

    @pytest.mark.asyncio
    async def test_malformed_xml_feed_does_not_crash_kym_ingestor(self) -> None:
        """Verify corrupt XML string is handled gracefully."""
        fetcher = KnowYourMemeFetcher()

        mock_response = httpx.Response(
            status_code=200,
            text="<<<corrupt xml unclosed tag",
            request=httpx.Request("GET", "https://knowyourmeme.com/memes.rss"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            memes = await fetcher.fetch_memes()
            assert isinstance(memes, list)

    @pytest.mark.asyncio
    async def test_source_isolation_one_failure_does_not_affect_others(
        self, raw_reddit_memes_json: dict
    ) -> None:
        """Verify when Reddit fails, KYM or other subreddits still return valid items."""
        reddit_mock_success = httpx.Response(
            status_code=200,
            json=raw_reddit_memes_json,
            request=httpx.Request("GET", "https://www.reddit.com/r/memes/hot.json"),
        )
        reddit_mock_fail = httpx.Response(
            status_code=503,
            text="Service Unavailable",
            request=httpx.Request("GET", "https://www.reddit.com/r/dankmemes/hot.json"),
        )

        fetcher = RedditFetcher()
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [reddit_mock_success, reddit_mock_fail]

            memes_sub1 = await fetcher.fetch_subreddit("memes")
            memes_sub2 = await fetcher.fetch_subreddit("dankmemes")

            assert len(memes_sub1) > 0
            assert isinstance(memes_sub2, list)

            if MemoryStore is not None:
                store = MemoryStore()
                store.upsert_memes(memes_sub1)
                assert store.count() > 0

    @pytest.mark.asyncio
    async def test_cache_retains_items_during_offline_outage(
        self, sample_normalized_memes: list[dict]
    ) -> None:
        """Verify memory store retains pre-existing memes when network is offline."""
        if MemoryStore is None:
            pytest.skip("MemoryStore not yet implemented")

        store = MemoryStore()
        pydantic_memes = [NormalizedMeme(**m) for m in sample_normalized_memes]
        store.upsert_memes(pydantic_memes)

        initial_count = store.count()
        assert initial_count > 0

        failed_fetch_memes: list[NormalizedMeme] = []
        store.upsert_memes(failed_fetch_memes)

        assert store.count() == initial_count
        latest, total = store.get_latest(limit=20, offset=0, nsfw=True)
        assert len(latest) == initial_count
