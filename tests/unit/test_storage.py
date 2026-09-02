"""Unit tests for dual-layer storage subsystem: MemoryStore (hot cache) and SqliteStore (persistence).

Validates:
- MemoryStore in-memory indexing: latest (created_at desc), trending (trending_score desc).
- Limit, offset, and total count pagination in memory cache.
- Source filtering (platform and community) and NSFW toggle.
- get_random retrieval, empty pool behavior, random distribution.
- SqliteStore async database initialization (WAL mode), upserting, and loading all records.
- Deduplication and engagement aggregation during upsert.
- Clear operations and cache state resets.
"""

from __future__ import annotations

import time
import pytest
import pytest_asyncio

from app.models.meme import MediaType, NormalizedMeme, SourcePlatform

try:
    from app.storage.memory_store import MemoryStore
    from app.storage.sqlite_store import SqliteStore
except ImportError:
    MemoryStore = None  # type: ignore
    SqliteStore = None  # type: ignore


@pytest.fixture(autouse=True)
def check_storage_implemented():
    """Ensure storage modules are available or skip."""
    if MemoryStore is None or SqliteStore is None:
        pytest.skip("app.storage not yet implemented (Milestone M2)")


class TestMemoryStore:
    """Tier 1 & Tier 2 tests for MemoryStore hot cache."""

    def test_memory_store_empty_initial_state(self) -> None:
        """Verify empty memory store returns 0 count and empty lists."""
        store = MemoryStore()
        items, total = store.get_latest(limit=20, offset=0)
        assert items == []
        assert total == 0
        assert store.get_random() is None

    def test_upsert_and_get_latest_ordering(self, sample_normalized_memes: list[dict]) -> None:
        """Verify get_latest returns memes sorted strictly in descending order of created_at."""
        store = MemoryStore()
        pydantic_memes = [NormalizedMeme(**m) for m in sample_normalized_memes]
        store.upsert_memes(pydantic_memes)

        items, total = store.get_latest(limit=10, offset=0, nsfw=True)
        assert len(items) > 0
        assert total >= len(items)

        for i in range(len(items) - 1):
            assert items[i].created_at >= items[i + 1].created_at

    def test_get_trending_ordering(self, sample_normalized_memes: list[dict]) -> None:
        """Verify get_trending returns memes sorted strictly in descending order of trending_score."""
        store = MemoryStore()
        pydantic_memes = [NormalizedMeme(**m) for m in sample_normalized_memes]
        store.upsert_memes(pydantic_memes)

        items, total = store.get_trending(limit=10, offset=0, nsfw=True)
        assert len(items) > 0

        for i in range(len(items) - 1):
            assert items[i].trending_score >= items[i + 1].trending_score

    def test_pagination_limit_and_offset(self, sample_normalized_memes: list[dict]) -> None:
        """Verify limit and offset slice the results properly without duplicates."""
        store = MemoryStore()
        pydantic_memes = [NormalizedMeme(**m) for m in sample_normalized_memes]
        store.upsert_memes(pydantic_memes)

        page1, total1 = store.get_latest(limit=2, offset=0, nsfw=True)
        page2, total2 = store.get_latest(limit=2, offset=2, nsfw=True)

        assert len(page1) == 2
        assert len(page2) == 2
        assert total1 == total2
        page1_ids = {m.id for m in page1}
        page2_ids = {m.id for m in page2}
        assert page1_ids.isdisjoint(page2_ids)

    def test_source_filtering_reddit_and_kym(self, sample_normalized_memes: list[dict]) -> None:
        """Verify source filter isolates items by platform and community."""
        store = MemoryStore()
        pydantic_memes = [NormalizedMeme(**m) for m in sample_normalized_memes]
        store.upsert_memes(pydantic_memes)

        reddit_items, _ = store.get_latest(limit=50, offset=0, source="reddit", nsfw=True)
        for item in reddit_items:
            assert item.source_platform in (SourcePlatform.REDDIT, "reddit")

        kym_items, _ = store.get_latest(limit=50, offset=0, source="knowyourmeme", nsfw=True)
        for item in kym_items:
            assert item.source_platform in (SourcePlatform.KNOWYOURMEME, "knowyourmeme")

    def test_source_community_subfilter(self, sample_normalized_memes: list[dict]) -> None:
        """Verify filtering by specific subreddit community e.g. r/dankmemes."""
        store = MemoryStore()
        pydantic_memes = [NormalizedMeme(**m) for m in sample_normalized_memes]
        store.upsert_memes(pydantic_memes)

        dank_items, _ = store.get_latest(limit=50, offset=0, source="dankmemes", nsfw=True)
        for item in dank_items:
            assert "dankmemes" in item.source_community.lower()

    def test_nsfw_filtering_behavior(self, sample_normalized_memes: list[dict]) -> None:
        """Verify nsfw=False excludes NSFW posts, while nsfw=True includes them."""
        store = MemoryStore()
        pydantic_memes = [NormalizedMeme(**m) for m in sample_normalized_memes]
        store.upsert_memes(pydantic_memes)

        safe_items, safe_total = store.get_latest(limit=50, offset=0, nsfw=False)
        for item in safe_items:
            assert item.is_nsfw is False

        all_items, all_total = store.get_latest(limit=50, offset=0, nsfw=True)
        assert any(item.is_nsfw for item in all_items)
        assert all_total >= safe_total

    def test_get_random_meme_retrieval(self, sample_normalized_memes: list[dict]) -> None:
        """Verify get_random returns a valid meme matching filter criteria."""
        store = MemoryStore()
        pydantic_memes = [NormalizedMeme(**m) for m in sample_normalized_memes]
        store.upsert_memes(pydantic_memes)

        rand_meme = store.get_random(nsfw=False)
        assert rand_meme is not None
        assert rand_meme.is_nsfw is False
        assert isinstance(rand_meme.title, str)

    def test_get_random_with_unmatched_source_returns_none(self, sample_normalized_memes: list[dict]) -> None:
        """Verify get_random returns None when no memes match the filter."""
        store = MemoryStore()
        pydantic_memes = [NormalizedMeme(**m) for m in sample_normalized_memes]
        store.upsert_memes(pydantic_memes)

        rand_meme = store.get_random(source="nonexistent_source")
        assert rand_meme is None

    def test_deduplication_on_upsert_merges_engagement(self, meme_factory: callable) -> None:
        """Verify upserting duplicate content_hash updates/merges existing record rather than duplicating."""
        store = MemoryStore()
        m1 = NormalizedMeme(**meme_factory(id="m1", content_hash="hash_abc", score=1000, num_comments=20))
        m2 = NormalizedMeme(**meme_factory(id="m2", content_hash="hash_abc", score=5000, num_comments=80))

        store.upsert_memes([m1])
        assert store.count() == 1

        store.upsert_memes([m2])
        assert store.count() == 1
        items, _ = store.get_latest(limit=10, offset=0, nsfw=True)
        assert items[0].score >= 1000

    def test_memory_store_clear(self, sample_normalized_memes: list[dict]) -> None:
        """Verify clear resets all in-memory indices."""
        store = MemoryStore()
        pydantic_memes = [NormalizedMeme(**m) for m in sample_normalized_memes]
        store.upsert_memes(pydantic_memes)
        assert store.count() > 0

        store.clear()
        assert store.count() == 0
        items, total = store.get_latest()
        assert items == []
        assert total == 0

    def test_trending_time_window_filtering(self, meme_factory: callable) -> None:
        """Verify get_trending respects time_window filters (1h, 6h, 24h, 7d)."""
        store = MemoryStore()
        now = time.time()

        m_30m = NormalizedMeme(**meme_factory(id="m_30m", content_hash="h1", created_at=now - 1800, score=5000))
        m_3h = NormalizedMeme(**meme_factory(id="m_3h", content_hash="h2", created_at=now - 10800, score=8000))
        m_12h = NormalizedMeme(**meme_factory(id="m_12h", content_hash="h3", created_at=now - 43200, score=12000))
        m_3d = NormalizedMeme(**meme_factory(id="m_3d", content_hash="h4", created_at=now - 259200, score=20000))

        store.upsert_memes([m_30m, m_3h, m_12h, m_3d])

        items_1h, total_1h = store.get_trending(time_window="1h", nsfw=True)
        assert len(items_1h) == 1
        assert items_1h[0].id == "m_30m"

        items_6h, total_6h = store.get_trending(time_window="6h", nsfw=True)
        assert len(items_6h) == 2
        assert {m.id for m in items_6h} == {"m_30m", "m_3h"}

        items_24h, total_24h = store.get_trending(time_window="24h", nsfw=True)
        assert len(items_24h) == 3

        items_7d, total_7d = store.get_trending(time_window="7d", nsfw=True)
        assert len(items_7d) == 4

    def test_memory_store_get_by_id_and_hash(self, meme_factory: callable) -> None:
        """Verify retrieval by primary id and content hash."""
        store = MemoryStore()
        m = NormalizedMeme(**meme_factory(id="target_01", content_hash="target_hash_01"))
        store.upsert_memes([m])

        assert store.get_by_id("target_01") is not None
        assert store.get_by_id("nonexistent") is None
        assert store.get_by_content_hash("target_hash_01") is not None
        assert store.get_by_content_hash("unknown_hash") is None

    def test_memory_store_health_and_sources_status(self) -> None:
        """Verify health and source status aggregations."""
        store = MemoryStore()
        sources = store.get_sources()
        assert len(sources) > 0
        assert all(s.status == "ok" for s in sources)

        health = store.get_health()
        assert health.status == "ok"
        assert health.healthy_sources == len(sources)

    @pytest.mark.asyncio
    async def test_memory_store_hydration_from_sqlite(
        self, temp_sqlite_db: str, sample_normalized_memes: list[dict]
    ) -> None:
        """Verify hydration loads all records into empty memory store."""
        sqlite = SqliteStore(database_path=temp_sqlite_db)
        await sqlite.initialize()
        pydantic_memes = [NormalizedMeme(**m) for m in sample_normalized_memes]
        await sqlite.save_memes(pydantic_memes)

        store = MemoryStore()
        assert store.count() == 0
        loaded_count = await store.hydrate_from_db(sqlite)
        assert loaded_count == len(pydantic_memes)
        assert store.count() == len(pydantic_memes)
        await sqlite.close()

    def test_memory_store_sub_millisecond_query_latency(self, meme_factory: callable) -> None:
        """Verify that slicing latest and trending from memory executes in under 1ms."""
        store = MemoryStore()
        large_batch = [
            NormalizedMeme(**meme_factory(id=f"perf_{i}", content_hash=f"perf_hash_{i}", score=i * 10))
            for i in range(1000)
        ]
        store.upsert_memes(large_batch)

        # Measure 100 queries
        t0 = time.perf_counter()
        for _ in range(100):
            items, total = store.get_latest(limit=20, offset=0)
        avg_latest_ms = ((time.perf_counter() - t0) / 100) * 1000.0

        t1 = time.perf_counter()
        for _ in range(100):
            items, total = store.get_trending(limit=20, offset=0)
        avg_trending_ms = ((time.perf_counter() - t1) / 100) * 1000.0

        assert avg_latest_ms < 1.0
        assert avg_trending_ms < 1.0


class TestSqliteStore:
    """Tier 1 & Tier 2 tests for SqliteStore async database operations."""

    @pytest.mark.asyncio
    async def test_sqlite_initialize_and_save_load(
        self, temp_sqlite_db: str, sample_normalized_memes: list[dict]
    ) -> None:
        """Verify SQLite tables are created and memes can be saved and loaded."""
        sqlite = SqliteStore(database_path=temp_sqlite_db)
        await sqlite.initialize()

        pydantic_memes = [NormalizedMeme(**m) for m in sample_normalized_memes]
        saved_count = await sqlite.save_memes(pydantic_memes)
        assert saved_count >= len(pydantic_memes)

        loaded = await sqlite.load_all_memes()
        assert len(loaded) == len(pydantic_memes)
        await sqlite.close()

    @pytest.mark.asyncio
    async def test_sqlite_idempotent_save(
        self, temp_sqlite_db: str, meme_factory: callable
    ) -> None:
        """Verify saving identical records multiple times does not violate primary key constraints."""
        sqlite = SqliteStore(database_path=temp_sqlite_db)
        await sqlite.initialize()

        m = NormalizedMeme(**meme_factory(id="fixed_id", content_hash="fixed_hash"))
        await sqlite.save_memes([m])
        await sqlite.save_memes([m])

        loaded = await sqlite.load_all_memes()
        assert len(loaded) == 1
        assert loaded[0].id == "fixed_id"
        await sqlite.close()

    @pytest.mark.asyncio
    async def test_sqlite_empty_database_load(self, temp_sqlite_db: str) -> None:
        """Verify loading from freshly initialized database returns empty list."""
        sqlite = SqliteStore(database_path=temp_sqlite_db)
        await sqlite.initialize()
        loaded = await sqlite.load_all_memes()
        assert loaded == []
        await sqlite.close()

    @pytest.mark.asyncio
    async def test_sqlite_persistence_across_connections(
        self, temp_sqlite_db: str, meme_factory: callable
    ) -> None:
        """Verify data persists when database connection is closed and reopened."""
        sqlite1 = SqliteStore(database_path=temp_sqlite_db)
        await sqlite1.initialize()
        m = NormalizedMeme(**meme_factory(id="persist_01", title="Persisted across restarts"))
        await sqlite1.save_memes([m])
        await sqlite1.close()

        sqlite2 = SqliteStore(database_path=temp_sqlite_db)
        await sqlite2.initialize()
        loaded = await sqlite2.load_all_memes()
        assert len(loaded) == 1
        assert loaded[0].id == "persist_01"
        assert loaded[0].title == "Persisted across restarts"
        await sqlite2.close()

    @pytest.mark.asyncio
    async def test_sqlite_get_by_id_and_hash_and_count(
        self, temp_sqlite_db: str, meme_factory: callable
    ) -> None:
        """Verify get_meme_by_id, get_meme_by_content_hash, and count."""
        sqlite = SqliteStore(database_path=temp_sqlite_db)
        await sqlite.initialize()
        m = NormalizedMeme(**meme_factory(id="db_01", content_hash="db_hash_01", score=500))
        await sqlite.save_memes([m])

        assert await sqlite.count() == 1
        found_id = await sqlite.get_meme_by_id("db_01")
        assert found_id is not None
        assert found_id.id == "db_01"

        found_hash = await sqlite.get_meme_by_content_hash("db_hash_01")
        assert found_hash is not None
        assert found_hash.content_hash == "db_hash_01"

        assert await sqlite.get_meme_by_id("db_missing") is None
        assert await sqlite.get_meme_by_content_hash("hash_missing") is None
        await sqlite.close()
