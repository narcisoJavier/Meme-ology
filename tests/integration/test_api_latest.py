"""Integration tests for GET /api/v1/memes/latest endpoint.

Validates:
- HTTP 200 response with normalized JSON payload.
- Pagination parameters: limit, offset, has_more flag, total count.
- Validation bounds: limit > 100, negative offset handling (HTTP 422).
- Source filtering (?source=reddit, ?source=knowyourmeme).
- NSFW filtering default (nsfw=false) vs opt-in (nsfw=true).
- High offset pagination returning empty list gracefully.
- Tier 3 Combinatorial tests (limit x source x nsfw matrix).
"""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.asyncio
class TestApiLatestEndpoint:
    """Integration test suite for /api/v1/memes/latest."""

    async def test_get_latest_default_success(self, async_client: httpx.AsyncClient) -> None:
        """Verify GET /api/v1/memes/latest returns HTTP 200 with valid paginated structure."""
        response = await async_client.get("/api/v1/memes/latest")
        assert response.status_code == 200
        data = response.json()

        assert "items" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) > 0
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

    async def test_get_latest_schema_fields(self, async_client: httpx.AsyncClient) -> None:
        """Verify each meme item in /latest contains required normalized fields."""
        response = await async_client.get("/api/v1/memes/latest?limit=5")
        assert response.status_code == 200
        data = response.json()

        item = data["items"][0]
        assert "id" in item
        assert "title" in item
        assert "media_url" in item or "url" in item
        assert "score" in item
        assert "created_at" in item
        assert "is_nsfw" in item
        assert isinstance(item["score"], int)
        assert isinstance(item["created_at"], (int, float))

    async def test_get_latest_sorted_by_recency(self, async_client: httpx.AsyncClient) -> None:
        """Verify memes in /latest are returned in strictly descending order of created_at."""
        response = await async_client.get("/api/v1/memes/latest?limit=10&nsfw=true")
        assert response.status_code == 200
        items = response.json()["items"]

        for i in range(len(items) - 1):
            assert items[i]["created_at"] >= items[i + 1]["created_at"]

    async def test_get_latest_pagination_limit(self, async_client: httpx.AsyncClient) -> None:
        """Verify limit parameter restricts number of returned items."""
        response = await async_client.get("/api/v1/memes/latest?limit=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 3
        assert data["limit"] == 3

    async def test_get_latest_pagination_offset(self, async_client: httpx.AsyncClient) -> None:
        """Verify offset parameter shifts the returned window without duplicating items."""
        resp1 = await async_client.get("/api/v1/memes/latest?limit=2&offset=0&nsfw=true")
        resp2 = await async_client.get("/api/v1/memes/latest?limit=2&offset=2&nsfw=true")

        assert resp1.status_code == 200
        assert resp2.status_code == 200

        items1 = resp1.json()["items"]
        items2 = resp2.json()["items"]

        assert len(items1) == 2
        assert len(items2) == 2
        ids1 = {m["id"] for m in items1}
        ids2 = {m["id"] for m in items2}
        assert ids1.isdisjoint(ids2)

    async def test_get_latest_source_filter_reddit(self, async_client: httpx.AsyncClient) -> None:
        """Verify filtering by source=reddit returns only Reddit memes."""
        response = await async_client.get("/api/v1/memes/latest?source=reddit&nsfw=true")
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            source_val = item.get("source_platform") or item.get("source")
            assert "reddit" in str(source_val).lower()

    async def test_get_latest_source_filter_knowyourmeme(self, async_client: httpx.AsyncClient) -> None:
        """Verify filtering by source=knowyourmeme returns only KYM memes."""
        response = await async_client.get("/api/v1/memes/latest?source=knowyourmeme&nsfw=true")
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            source_val = item.get("source_platform") or item.get("source")
            assert "knowyourmeme" in str(source_val).lower() or "kym" in str(source_val).lower()

    async def test_get_latest_nsfw_default_safe(self, async_client: httpx.AsyncClient) -> None:
        """Verify default nsfw=false excludes all NSFW items."""
        response = await async_client.get("/api/v1/memes/latest")
        assert response.status_code == 200
        items = response.json()["items"]
        for item in items:
            assert item["is_nsfw"] is False

    async def test_get_latest_nsfw_opt_in(self, async_client: httpx.AsyncClient) -> None:
        """Verify nsfw=true returns NSFW items when available."""
        response = await async_client.get("/api/v1/memes/latest?nsfw=true")
        assert response.status_code == 200
        items = response.json()["items"]
        assert any(item["is_nsfw"] is True for item in items)

    async def test_get_latest_high_offset_empty_list(self, async_client: httpx.AsyncClient) -> None:
        """Verify offset exceeding total items returns HTTP 200 with empty list."""
        response = await async_client.get("/api/v1/memes/latest?offset=99999")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["has_more"] is False

    async def test_get_latest_invalid_limit_validation_error(self, async_client: httpx.AsyncClient) -> None:
        """Verify negative or excessively large limit returns HTTP 422 Unprocessable Entity."""
        res_neg = await async_client.get("/api/v1/memes/latest?limit=-1")
        assert res_neg.status_code == 422

        res_huge = await async_client.get("/api/v1/memes/latest?limit=500")
        assert res_huge.status_code in (422, 400)

    async def test_get_latest_invalid_offset_validation_error(self, async_client: httpx.AsyncClient) -> None:
        """Verify negative offset returns HTTP 422."""
        response = await async_client.get("/api/v1/memes/latest?offset=-5")
        assert response.status_code == 422

    @pytest.mark.parametrize("limit", [1, 5, 20])
    @pytest.mark.parametrize("source", [None, "reddit", "knowyourmeme"])
    @pytest.mark.parametrize("nsfw", [False, True])
    async def test_get_latest_pairwise_combinations(
        self, async_client: httpx.AsyncClient, limit: int, source: str | None, nsfw: bool
    ) -> None:
        """Tier 3: Combinatorial test matrix across limit, source, and nsfw filters."""
        url = f"/api/v1/memes/latest?limit={limit}&nsfw={'true' if nsfw else 'false'}"
        if source:
            url += f"&source={source}"

        response = await async_client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= limit

        for item in data["items"]:
            if not nsfw:
                assert item["is_nsfw"] is False
            if source == "reddit":
                assert "reddit" in str(item.get("source_platform") or item.get("source")).lower()
            elif source == "knowyourmeme":
                assert "knowyourmeme" in str(item.get("source_platform") or item.get("source")).lower() or "kym" in str(item.get("source_platform") or item.get("source")).lower()
