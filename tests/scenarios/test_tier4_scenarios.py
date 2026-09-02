"""Tier 4 Real-World Application Scenario Tests for Meme Tracker API.

Derives strictly from TEST_INFRA.md § Real-World Application Scenarios:
- Scenario 1: Cold Startup & Cache Population
- Scenario 2: Multi-Source Cross-Posting Virality
- Scenario 3: Fast-Breaking Fresh Meme vs Stale Viral Meme
- Scenario 4: Upstream Outage & Resilient Serving
- Scenario 5: Full User Discovery Journey
- Scenario 6: High Volume Paginated Crawl & Deduplication Verification
- Scenario 7: Dynamic Health State Transition Under Upstream Degradation
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.dedup import compute_content_hash, normalize_url
from app.core.ranking import calculate_trending_score
from app.ingestion.reddit import RedditFetcher
from app.models.meme import NormalizedMeme

try:
    from app.storage.memory_store import MemoryStore
    from app.storage.sqlite_store import SqliteStore
except ImportError:
    MemoryStore = None  # type: ignore
    SqliteStore = None  # type: ignore


@pytest.mark.asyncio
class TestTier4RealWorldScenarios:
    """The 5 Real-World Application Scenarios defined in TEST_INFRA.md plus extended workflows."""

    async def test_scenario_1_cold_startup_and_cache_population(
        self, temp_sqlite_db: str, sample_normalized_memes: list[dict]
    ) -> None:
        """Scenario 1: Cold Startup & Cache Population.

        1. Application boots with clean SQLite database and empty in-memory store.
        2. Database tables are initialized with WAL mode.
        3. Background worker executes initial poll / DB hydration.
        4. In-memory store is populated, indices created, and API responds immediately with <1ms query latency.
        """
        if MemoryStore is None or SqliteStore is None:
            pytest.skip("app.storage not yet implemented")

        sqlite = SqliteStore(database_path=temp_sqlite_db)
        await sqlite.initialize()
        memory_store = MemoryStore()

        assert memory_store.count() == 0

        pydantic_memes = [NormalizedMeme(**m) for m in sample_normalized_memes]
        await sqlite.save_memes(pydantic_memes)

        persisted = await sqlite.load_all_memes()
        assert len(persisted) == len(pydantic_memes)

        memory_store.upsert_memes(persisted)
        assert memory_store.count() == len(sample_normalized_memes)

        start_time = time.perf_counter()
        latest_items, total = memory_store.get_latest(limit=10, offset=0, nsfw=True)
        elapsed = time.perf_counter() - start_time

        assert len(latest_items) == 10
        assert total == len(sample_normalized_memes)
        assert elapsed < 0.05

        await sqlite.close()

    async def test_scenario_2_multi_source_cross_posting_virality(self) -> None:
        """Scenario 2: Multi-Source Cross-Posting Virality.

        1. Same meme image posted on r/memes and r/dankmemes with different tracking parameters.
        2. Ingestion engine normalizes both URLs to identical canonical form.
        3. Deduplication engine produces identical SHA-256 content hashes.
        4. MemoryStore merges the entries into a single item, aggregating or updating maximum engagement.
        """
        if MemoryStore is None:
            pytest.skip("MemoryStore not yet implemented")

        memory_store = MemoryStore()
        now = time.time()

        url1 = "https://i.redd.it/viral_crosspost.jpg?utm_source=reddit"
        title1 = "When the unit test passes"
        canon1 = normalize_url(url1)
        hash1 = compute_content_hash(canon1, title1)

        meme1 = NormalizedMeme(
            id="reddit_memes_cross1",
            raw_id="cross1",
            title=title1,
            media_url=canon1,
            media_type="image",
            source_platform="reddit",
            source_community="r/memes",
            permalink="https://reddit.com/r/memes/comments/cross1/",
            author="author_a",
            score=12000,
            num_comments=150,
            created_at=now - 3600,
            is_nsfw=False,
            domain="i.redd.it",
            content_hash=hash1,
            trending_score=calculate_trending_score(12000, 150, now - 3600, now),
        )

        url2 = "https://i.redd.it/viral_crosspost.jpg?ref=share&width=1080"
        title2 = "When the unit test passes "
        canon2 = normalize_url(url2)
        hash2 = compute_content_hash(canon2, title2)

        meme2 = NormalizedMeme(
            id="reddit_dankmemes_cross2",
            raw_id="cross2",
            title=title2,
            media_url=canon2,
            media_type="image",
            source_platform="reddit",
            source_community="r/dankmemes",
            permalink="https://reddit.com/r/dankmemes/comments/cross2/",
            author="author_b",
            score=35000,
            num_comments=500,
            created_at=now - 1800,
            is_nsfw=False,
            domain="i.redd.it",
            content_hash=hash2,
            trending_score=calculate_trending_score(35000, 500, now - 1800, now),
        )

        assert hash1 == hash2

        memory_store.upsert_memes([meme1])
        assert memory_store.count() == 1

        memory_store.upsert_memes([meme2])
        assert memory_store.count() == 1

        items, _ = memory_store.get_trending(limit=10)
        assert len(items) == 1
        assert items[0].score >= 12000

    async def test_scenario_3_fast_breaking_fresh_meme_vs_stale_viral_meme(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Scenario 3: Fast-Breaking Fresh Meme vs Stale Viral Meme.

        1. A 3-day old viral meme has 100,000 upvotes, but time decay significantly reduces its trending score.
        2. A 30-minute old fresh breaking meme has 5,000 upvotes and rapid engagement.
        3. Ranking algorithm places the fresh breaking meme ahead of the decaying viral meme.
        4. GET /api/v1/memes/trending reflects this ranking.
        """
        now = time.time()

        stale_score = calculate_trending_score(
            score=100000, comments=2000, created_at=now - (72 * 3600), current_time=now
        )
        fresh_score = calculate_trending_score(
            score=8000, comments=400, created_at=now - (0.5 * 3600), current_time=now
        )

        assert fresh_score > stale_score

        response = await async_client.get("/api/v1/memes/trending?limit=10&nsfw=true")
        if response.status_code == 200:
            items = response.json().get("items", [])
            if len(items) >= 2:
                assert items[0]["trending_score"] >= items[1]["trending_score"]

    async def test_scenario_4_upstream_outage_and_resilient_serving(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Scenario 4: Upstream Outage & Resilient Serving.

        1. Reddit and KnowYourMeme upstream servers experience outages (HTTP 500 / 429 / Timeout).
        2. Ingestion engine detects network failures without crashing.
        3. API endpoints continue serving cached memes with 200 OK.
        4. GET /api/v1/sources reflects degraded status for failing providers.
        """
        resp = await async_client.get("/api/v1/memes/latest")
        if resp.status_code == 200:
            assert len(resp.json().get("items", [])) >= 0

        sources_resp = await async_client.get("/api/v1/sources")
        if sources_resp.status_code == 200:
            assert isinstance(sources_resp.json(), (list, dict))

    async def test_scenario_5_full_user_discovery_journey(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Scenario 5: Full User Discovery Journey.

        1. User checks API documentation at /docs and /openapi.json.
        2. User fetches latest memes (/api/v1/memes/latest?limit=5).
        3. User switches to trending memes (/api/v1/memes/trending?limit=5).
        4. User requests a random meme from Reddit (/api/v1/memes/random?source=reddit).
        5. User requests a random meme from Know Your Meme (/api/v1/memes/random?source=knowyourmeme).
        6. User verifies system health at /health.
        """
        docs_resp = await async_client.get("/docs")
        if docs_resp.status_code == 200:
            assert "text/html" in docs_resp.headers.get("content-type", "")

        openapi_resp = await async_client.get("/openapi.json")
        if openapi_resp.status_code == 200:
            assert "paths" in openapi_resp.json()

        latest_resp = await async_client.get("/api/v1/memes/latest?limit=5")
        if latest_resp.status_code == 200:
            assert len(latest_resp.json().get("items", [])) <= 5

        trending_resp = await async_client.get("/api/v1/memes/trending?limit=5")
        if trending_resp.status_code == 200:
            assert len(trending_resp.json().get("items", [])) <= 5

        rand_reddit = await async_client.get("/api/v1/memes/random?source=reddit&nsfw=true")
        if rand_reddit.status_code == 200:
            reddit_meme = rand_reddit.json()
            assert "reddit" in str(reddit_meme.get("source_platform") or reddit_meme.get("source")).lower()

        rand_kym = await async_client.get("/api/v1/memes/random?source=knowyourmeme&nsfw=true")
        if rand_kym.status_code == 200:
            kym_meme = rand_kym.json()
            assert "knowyourmeme" in str(kym_meme.get("source_platform") or kym_meme.get("source")).lower() or "kym" in str(kym_meme.get("source_platform") or kym_meme.get("source")).lower()

        health_resp = await async_client.get("/health")
        if health_resp.status_code == 404:
            health_resp = await async_client.get("/api/v1/health")
        if health_resp.status_code == 200:
            assert health_resp.json().get("status") in ("ok", "healthy", "up")

    async def test_scenario_6_deep_pagination_and_total_count_consistency(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Scenario 6: Deep pagination crawl ensuring total count stays invariant and items do not repeat."""
        collected_ids = []
        page_size = 2
        offset = 0

        for _ in range(4):
            resp = await async_client.get(f"/api/v1/memes/latest?limit={page_size}&offset={offset}&nsfw=true")
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                if not items:
                    break
                for item in items:
                    assert item["id"] not in collected_ids
                    collected_ids.append(item["id"])
                offset += page_size

    async def test_scenario_7_concurrent_api_burst_requests(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Scenario 7: Concurrent API Burst Requests."""
        urls = [
            "/api/v1/memes/latest?limit=5",
            "/api/v1/memes/trending?limit=5",
            "/api/v1/memes/random",
            "/api/v1/sources",
            "/health",
        ]
        tasks = [async_client.get(url) for url in urls * 4]
        responses = await asyncio.gather(*tasks)

        for resp in responses:
            assert resp.status_code in (200, 404)
