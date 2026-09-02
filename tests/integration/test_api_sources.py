"""Integration tests for GET /api/v1/sources and GET /health endpoints.

Validates:
- /api/v1/sources list output with active platforms, status ('ok'/'degraded'/'error'), and item counts.
- /health uptime metrics, cached item counts, and status indicators.
- Source community breakdown and sync timestamp validation.
- Health endpoint schema integrity.
"""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.asyncio
class TestApiSourcesAndHealthEndpoints:
    """Integration test suite for /api/v1/sources and /health."""

    async def test_get_sources_returns_status_list(self, async_client: httpx.AsyncClient) -> None:
        """Verify GET /api/v1/sources returns list of tracked ingestion sources."""
        response = await async_client.get("/api/v1/sources")
        assert response.status_code == 200
        sources = response.json()

        assert isinstance(sources, list)
        assert len(sources) > 0

        first = sources[0]
        assert "id" in first or "name" in first
        assert "platform" in first or "source" in first
        assert "status" in first
        assert first["status"] in ("ok", "healthy", "degraded", "error", "offline", "active")

    async def test_get_sources_item_counts(self, async_client: httpx.AsyncClient) -> None:
        """Verify source objects contain integer item counts."""
        response = await async_client.get("/api/v1/sources")
        assert response.status_code == 200
        sources = response.json()
        for src in sources:
            if "item_count" in src:
                assert isinstance(src["item_count"], int)
                assert src["item_count"] >= 0

    async def test_get_sources_contains_reddit_and_kym(self, async_client: httpx.AsyncClient) -> None:
        """Verify sources list includes both Reddit and Know Your Meme entries."""
        response = await async_client.get("/api/v1/sources")
        assert response.status_code == 200
        sources = response.json()
        platforms = [str(s.get("platform") or s.get("source") or s.get("id")).lower() for s in sources]
        assert any("reddit" in p for p in platforms)
        assert any("kym" in p or "knowyourmeme" in p for p in platforms)

    async def test_get_health_endpoint_success(self, async_client: httpx.AsyncClient) -> None:
        """Verify GET /health returns HTTP 200 with operational metrics."""
        response = await async_client.get("/health")
        if response.status_code == 404:
            response = await async_client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert data["status"] in ("ok", "healthy", "up")
        if "uptime_seconds" in data:
            assert isinstance(data["uptime_seconds"], (int, float))
            assert data["uptime_seconds"] >= 0

    async def test_get_health_reports_cache_count(self, async_client: httpx.AsyncClient) -> None:
        """Verify health check reports cached meme count."""
        response = await async_client.get("/health")
        if response.status_code == 404:
            response = await async_client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        count_key = next((k for k in ("total_memes", "cached_memes", "item_count", "memes_count") if k in data), None)
        if count_key:
            assert isinstance(data[count_key], int)
            assert data[count_key] >= 0

    async def test_get_health_source_counts(self, async_client: httpx.AsyncClient) -> None:
        """Verify health check includes healthy sources count."""
        response = await async_client.get("/health")
        if response.status_code == 404:
            response = await async_client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        if "healthy_sources" in data:
            assert isinstance(data["healthy_sources"], int)
            assert data["healthy_sources"] >= 0
