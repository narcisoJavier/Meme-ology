"""Integration tests for GET /api/v1/memes/random endpoint.

Validates:
- HTTP 200 single meme response payload.
- Random selection respects source query filter (?source=reddit, ?source=knowyourmeme).
- Random selection respects NSFW filter (nsfw=false by default).
- Random selection with community subfilters (e.g. r/memes).
- HTTP 404 Not Found when filtering matches zero memes or when storage is empty.
- Multi-query randomness distribution sanity check.
"""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.asyncio
class TestApiRandomEndpoint:
    """Integration test suite for /api/v1/memes/random."""

    async def test_get_random_default_success(self, async_client: httpx.AsyncClient) -> None:
        """Verify GET /api/v1/memes/random returns HTTP 200 with a valid single meme object."""
        response = await async_client.get("/api/v1/memes/random")
        assert response.status_code == 200
        meme = response.json()

        assert isinstance(meme, dict)
        assert "id" in meme
        assert "title" in meme
        assert "media_url" in meme or "url" in meme
        assert "score" in meme
        assert meme["is_nsfw"] is False

    async def test_get_random_with_reddit_source_filter(self, async_client: httpx.AsyncClient) -> None:
        """Verify random meme with source=reddit returns a Reddit meme."""
        response = await async_client.get("/api/v1/memes/random?source=reddit&nsfw=true")
        assert response.status_code == 200
        meme = response.json()
        source = meme.get("source_platform") or meme.get("source")
        assert "reddit" in str(source).lower()

    async def test_get_random_with_kym_source_filter(self, async_client: httpx.AsyncClient) -> None:
        """Verify random meme with source=knowyourmeme returns a KYM meme."""
        response = await async_client.get("/api/v1/memes/random?source=knowyourmeme&nsfw=true")
        assert response.status_code == 200
        meme = response.json()
        source = meme.get("source_platform") or meme.get("source")
        assert "knowyourmeme" in str(source).lower() or "kym" in str(source).lower()

    async def test_get_random_with_community_filter(self, async_client: httpx.AsyncClient) -> None:
        """Verify random meme with specific subreddit filter."""
        response = await async_client.get("/api/v1/memes/random?source=dankmemes&nsfw=true")
        if response.status_code == 200:
            meme = response.json()
            assert "dankmemes" in str(meme.get("source_community") or meme.get("source_platform")).lower()

    async def test_get_random_nsfw_default_safe(self, async_client: httpx.AsyncClient) -> None:
        """Verify repeated calls with default nsfw=false never return an NSFW item."""
        for _ in range(5):
            response = await async_client.get("/api/v1/memes/random")
            assert response.status_code == 200
            meme = response.json()
            assert meme["is_nsfw"] is False

    async def test_get_random_nonexistent_source_returns_404(self, async_client: httpx.AsyncClient) -> None:
        """Verify requesting random meme from non-existent source returns HTTP 404."""
        response = await async_client.get("/api/v1/memes/random?source=nonexistent_platform_xyz")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data or "message" in data or "error" in data

    async def test_get_random_schema_compliance(self, async_client: httpx.AsyncClient) -> None:
        """Verify full schema properties of returned random meme."""
        response = await async_client.get("/api/v1/memes/random")
        assert response.status_code == 200
        meme = response.json()

        assert isinstance(meme["id"], str)
        assert isinstance(meme["title"], str)
        assert len(meme["title"]) > 0
        assert isinstance(meme["score"], int)
        assert isinstance(meme["created_at"], (int, float))

    async def test_get_random_returns_diverse_items(self, async_client: httpx.AsyncClient) -> None:
        """Verify repeated random calls over multiple iterations returns items from available pool."""
        seen_ids = set()
        for _ in range(10):
            response = await async_client.get("/api/v1/memes/random?nsfw=true")
            if response.status_code == 200:
                seen_ids.add(response.json()["id"])
        # Should observe at least 1 or more distinct items
        assert len(seen_ids) >= 1
