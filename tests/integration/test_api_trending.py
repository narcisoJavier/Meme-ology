"""Integration tests for GET /api/v1/memes/trending endpoint.

Validates:
- HTTP 200 response with memes sorted by trending score descending.
- Trending score field presence and value assertions.
- Source and NSFW filtering on trending rankings.
- Pagination slicing (limit/offset) on trending rankings.
- Parameter validation error responses (HTTP 422).
- Tier 3 Combinatorial tests (limit x source x nsfw matrix).
"""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.asyncio
class TestApiTrendingEndpoint:
    """Integration test suite for /api/v1/memes/trending."""

    async def test_get_trending_default_success(self, async_client: httpx.AsyncClient) -> None:
        """Verify GET /api/v1/memes/trending returns HTTP 200 with valid paginated trending list."""
        response = await async_client.get("/api/v1/memes/trending")
        assert response.status_code == 200
        data = response.json()

        assert "items" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) > 0
        assert "total" in data

    async def test_get_trending_sorted_by_trending_score(self, async_client: httpx.AsyncClient) -> None:
        """Verify items are strictly sorted in descending order of trending_score."""
        response = await async_client.get("/api/v1/memes/trending?limit=10&nsfw=true")
        assert response.status_code == 200
        items = response.json()["items"]

        for i in range(len(items) - 1):
            curr_score = items[i].get("trending_score", 0.0)
            next_score = items[i + 1].get("trending_score", 0.0)
            assert curr_score >= next_score

    async def test_get_trending_schema_fields(self, async_client: httpx.AsyncClient) -> None:
        """Verify trending items contain title, score, trending_score, and media URL."""
        response = await async_client.get("/api/v1/memes/trending?limit=1")
        assert response.status_code == 200
        item = response.json()["items"][0]

        assert "id" in item
        assert "title" in item
        assert "trending_score" in item
        assert item["trending_score"] >= 0.0
        assert "media_url" in item or "url" in item

    async def test_get_trending_pagination_limit(self, async_client: httpx.AsyncClient) -> None:
        """Verify limit parameter constrains trending results count."""
        response = await async_client.get("/api/v1/memes/trending?limit=4")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 4
        assert data["limit"] == 4

    async def test_get_trending_pagination_offset(self, async_client: httpx.AsyncClient) -> None:
        """Verify offset parameter pagination on trending ranking."""
        resp1 = await async_client.get("/api/v1/memes/trending?limit=2&offset=0&nsfw=true")
        resp2 = await async_client.get("/api/v1/memes/trending?limit=2&offset=2&nsfw=true")

        assert resp1.status_code == 200
        assert resp2.status_code == 200

        items1 = resp1.json()["items"]
        items2 = resp2.json()["items"]

        assert len(items1) == 2
        assert len(items2) == 2
        ids1 = {m["id"] for m in items1}
        ids2 = {m["id"] for m in items2}
        assert ids1.isdisjoint(ids2)

    async def test_get_trending_source_filter_reddit(self, async_client: httpx.AsyncClient) -> None:
        """Verify source=reddit filter on trending memes."""
        response = await async_client.get("/api/v1/memes/trending?source=reddit&nsfw=true")
        assert response.status_code == 200
        items = response.json()["items"]
        for item in items:
            source = item.get("source_platform") or item.get("source")
            assert "reddit" in str(source).lower()

    async def test_get_trending_source_filter_knowyourmeme(self, async_client: httpx.AsyncClient) -> None:
        """Verify source=knowyourmeme filter on trending memes."""
        response = await async_client.get("/api/v1/memes/trending?source=knowyourmeme&nsfw=true")
        assert response.status_code == 200
        items = response.json()["items"]
        for item in items:
            source = item.get("source_platform") or item.get("source")
            assert "knowyourmeme" in str(source).lower() or "kym" in str(source).lower()

    async def test_get_trending_nsfw_filter_default_safe(self, async_client: httpx.AsyncClient) -> None:
        """Verify default trending response excludes NSFW items."""
        response = await async_client.get("/api/v1/memes/trending")
        assert response.status_code == 200
        items = response.json()["items"]
        for item in items:
            assert item["is_nsfw"] is False

    async def test_get_trending_invalid_parameters_return_422(self, async_client: httpx.AsyncClient) -> None:
        """Verify invalid query parameter types/bounds return HTTP 422."""
        res1 = await async_client.get("/api/v1/memes/trending?limit=invalid_int")
        assert res1.status_code == 422

        res2 = await async_client.get("/api/v1/memes/trending?offset=-1")
        assert res2.status_code == 422

    @pytest.mark.parametrize("limit", [2, 5])
    @pytest.mark.parametrize("source", [None, "reddit", "knowyourmeme"])
    @pytest.mark.parametrize("nsfw", [False, True])
    async def test_get_trending_pairwise_combinations(
        self, async_client: httpx.AsyncClient, limit: int, source: str | None, nsfw: bool
    ) -> None:
        """Tier 3: Combinatorial test matrix across limit, source, and nsfw filters for trending."""
        url = f"/api/v1/memes/trending?limit={limit}&nsfw={'true' if nsfw else 'false'}"
        if source:
            url += f"&source={source}"

        response = await async_client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= limit

        items = data["items"]
        for i in range(len(items) - 1):
            assert items[i].get("trending_score", 0.0) >= items[i + 1].get("trending_score", 0.0)
