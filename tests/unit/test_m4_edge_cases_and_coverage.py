"""Targeted edge-case and comprehensive coverage test suite for Milestone 4 verification."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from app.api.v1.memes import get_memory_store as get_memes_memory_store
from app.api.v1.sources import get_api_health
from app.api.v1.sources import get_memory_store as get_sources_memory_store
from app.config import Settings
from app.core.dedup import compute_content_hash, normalize_url
from app.core.ranking import calculate_trending_score
from app.ingestion.base import (
    BaseSourceFetcher,
    calculate_trending_score as base_calc_trending,
    compute_content_hash as base_compute_hash,
)
from app.models.meme import MediaType, Meme, NormalizedMeme, PaginatedMemeResponse, SourcePlatform
from app.models.source import SourceStatus
from app.storage.memory_store import MemoryStore
from app.storage.sqlite_store import SqliteStore


class DummyFetcher(BaseSourceFetcher):
    """Concrete implementation of BaseSourceFetcher for testing."""

    async def fetch_memes(self) -> list[NormalizedMeme]:
        return []

    def load_offline_fixtures(self) -> list[NormalizedMeme]:
        return []


class TestM4IngestionBaseAndConfig:
    """Tests covering ingestion base helper functions and config parsing."""

    def test_base_compute_content_hash(self) -> None:
        """Verify compute_content_hash in base module handles queries and whitespace."""
        h1 = base_compute_hash("https://i.redd.it/test.png?width=100&auto=webp", "  Funny Title  ")
        h2 = base_compute_hash("https://i.redd.it/test.png", "funny title")
        assert h1 == h2
        assert len(h1) == 64

        empty_h = base_compute_hash("", "")
        assert len(empty_h) == 64

    def test_base_calculate_trending_score(self) -> None:
        """Verify trending score calculation handles edge numbers."""
        now = 1000000.0
        score = base_calc_trending(score=500, num_comments=50, created_at=now - 3600, current_time=now)
        assert score > 0.0

        # Negative engagement clamped to 0
        neg_score = base_calc_trending(score=-10, num_comments=-5, created_at=now, current_time=now)
        assert neg_score == 0.0

        # Current time fallback
        live_score = base_calc_trending(score=100, num_comments=10, created_at=time.time())
        assert live_score >= 0.0

    def test_dummy_fetcher_lifecycle(self) -> None:
        """Verify BaseSourceFetcher status updates for success and failure."""
        fetcher = DummyFetcher(name="test_feed", platform=SourcePlatform.REDDIT, community="r/memes")
        assert fetcher.status.status == "ok"
        assert fetcher.status.item_count == 0

        fetcher.update_success(count=42, latency_ms=123.456)
        assert fetcher.status.status == "ok"
        assert fetcher.status.item_count == 42
        assert fetcher.status.latency_ms == 123.46
        assert fetcher.status.last_synced_at is not None
        assert fetcher.status.last_error is None

        fetcher.update_failure(RuntimeError("Connection timeout"))
        assert fetcher.status.status == "degraded"
        assert fetcher.status.last_error == "Connection timeout"

    def test_config_parse_list_fields(self) -> None:
        """Verify parse_list_fields handles invalid json gracefully."""
        # JSON parse error branch fallback
        s = Settings(REDDIT_SUBREDDITS="[invalid_json_str, memes]")
        assert "memes" in s.REDDIT_SUBREDDITS or len(s.REDDIT_SUBREDDITS) > 0

        # Comma separated
        s2 = Settings(REDDIT_SUBREDDITS="memes, dankmemes , wholesome")
        assert s2.REDDIT_SUBREDDITS == ["memes", "dankmemes", "wholesome"]

        # Valid JSON array
        s3 = Settings(REDDIT_SUBREDDITS='["memes", "me_irl"]')
        assert s3.REDDIT_SUBREDDITS == ["memes", "me_irl"]


class TestM4ModelsExtended:
    """Tests covering domain model edge cases and conversions."""

    def test_normalized_meme_defaults_and_validation(self) -> None:
        """Verify NormalizedMeme default field handling and compute logic."""
        data = {
            "id": "reddit_memes_abc123",
            "title": "Funny Test Title",
            "media_url": "https://i.redd.it/abc1234.png",
            "source_platform": "reddit",
            "source_community": "r/memes",
            "created_at": time.time() - 1800,
            "score": 100,
            "num_comments": 20,
        }
        m = NormalizedMeme(**data)
        assert m.raw_id == "abc123"
        assert m.author == "unknown"
        assert m.domain == ""
        assert m.title == "Funny Test Title"
        assert m.permalink == ""
        assert m.content_hash is not None
        assert m.trending_score > 0.0

    def test_meme_alias_syncing_and_conversions(self) -> None:
        """Verify Meme alias synchronization between url/media_url and source/source_platform."""
        # Test dict without url but with media_url
        d1 = {
            "id": "kym_12345",
            "title": "Doggo",
            "media_url": "https://i.kym-cdn.com/doggo.jpg",
            "source_platform": SourcePlatform.KNOWYOURMEME,
            "source_community": "confirmed",
            "created_at": 1700000000.0,
        }
        m1 = Meme(**d1)
        assert m1.url == "https://i.kym-cdn.com/doggo.jpg"
        assert m1.source == "knowyourmeme"

        # Test dict with url and source
        d2 = {
            "id": "reddit_memes_999",
            "title": "Cat",
            "url": "https://i.redd.it/cat.jpg",
            "source": "reddit",
            "source_community": "r/memes",
            "created_at": 1700000000.0,
        }
        m2 = Meme(**d2)
        assert m2.media_url == "https://i.redd.it/cat.jpg"
        assert m2.source_platform == SourcePlatform.REDDIT

        # Test from_normalized conversion
        norm = NormalizedMeme(
            id="reddit_dankmemes_888",
            raw_id="888",
            title="Dank Meme",
            media_url="https://i.redd.it/dank.jpg",
            media_type=MediaType.IMAGE,
            source_platform="reddit",
            source_community="r/dankmemes",
            permalink="https://reddit.com/r/dankmemes/888",
            created_at=1700000000.0,
        )
        m3 = Meme.from_normalized(norm)
        assert m3.id == norm.id
        assert m3.source == "reddit"


class TestM4MemoryStoreExtended:
    """Tests covering MemoryStore upsert with different formats, time windows, and query key resolution."""

    def test_upsert_dict_and_meme_objects(self) -> None:
        """Verify MemoryStore accepts dicts and Meme objects during upsert."""
        store = MemoryStore()
        now = time.time()

        dict_item = {
            "id": "reddit_memes_dict1",
            "raw_id": "dict1",
            "title": "Dict Meme",
            "media_url": "https://i.redd.it/dict1.png",
            "source_platform": "reddit",
            "source_community": "r/memes",
            "permalink": "https://reddit.com/r/memes/dict1",
            "created_at": now,
        }

        meme_reddit = Meme(
            id="reddit_dankmemes_meme1",
            title="Reddit Meme",
            url="https://i.redd.it/meme1.png",
            media_url="https://i.redd.it/meme1.png",
            source="reddit",
            source_platform="reddit",
            source_community="r/dankmemes",
            permalink="https://reddit.com/r/dankmemes/meme1",
            created_at=now,
        )

        meme_kym = Meme(
            id="kym_meme2",
            title="KYM Meme",
            url="https://i.kym-cdn.com/meme2.jpg",
            media_url="https://i.kym-cdn.com/meme2.jpg",
            source="knowyourmeme",
            source_platform="knowyourmeme",
            source_community="confirmed",
            permalink="https://knowyourmeme.com/memes/meme2",
            created_at=now,
        )

        store.upsert_memes([dict_item, meme_reddit, meme_kym])
        assert store.count() == 3

    def test_time_window_filtering_in_latest_and_trending(self) -> None:
        """Verify time window filtering (1h, 6h, 24h, 7d) in latest and trending."""
        store = MemoryStore()
        now = time.time()

        m_fresh = NormalizedMeme(
            id="fresh_1",
            title="Fresh 30min",
            media_url="https://i.redd.it/fresh.png",
            source_platform="reddit",
            source_community="r/memes",
            permalink="https://reddit.com/r/memes/fresh",
            created_at=now - 1800,
            score=1000,
        )
        m_2h = NormalizedMeme(
            id="old_2h",
            title="Old 2 hours",
            media_url="https://i.redd.it/2h.png",
            source_platform="reddit",
            source_community="r/memes",
            permalink="https://reddit.com/r/memes/2h",
            created_at=now - 7200,
            score=500,
        )
        m_2d = NormalizedMeme(
            id="old_2d",
            title="Old 2 days",
            media_url="https://i.redd.it/2d.png",
            source_platform="reddit",
            source_community="r/memes",
            permalink="https://reddit.com/r/memes/2d",
            created_at=now - 172800,
            score=200,
        )

        store.upsert_memes([m_fresh, m_2h, m_2d])

        # 1h filter should only include m_fresh
        items_1h, count_1h = store.get_latest(time_window="1h")
        assert count_1h == 1
        assert items_1h[0].id == "fresh_1"

        # 6h filter should include m_fresh and m_2h
        items_6h, count_6h = store.get_latest(time_window="6h")
        assert count_6h == 2

        # 7d filter includes all 3
        items_7d, count_7d = store.get_latest(time_window="7d")
        assert count_7d == 3

        # Trending with 1h time window
        trend_1h, trend_cnt_1h = store.get_trending(time_window="1h")
        assert trend_cnt_1h == 1
        assert trend_1h[0].id == "fresh_1"

    def test_composite_source_resolution_and_matching(self) -> None:
        """Verify composite source resolution formats (reddit:r/memes, reddit/memes, etc.)."""
        store = MemoryStore()
        now = time.time()
        m = NormalizedMeme(
            id="reddit_memes_1",
            title="Subreddit Meme",
            media_url="https://i.redd.it/sub1.png",
            source_platform="reddit",
            source_community="r/memes",
            permalink="https://reddit.com/r/memes/sub1",
            created_at=now,
        )
        store.upsert_memes([m])

        # Query with composite syntax
        res_key = store._resolve_source_query_key("reddit:r/memes")
        assert res_key is not None

        items, total = store.get_latest(source="reddit:r/memes")
        assert total == 1
        assert items[0].id == "reddit_memes_1"

        # Direct _matches_source test
        assert store._matches_source(m, "reddit") is True
        assert store._matches_source(m, "r/memes") is True
        assert store._matches_source(m, "memes") is True
        assert store._matches_source(m, "reddit:r/memes") is True
        assert store._matches_source(m, "knowyourmeme") is False


class TestM4ApiDependenciesAndHealth:
    """Tests covering API dependency fallbacks and health endpoints."""

    def test_get_memory_store_state_fallback(self) -> None:
        """Verify get_memory_store initializes MemoryStore if app.state has none."""
        mock_request = MagicMock()
        mock_request.app.state.memory_store = None

        store1 = get_memes_memory_store(mock_request)
        assert isinstance(store1, MemoryStore)
        assert mock_request.app.state.memory_store == store1

        # Sources dependency fallback
        mock_request2 = MagicMock()
        mock_request2.app.state.memory_store = None
        store2 = get_sources_memory_store(mock_request2)
        assert isinstance(store2, MemoryStore)

    @pytest.mark.asyncio
    async def test_api_health_endpoint_direct(self) -> None:
        """Verify get_api_health direct function call returns HealthResponse."""
        store = MemoryStore()
        health = await get_api_health(store=store)
        assert health.status in ("ok", "healthy", "up")
        assert health.total_memes_cached == 0


class TestM4ParsersAndSqliteBranches:
    """Tests covering reddit and kym parser helpers and sqlite store branches."""

    def test_parse_reddit_listing_helper(self) -> None:
        """Verify parse_reddit_listing top-level function works with str and dict."""
        from app.ingestion.reddit import parse_reddit_listing

        dict_payload = {
            "kind": "Listing",
            "data": {
                "children": [
                    {
                        "kind": "t3",
                        "data": {
                            "id": "helper1",
                            "title": "Helper Title",
                            "url": "https://i.redd.it/helper1.png",
                            "subreddit": "memes",
                            "permalink": "/r/memes/comments/helper1/",
                            "author": "tester",
                            "ups": 150,
                            "num_comments": 15,
                            "created_utc": time.time() - 3600,
                            "over_18": False,
                            "is_video": False,
                        },
                    }
                ]
            },
        }

        # Dict input
        memes_dict = parse_reddit_listing(dict_payload, subreddit="r/memes")
        assert len(memes_dict) == 1
        assert memes_dict[0].id == "reddit_memes_helper1"

        # String JSON input
        import json
        json_str = json.dumps(dict_payload)
        memes_str = parse_reddit_listing(json_str, subreddit="r/memes")
        assert len(memes_str) == 1
        assert memes_str[0].id == "reddit_memes_helper1"

        # Invalid input type
        assert parse_reddit_listing(12345) == []  # type: ignore

    def test_kym_parse_trending_json(self) -> None:
        """Verify KnowYourMemeFetcher.parse_trending_json with valid and invalid input."""
        from app.ingestion.knowyourmeme import KnowYourMemeFetcher

        fetcher = KnowYourMemeFetcher()

        # Invalid JSON
        assert fetcher.parse_trending_json("not valid json [{}") == []

        # Valid JSON array
        valid_json = """[
            {
                "id": "kym_999",
                "title": "Trending KYM Entry",
                "url": "https://i.kym-cdn.com/photos/images/original/000/999/999/test.jpg",
                "permalink": "https://knowyourmeme.com/memes/trending-entry",
                "score": 500,
                "num_comments": 40,
                "created_at": 1700000000
            },
            {
                "id": "kym_empty",
                "title": "",
                "url": ""
            }
        ]"""
        res = fetcher.parse_trending_json(valid_json)
        assert len(res) == 1
        assert res[0].id == "kym_999"

    @pytest.mark.asyncio
    async def test_sqlite_store_branch_coverage(self, temp_sqlite_db: str) -> None:
        """Verify SqliteStore empty batch save and row conversion fallbacks."""
        store = SqliteStore(database_path=temp_sqlite_db)
        await store.initialize()

        # Empty save returns 0
        assert await store.save_memes([]) == 0

        # Row conversion with fallback types
        row = (
            "test_fallback_id",
            "fallback_id",
            "Fallback Title",
            "https://i.redd.it/fallback.png",
            "unknown_media_type",  # triggers ValueError -> MediaType.IMAGE
            "custom_source_platform",  # triggers ValueError -> keeps string
            "r/memes",
            "https://reddit.com/r/memes/comments/fallback/",
            "author",
            50,
            5,
            time.time() - 100,
            0,
            "i.redd.it",
            "dummy_hash",
            10.5,
        )
        converted = store._row_to_meme(row)
        assert converted.media_type == MediaType.IMAGE
        assert converted.source_platform == "custom_source_platform"

        await store.close()

