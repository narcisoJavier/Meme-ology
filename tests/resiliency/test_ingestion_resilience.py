"""Resiliency and network failure fallback tests for ingestion fetchers."""

import pytest
import httpx
from unittest.mock import AsyncMock, patch
from app.ingestion.bluesky import BlueskyFetcher
from app.ingestion.knowyourmeme import KnowYourMemeFetcher
from app.ingestion.mastodon import MastodonFetcher
from app.ingestion.reddit import RedditMemeFetcher
from app.models.meme import SourcePlatform


@pytest.fixture(autouse=True)
def fast_sleep():
    """Patch asyncio.sleep to fast-forward backoff delays during testing."""
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        yield mock_sleep


@pytest.mark.asyncio
async def test_reddit_fetcher_offline_fallback(monkeypatch):
    """Verify Reddit fetcher gracefully falls back to offline fixtures on network exception."""
    fetcher = RedditMemeFetcher("memes")
    
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.ConnectError("Connection refused")
    fetcher._custom_client = mock_client

    memes = await fetcher.fetch_memes()
    assert len(memes) > 0
    assert all(m.source_platform == SourcePlatform.REDDIT for m in memes)


@pytest.mark.asyncio
async def test_reddit_fetcher_rate_limit_fallback():
    """Verify Reddit fetcher handles HTTP 429 and falls back to fixtures."""
    fetcher = RedditMemeFetcher("dankmemes")

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = httpx.Response(
        status_code=429,
        headers={"Retry-After": "0.01"},
        request=httpx.Request("GET", "https://www.reddit.com/r/dankmemes/hot.json"),
    )
    mock_client.get.return_value = mock_resp
    fetcher._custom_client = mock_client

    memes = await fetcher.fetch_memes()
    assert len(memes) > 0
    assert fetcher.status.status in ("ok", "degraded")


@pytest.mark.asyncio
async def test_kym_fetcher_error_fallback():
    """Verify Know Your Meme fetcher falls back to fixtures on HTTP 500 error."""
    fetcher = KnowYourMemeFetcher()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = httpx.Response(
        status_code=500,
        text="Internal Server Error",
        request=httpx.Request("GET", "https://knowyourmeme.com/memes.rss"),
    )
    mock_client.get.return_value = mock_resp
    fetcher._custom_client = mock_client

    memes = await fetcher.fetch_memes()
    assert len(memes) > 0
    assert all(m.source_platform == SourcePlatform.KNOWYOURMEME for m in memes)


@pytest.mark.asyncio
async def test_bluesky_fetcher_error_fallback():
    """Verify Bluesky fetcher falls back to fixtures on network error."""
    fetcher = BlueskyFetcher()
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.ConnectError("Connection refused")
    fetcher._custom_client = mock_client

    memes = await fetcher.fetch_memes()
    assert len(memes) > 0
    assert all(m.source_platform == SourcePlatform.BLUESKY for m in memes)


@pytest.mark.asyncio
async def test_mastodon_fetcher_error_fallback():
    """Verify Mastodon fetcher falls back to fixtures on HTTP 503 error."""
    fetcher = MastodonFetcher()
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = httpx.Response(
        status_code=503,
        text="Service Unavailable",
        request=httpx.Request("GET", "https://mastodon.social/api/v1/timelines/tag/meme"),
    )
    mock_client.get.return_value = mock_resp
    fetcher._custom_client = mock_client

    memes = await fetcher.fetch_memes()
    assert len(memes) > 0
    assert all(m.source_platform == SourcePlatform.MASTODON for m in memes)
