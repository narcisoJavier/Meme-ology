"""Tier 5 Adversarial and Hardening Test Suite.

Comprehensive stress tests covering:
- High-concurrency multithreaded and asyncio lock contention on MemoryStore and SQLiteStore
- Temporal boundary conditions (epoch 0, future timestamps, sub-second precision, clock skew)
- URL canonicalization and payload fuzzing with adversarial inputs and tracking param abuse
- Pagination boundary permutations (huge offsets, edge limits, empty filters)
- Reddit, KYM, and Base fetcher error isolation and recovery under catastrophic failures
- Strict invariant checks (engagement maximization, temporal anchor preservation, NSFW taint propagation)
- Security headers, backoff clamping, rate limiter throttling, and configuration resilience
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import html
import json
import logging
import os
import random
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import httpx
import pytest
import pytest_asyncio

from app.config import Settings, get_settings
from app.core.dedup import compute_content_hash, normalize_url
from app.core.ranking import calculate_trending_score
from app.core.security import (
    PoliteRateLimiter,
    calculate_backoff_delay,
    get_random_user_agent,
    get_request_headers,
)
from app.ingestion.base import (
    BaseSourceFetcher,
    calculate_trending_score as base_calc_trending,
    compute_content_hash as base_compute_hash,
)
from app.ingestion.knowyourmeme import (
    KnowYourMemeFetcher,
    extract_image_from_description,
    parse_kym_rss,
    parse_rfc822_date,
)
from app.ingestion.reddit import (
    RedditFetcher,
    parse_reddit_listing,
)
from app.ingestion.worker import MemePollingWorker
from app.main import app, create_app
from app.models.meme import MediaType, Meme, NormalizedMeme, PaginatedMemeResponse, SourcePlatform
from app.models.source import HealthResponse, SourceStatus, SourcesResponse
from app.storage.memory_store import MemoryStore, _extract_source_tokens
from app.storage.sqlite_store import SqliteStore


# ==============================================================================
# SECTION 1: High Concurrency & Lock Contention Stress on Storage
# ==============================================================================

class TestStorageConcurrencyStress:
    """Adversarial concurrent reading and writing to in-memory store and SQLite."""

    def test_multithreaded_memory_store_hammer(self, sample_normalized_memes: List[dict]) -> None:
        """Spawn 20 parallel OS threads hammering MemoryStore with concurrent writes,

        upserts with engagement updates, reads, filter queries, and random sampling.
        Assert that zero race conditions or index corruptions occur.
        """
        store = MemoryStore()
        base_memes = [NormalizedMeme(**m) for m in sample_normalized_memes]
        store.upsert_memes(base_memes)

        errors: List[Exception] = []
        num_threads = 20
        ops_per_thread = 100

        def worker_task(thread_id: int) -> None:
            try:
                for i in range(ops_per_thread):
                    op = random.choice([
                        "read_latest",
                        "read_trending",
                        "read_random",
                        "upsert_new",
                        "upsert_existing",
                        "check_health",
                        "check_sources",
                    ])
                    if op == "read_latest":
                        src = random.choice([None, "reddit", "r/memes", "knowyourmeme", "kym:confirmed"])
                        nsfw = random.choice([True, False])
                        items, total = store.get_latest(limit=10, offset=random.randint(0, 5), source=src, nsfw=nsfw)
                        assert isinstance(items, list)
                        assert total >= len(items)
                    elif op == "read_trending":
                        src = random.choice([None, "reddit", "dankmemes", "kym"])
                        nsfw = random.choice([True, False])
                        items, total = store.get_trending(limit=10, offset=random.randint(0, 5), source=src, nsfw=nsfw)
                        assert isinstance(items, list)
                        assert total >= len(items)
                    elif op == "read_random":
                        src = random.choice([None, "r/memes", "knowyourmeme"])
                        _ = store.get_random(source=src, nsfw=True)
                    elif op == "upsert_new":
                        new_meme = NormalizedMeme(
                            id=f"thread_{thread_id}_meme_{i}",
                            title=f"Concurrent Meme {thread_id}-{i}",
                            media_url=f"https://i.redd.it/thread_{thread_id}_{i}.jpg",
                            media_type=MediaType.IMAGE,
                            source_platform=SourcePlatform.REDDIT,
                            source_community="r/memes",
                            permalink=f"https://reddit.com/r/memes/{thread_id}_{i}",
                            score=random.randint(100, 50000),
                            num_comments=random.randint(10, 500),
                            created_at=time.time() - random.randint(100, 10000),
                            is_nsfw=(i % 5 == 0),
                        )
                        store.upsert_memes([new_meme])
                    elif op == "upsert_existing":
                        # Upsert with higher score to test engagement merge under concurrency
                        updated_meme = NormalizedMeme(
                            id="reddit_memes_001",
                            title="Compiler first try success",
                            media_url="https://i.redd.it/compiler01.jpg",
                            media_type=MediaType.IMAGE,
                            source_platform=SourcePlatform.REDDIT,
                            source_community="r/memes",
                            permalink="https://reddit.com/r/memes/1",
                            score=random.randint(20000, 99999),
                            num_comments=random.randint(500, 2000),
                            created_at=time.time() - 7200,
                            is_nsfw=False,
                        )
                        store.upsert_memes([updated_meme])
                    elif op == "check_health":
                        health = store.get_health_status()
                        assert health.total_memes >= len(base_memes)
                    elif op == "check_sources":
                        sources = store.get_sources_status()
                        assert len(sources) > 0
            except Exception as exc:
                errors.append(exc)

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_task, tid) for tid in range(num_threads)]
            concurrent.futures.wait(futures)

        assert len(errors) == 0, f"Encountered thread errors during concurrency hammer: {errors}"
        # Assert internal index consistency post-hammer
        assert len(store._latest_index) == store.count()
        assert len(store._trending_index) == store.count()
        assert len(store._latest_index_sfw) <= len(store._latest_index)
        assert all(not m.is_nsfw for m in store._latest_index_sfw)
        assert all(not m.is_nsfw for m in store._trending_index_sfw)

    @pytest.mark.asyncio
    async def test_asyncio_sqlite_store_concurrent_hammer(self, sample_normalized_memes: List[dict]) -> None:
        """Spawn 15 concurrent asyncio tasks reading and writing to SqliteStore."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name

        try:
            store = SqliteStore(database_path=db_path)
            await store.initialize()

            base_memes = [NormalizedMeme(**m) for m in sample_normalized_memes]
            await store.save_memes(base_memes)

            async def async_worker(task_id: int) -> None:
                for i in range(25):
                    # Save a batch
                    task_memes = [
                        NormalizedMeme(
                            id=f"async_{task_id}_{i}_{j}",
                            title=f"Async Meme {task_id}-{i}-{j}",
                            media_url=f"https://i.redd.it/async_{task_id}_{i}_{j}.png",
                            media_type=MediaType.IMAGE,
                            source_platform=SourcePlatform.REDDIT,
                            source_community="r/dankmemes",
                            permalink="https://reddit.com",
                            score=100 + j,
                            num_comments=10 + j,
                            created_at=time.time() - (i * 100 + j),
                            is_nsfw=False,
                        )
                        for j in range(3)
                    ]
                    await store.save_memes(task_memes)
                    # Query back
                    cnt = await store.count()
                    assert cnt >= len(base_memes)
                    by_id = await store.get_meme_by_id(f"async_{task_id}_{i}_0")
                    assert by_id is not None
                    by_hash = await store.get_meme_by_content_hash(by_id.content_hash)
                    assert by_hash is not None

            tasks = [async_worker(t) for t in range(15)]
            await asyncio.gather(*tasks)

            all_memes = await store.load_all_memes()
            assert len(all_memes) == await store.count()
            # Verify ordering by created_at DESC
            for k in range(len(all_memes) - 1):
                assert all_memes[k].created_at >= all_memes[k + 1].created_at
        finally:
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                except OSError:
                    pass


# ==============================================================================
# SECTION 2: Invariant Hardening (Engagement Merge, Temporal Anchor, NSFW Taint)
# ==============================================================================

class TestStoreInvariantsAndTypeHeterogeneity:
    """Verify core domain invariants during upsert and retrieval."""

    def test_engagement_maximization_and_temporal_anchor_invariants(self) -> None:
        """Verify that re-upserting a meme:

        1. Takes max(score_1, score_2)
        2. Takes max(comments_1, comments_2)
        3. Preserves min(created_at_1, created_at_2) (earliest creation timestamp)
        4. Propagates is_nsfw = is_nsfw_1 OR is_nsfw_2
        """
        store = MemoryStore()

        meme_v1 = NormalizedMeme(
            id="reddit_memes_merge_test",
            title="Invariant Test Title",
            media_url="https://i.redd.it/merge_test.jpg",
            media_type=MediaType.IMAGE,
            source_platform=SourcePlatform.REDDIT,
            source_community="r/memes",
            permalink="https://reddit.com/r/memes/merge1",
            score=500,
            num_comments=50,
            created_at=1700000000.0,
            is_nsfw=False,
        )
        store.upsert_memes([meme_v1])

        # Second version with higher score, lower comments, later timestamp, NSFW flag
        meme_v2 = NormalizedMeme(
            id="reddit_memes_merge_test",
            title="Invariant Test Title",
            media_url="https://i.redd.it/merge_test.jpg",
            media_type=MediaType.IMAGE,
            source_platform=SourcePlatform.REDDIT,
            source_community="r/memes",
            permalink="https://reddit.com/r/memes/merge1",
            score=1200,          # HIGHER -> should win
            num_comments=20,     # LOWER -> previous 50 should be preserved
            created_at=1700050000.0,  # LATER -> previous 1700000000.0 should be preserved
            is_nsfw=True,        # TAINT -> result must be NSFW
        )
        store.upsert_memes([meme_v2])

        merged = store.get_by_id("reddit_memes_merge_test")
        assert merged is not None
        assert merged.score == 1200
        assert merged.num_comments == 50
        assert merged.created_at == 1700000000.0
        assert merged.is_nsfw is True

    def test_upsert_heterogeneous_types_in_single_batch(self) -> None:
        """MemoryStore.upsert_memes handles mixed inputs: dicts, Meme objects, and NormalizedMeme objects."""
        store = MemoryStore()

        raw_dict = {
            "id": "dict_meme_01",
            "title": "Dict Meme",
            "media_url": "https://i.redd.it/dict01.png",
            "media_type": "image",
            "source_platform": "reddit",
            "source_community": "r/memes",
            "permalink": "https://reddit.com/dict01",
            "score": 100,
            "num_comments": 10,
            "created_at": time.time(),
            "is_nsfw": False,
        }

        meme_obj = Meme(
            id="model_meme_02",
            title="Pydantic Meme",
            url="https://i.kym-cdn.com/photos/images/original/000/000/001/kym.jpg",
            source="knowyourmeme",
            source_platform=SourcePlatform.KNOWYOURMEME,
            source_community="confirmed",
            permalink="https://knowyourmeme.com/photos/1",
            score=250,
            num_comments=25,
            created_at=time.time() - 500,
            is_nsfw=False,
        )

        norm_obj = NormalizedMeme(
            id="norm_meme_03",
            title="Normalized Meme",
            media_url="https://i.redd.it/norm03.gif",
            media_type=MediaType.GIF,
            source_platform=SourcePlatform.REDDIT,
            source_community="r/dankmemes",
            permalink="https://reddit.com/norm03",
            score=300,
            num_comments=30,
            created_at=time.time() - 1000,
            is_nsfw=False,
        )

        count = store.upsert_memes([raw_dict, meme_obj, norm_obj])
        assert count == 3
        assert store.get_by_id("dict_meme_01") is not None
        assert store.get_by_id("model_meme_02") is not None
        assert store.get_by_id("norm_meme_03") is not None


# ==============================================================================
# SECTION 3: URL Canonicalization & Content Hashing Boundary Permutations
# ==============================================================================

class TestDedupAndCanonicalizationHardening:
    """Adversarial testing of URL normalization, tracking parameter stripping, and hashing."""

    @pytest.mark.parametrize(
        "raw_url,expected_canonical",
        [
            # Protocol relative URLs
            ("//cdn.example.com/pic.jpg", "https://cdn.example.com/pic.jpg"),
            # Missing scheme
            ("i.redd.it/abc1234.png", "https://i.redd.it/abc1234.png"),
            ("HTTP://I.REDD.IT/ABC1234.PNG", "https://i.redd.it/ABC1234.PNG"),
            # Trailing slashes on paths
            ("https://example.com/path/image.jpg/", "https://example.com/path/image.jpg"),
            # Tracking parameter stripping
            ("https://i.redd.it/pic.jpg?utm_source=reddit&utm_medium=app&utm_campaign=share", "https://i.redd.it/pic.jpg"),
            ("https://i.redd.it/pic.jpg?ref=share&s=abc12345&auto=webp", "https://i.redd.it/pic.jpg"),
            ("https://i.redd.it/pic.jpg?width=960&crop=smart&format=pjpg", "https://i.redd.it/pic.jpg"),
            # Retain non-tracking query parameters
            ("https://example.com/view?id=456&version=2", "https://example.com/view?id=456&version=2"),
            # Empty / whitespace / None
            ("", ""),
            ("   ", ""),
            (None, ""),
        ],
    )
    def test_normalize_url_permutations(self, raw_url: Optional[str], expected_canonical: str) -> None:
        assert normalize_url(raw_url) == expected_canonical

    def test_compute_content_hash_invariance(self) -> None:
        """Verify content hash is invariant under whitespace, title casing, and tracking query params."""
        hash1 = compute_content_hash(
            "https://i.redd.it/pic.jpg?utm_source=share&utm_medium=ios_app",
            "  The Funniest MEME Ever  ",
        )
        hash2 = compute_content_hash(
            "https://i.redd.it/pic.jpg?ref=search",
            "the funniest meme ever",
        )
        assert hash1 == hash2

    def test_base_and_dedup_hash_and_ranking_parity(self) -> None:
        """Verify parity between app/core/dedup.py, app/core/ranking.py and app/ingestion/base.py."""
        # Content hash parity
        h1 = compute_content_hash("https://i.redd.it/test.jpg?utm_source=1", "Test Title")
        h2 = base_compute_hash("https://i.redd.it/test.jpg?utm_source=1", "Test Title")
        assert h1 == h2

        # Trending score parity
        now = 1725300000.0
        s1 = calculate_trending_score(1500, 300, now - 7200, current_time=now)
        s2 = base_calc_trending(1500, 300, now - 7200, current_time=now)
        assert s1 == s2


# ==============================================================================
# SECTION 4: Temporal & Boundary Timestamp Hardening
# ==============================================================================

class TestTemporalBoundaryConditions:
    """Stress test trending calculations and time window filters on edge timestamps."""

    def test_trending_score_boundary_values(self) -> None:
        """Verify trending algorithm gracefully handles negative engagement, zero created_at,

        future created_at, and astronomical numbers without ZeroDivisionError or overflow.
        """
        now = time.time()

        # 1. Negative scores and comments (clamped to 0)
        neg_score = calculate_trending_score(score=-500, comments=-20, created_at=now)
        assert neg_score == 0.0

        # 2. Future timestamp (created_at > now -> age = 0)
        future_score = calculate_trending_score(score=1000, comments=50, created_at=now + 3600.0, current_time=now)
        normal_score = calculate_trending_score(score=1000, comments=50, created_at=now, current_time=now)
        assert future_score == normal_score

        # 3. Epoch 0 (1970) timestamp
        ancient_score = calculate_trending_score(score=100000, comments=5000, created_at=0.0, current_time=now)
        assert ancient_score < 0.1  # Deeply decayed

        # 4. Astronomical engagement values
        huge_score = calculate_trending_score(score=10_000_000, comments=1_000_000, created_at=now, current_time=now)
        assert huge_score > 0 and not (huge_score == float("inf"))

        # 5. num_comments keyword argument precedence
        kw_score = calculate_trending_score(score=100, comments=10, num_comments=50, created_at=now, current_time=now)
        expected_score = calculate_trending_score(score=100, comments=50, created_at=now, current_time=now)
        assert kw_score == expected_score

    def test_memory_store_time_window_filtering(self) -> None:
        """Test time_window filters ('1h', '6h', '24h', '7d', 'all', invalid) against exact cutoff boundaries."""
        store = MemoryStore()
        now = time.time()

        memes = [
            NormalizedMeme(
                id=f"time_meme_{label}",
                title=f"Time Meme {label}",
                media_url=f"https://i.redd.it/{label}.jpg",
                media_type=MediaType.IMAGE,
                source_platform=SourcePlatform.REDDIT,
                source_community="r/memes",
                permalink=f"https://reddit.com/{label}",
                score=100,
                num_comments=10,
                created_at=now - offset_sec,
                is_nsfw=False,
            )
            for label, offset_sec in [
                ("30m", 1800),     # <= 1h
                ("2h", 7200),      # <= 6h
                ("12h", 43200),    # <= 24h
                ("3d", 259200),    # <= 7d
                ("10d", 864000),   # > 7d
            ]
        ]
        store.upsert_memes(memes)

        # 1h filter -> only '30m'
        items_1h, total_1h = store.get_latest(time_window="1h")
        assert total_1h == 1
        assert items_1h[0].id == "time_meme_30m"

        # 6h filter -> '30m' and '2h'
        items_6h, total_6h = store.get_latest(time_window="6h")
        assert total_6h == 2

        # 24h filter -> '30m', '2h', '12h'
        items_24h, total_24h = store.get_latest(time_window="24h")
        assert total_24h == 3

        # 7d filter -> '30m', '2h', '12h', '3d'
        items_7d, total_7d = store.get_latest(time_window="7d")
        assert total_7d == 4

        # Invalid or 'all' filter -> returns all 5 memes
        items_all, total_all = store.get_latest(time_window="all")
        assert total_all == 5

        items_invalid, total_invalid = store.get_latest(time_window="invalid_tw")
        assert total_invalid == 5

        # Also verify trending time window filtering
        t_items_1h, t_total_1h = store.get_trending(time_window="1h")
        assert t_total_1h == 1
        assert t_items_1h[0].id == "time_meme_30m"


# ==============================================================================
# SECTION 5: Source Filter Resolution & Token Permutations
# ==============================================================================

class TestSourceFilterResolutionPermutations:
    """Test every conceivable syntax and variation of the source query parameter."""

    @pytest.fixture(autouse=True)
    def setup_store(self, sample_normalized_memes: List[dict]) -> None:
        self.store = MemoryStore()
        memes = [NormalizedMeme(**m) for m in sample_normalized_memes]
        self.store.upsert_memes(memes)

    @pytest.mark.parametrize(
        "query,expected_min_count,should_contain_platform",
        [
            ("reddit", 4, SourcePlatform.REDDIT),
            ("Reddit", 4, SourcePlatform.REDDIT),
            ("  REDDIT  ", 4, SourcePlatform.REDDIT),
            ("knowyourmeme", 2, SourcePlatform.KNOWYOURMEME),
            ("kym", 2, SourcePlatform.KNOWYOURMEME),
            ("know your meme", 2, SourcePlatform.KNOWYOURMEME),
            ("r/memes", 1, SourcePlatform.REDDIT),
            ("memes", 1, SourcePlatform.REDDIT),
            ("dankmemes", 1, SourcePlatform.REDDIT),
            ("r/dankmemes", 1, SourcePlatform.REDDIT),
            ("me_irl", 1, SourcePlatform.REDDIT),
            ("r/me_irl", 1, SourcePlatform.REDDIT),
            ("wholesomememes", 1, SourcePlatform.REDDIT),
            ("reddit:r/memes", 1, SourcePlatform.REDDIT),
            ("reddit/r/memes", 1, SourcePlatform.REDDIT),
            ("reddit:memes", 1, SourcePlatform.REDDIT),
            ("reddit/memes", 1, SourcePlatform.REDDIT),
            ("knowyourmeme:confirmed", 2, SourcePlatform.KNOWYOURMEME),
            ("kym:confirmed", 2, SourcePlatform.KNOWYOURMEME),
            ("kym/confirmed", 2, SourcePlatform.KNOWYOURMEME),
        ],
    )
    def test_source_filter_token_resolution(
        self, query: str, expected_min_count: int, should_contain_platform: SourcePlatform
    ) -> None:
        items, total = self.store.get_latest(source=query, nsfw=True)
        assert total >= expected_min_count
        assert all(m.source_platform == should_contain_platform for m in items)

    def test_nonexistent_source_filter_returns_empty(self) -> None:
        items, total = self.store.get_latest(source="completely_fake_subreddit_xyz")
        assert total == 0
        assert items == []

        random_meme = self.store.get_random(source="completely_fake_subreddit_xyz")
        assert random_meme is None


# ==============================================================================
# SECTION 6: Ingestion Parser Adversarial Payload Hardening
# ==============================================================================

class TestIngestionParsersAdversarialHardening:
    """Fuzz Reddit and KYM parsers with corrupt, deeply nested, or malformed data."""

    def test_parse_reddit_listing_top_level_helper(self) -> None:
        """Verify parse_reddit_listing accepts JSON string, dict, or invalid types safely."""
        json_str = json.dumps({
            "kind": "Listing",
            "data": {
                "children": [
                    {
                        "kind": "t3",
                        "data": {
                            "id": "helper01",
                            "title": "Helper Title",
                            "url": "https://i.redd.it/helper01.png",
                            "domain": "i.redd.it",
                            "score": 500,
                            "num_comments": 12,
                            "created_utc": 1725300000.0,
                        },
                    }
                ]
            },
        })
        memes_from_str = parse_reddit_listing(json_str, subreddit="r/memes")
        assert len(memes_from_str) == 1
        assert memes_from_str[0].id == "reddit_memes_helper01"

        dict_payload = json.loads(json_str)
        memes_from_dict = parse_reddit_listing(dict_payload, subreddit="r/dankmemes")
        assert len(memes_from_dict) == 1
        assert memes_from_dict[0].id == "reddit_dankmemes_helper01"

        # Invalid payloads
        assert parse_reddit_listing(12345) == []  # type: ignore
        assert parse_reddit_listing("") == []
        assert parse_reddit_listing("{not-valid-json}") == []

    def test_reddit_parser_adversarial_post_variations(self) -> None:
        """Test Reddit parser against edge cases: galleries, v.redd.it secure_media, deleted authors, etc."""
        fetcher = RedditFetcher(subreddit="memes")

        # 1. Post with deleted author or removed text -> must be skipped
        deleted_post = {
            "id": "del01",
            "title": "Deleted post",
            "author": "[deleted]",
            "url": "https://i.redd.it/del.jpg",
        }
        assert fetcher.parse_post_data(deleted_post) is None

        # 2. Stickied / Pinned / is_self post -> must be skipped
        stickied_post = {
            "id": "stk01",
            "title": "Sticky rules",
            "author": "moderator",
            "stickied": True,
            "url": "https://i.redd.it/rule.jpg",
        }
        assert fetcher.parse_post_data(stickied_post) is None

        # 3. Native Reddit Video via secure_media
        video_post = {
            "id": "vid01",
            "title": "Video Meme",
            "author": "creator",
            "domain": "v.redd.it",
            "is_video": True,
            "secure_media": {
                "reddit_video": {
                    "fallback_url": "https://v.redd.it/vid01/DASH_720.mp4?source=fallback"
                }
            },
        }
        v_meme = fetcher.parse_post_data(video_post)
        assert v_meme is not None
        assert v_meme.media_type == MediaType.VIDEO
        assert "DASH_720.mp4" in v_meme.media_url

        # 4. Imgur link transformation
        imgur_post = {
            "id": "img01",
            "title": "Imgur Meme",
            "author": "imgur_user",
            "domain": "imgur.com",
            "url": "https://imgur.com/gallery/aBcDeFg",
        }
        i_meme = fetcher.parse_post_data(imgur_post)
        assert i_meme is not None
        assert i_meme.media_url == "https://i.imgur.com/aBcDeFg.jpg"
        assert i_meme.media_type == MediaType.IMAGE

        # 5. .gifv to .mp4 transformation
        gifv_post = {
            "id": "gifv01",
            "title": "Gifv Meme",
            "author": "gif_user",
            "domain": "i.imgur.com",
            "url": "https://i.imgur.com/animation.gifv",
        }
        g_meme = fetcher.parse_post_data(gifv_post)
        assert g_meme is not None
        assert g_meme.media_url == "https://i.imgur.com/animation.mp4"
        assert g_meme.media_type == MediaType.VIDEO

        # 6. Reddit Gallery with media_metadata fallback
        gallery_post = {
            "id": "gal01",
            "title": "Gallery Meme",
            "author": "gal_user",
            "is_gallery": True,
            "gallery_data": {"items": []},  # Empty items list
            "media_metadata": {
                "med_meta_id_99": {
                    "status": "valid",
                    "e": "Image",
                    "m": "image/jpg",
                    "p": [{"u": "https://preview.redd.it/preview_last.jpg?width=640"}],
                }
            },
        }
        gal_meme = fetcher.parse_post_data(gallery_post)
        assert gal_meme is not None
        assert "preview_last.jpg" in gal_meme.media_url

    def test_kym_parser_rss_xml_and_trending_json_edge_cases(self) -> None:
        """Test KYM parser with edge XML elements, CDATA, missing tags, and trending JSON."""
        fetcher = KnowYourMemeFetcher(category="confirmed")

        # 1. Top-level helper function parse_kym_rss
        sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>KYM Test</title>
            <item>
              <guid>test_guid_101</guid>
              <title><![CDATA[Special Character &amp; Meme]]></title>
              <link>https://knowyourmeme.com/memes/special</link>
              <pubDate>Mon, 24 Aug 2026 10:13:17 -0400</pubDate>
              <enclosure url="https://i.kym-cdn.com/entries/icons/original/special.jpg" type="image/jpeg" />
            </item>
          </channel>
        </rss>"""

        memes = parse_kym_rss(sample_xml, category="confirmed")
        assert len(memes) == 1
        assert memes[0].title == "Special Character & Meme"
        assert memes[0].media_url == "https://i.kym-cdn.com/entries/icons/original/special.jpg"

        # 2. Corrupt XML
        assert fetcher.parse_rss_xml("<unclosed><xml>") == []

        # 3. Trending JSON parsing with string IDs and numeric field variations
        json_payload = json.dumps([
            {
                "id": "kym_trend_01",
                "title": "Trending Guy",
                "url": "https://i.kym-cdn.com/photos/images/original/000/000/999/trend.jpg",
                "score": "4500",
                "num_comments": "120",
                "created_at": "1725300000.0",
                "is_nsfw": 0,
            }
        ])
        t_memes = fetcher.parse_trending_json(json_payload)
        assert len(t_memes) == 1
        assert t_memes[0].id == "kym_trend_01"
        assert t_memes[0].score == 4500
        assert t_memes[0].num_comments == 120

    def test_parse_rfc822_date_edge_cases(self) -> None:
        """Verify parse_rfc822_date handles malformed strings without throwing."""
        assert parse_rfc822_date(None) > 0
        assert parse_rfc822_date("") > 0
        assert parse_rfc822_date("not-a-valid-date-string-12345") > 0
        # Valid RFC 822 date
        valid_ts = parse_rfc822_date("Mon, 24 Aug 2026 10:13:17 -0400")
        assert valid_ts > 1700000000.0

    def test_extract_image_from_description_edge_cases(self) -> None:
        """Verify HTML description image regex parser."""
        assert extract_image_from_description(None) is None
        assert extract_image_from_description("") is None
        assert extract_image_from_description("<p>No image here</p>") is None

        html_desc = '<p>Check this out: <img src="https://i.kym-cdn.com/photo.jpg" alt="test" /></p>'
        assert extract_image_from_description(html_desc) == "https://i.kym-cdn.com/photo.jpg"


# ==============================================================================
# SECTION 7: Background Worker Lifecycle & Fault Isolation
# ==============================================================================

class TestWorkerLifecycleAndFaultIsolation:
    """Stress background poller start/stop cycles and error recovery."""

    @pytest.mark.asyncio
    async def test_worker_rapid_start_stop_idempotence(self) -> None:
        """Calling start() and stop() repeatedly in rapid succession must be completely idempotent."""
        store = MemoryStore()
        worker = MemePollingWorker(memory_store=store, poll_interval_seconds=0.1)

        # Multiple start calls
        await worker.start()
        assert worker.is_running is True
        await worker.start()
        assert worker.is_running is True

        # Stop
        await worker.stop()
        assert worker.is_running is False
        # Multiple stop calls
        await worker.stop()
        assert worker.is_running is False

    @pytest.mark.asyncio
    async def test_worker_fault_isolation_under_exploding_fetchers(self) -> None:
        """When 2 out of 3 fetchers throw unexpected exceptions, the worker must still

        collect memes from the healthy fetcher and mark the broken fetchers as degraded.
        """
        store = MemoryStore()

        healthy_fetcher = RedditFetcher(subreddit="memes")
        healthy_fetcher.fetch_memes = AsyncMock(return_value=[
            NormalizedMeme(
                id="reddit_memes_healthy01",
                title="Healthy Meme",
                media_url="https://i.redd.it/healthy.jpg",
                media_type=MediaType.IMAGE,
                source_platform=SourcePlatform.REDDIT,
                source_community="r/memes",
                permalink="https://reddit.com/r/memes/1",
                score=1000,
                num_comments=100,
                created_at=time.time(),
                is_nsfw=False,
            )
        ])

        exploding_fetcher_1 = RedditFetcher(subreddit="dankmemes")
        exploding_fetcher_1.fetch_memes = AsyncMock(side_effect=RuntimeError("Catastrophic network socket error"))

        exploding_fetcher_2 = KnowYourMemeFetcher(category="confirmed")
        exploding_fetcher_2.fetch_memes = AsyncMock(side_effect=ValueError("Corrupt byte stream"))

        worker = MemePollingWorker(
            memory_store=store,
            fetchers=[healthy_fetcher, exploding_fetcher_1, exploding_fetcher_2],
            poll_interval_seconds=60.0,
        )

        result = await worker.poll_once()
        assert result["status"] == "ok"
        assert result["new_items"] == 1
        assert store.count() == 1
        assert store.get_by_id("reddit_memes_healthy01") is not None

        # Verify healthy fetcher has 'ok' and broken fetchers have 'degraded'
        sources = {s.name: s for s in store.get_sources_status()}
        assert sources["reddit:r/memes"].status == "ok"
        assert sources["reddit:r/dankmemes"].status == "degraded"
        assert sources["knowyourmeme:confirmed"].status == "degraded"


# ==============================================================================
# SECTION 8: Security, Rate Limiter & Configuration Hardening
# ==============================================================================

class TestSecurityAndConfigHardening:
    """Stress backoff delay calculation, user agent generation, and rate limiter concurrency."""

    @pytest.mark.asyncio
    async def test_polite_rate_limiter_concurrency(self) -> None:
        """PoliteRateLimiter properly serializes rapid requests to the same domain."""
        limiter = PoliteRateLimiter(min_interval_seconds=0.05)
        start = time.monotonic()

        async def make_request(idx: int) -> int:
            await limiter.throttle("api.reddit.com")
            return idx

        results = await asyncio.gather(*[make_request(i) for i in range(4)])
        elapsed = time.monotonic() - start

        assert len(results) == 4
        # 4 requests with 0.05s intervals should take at least ~0.15s
        assert elapsed >= 0.10

    def test_calculate_backoff_delay_header_permutations(self) -> None:
        """Verify backoff calculation with various HTTP headers."""
        # 1. Retry-After header as integer/float
        d1 = calculate_backoff_delay(0, response_headers={"Retry-After": "5"})
        assert d1 == 5.0

        # 2. Retry-After exceeding max_backoff -> clamped to max_backoff
        d2 = calculate_backoff_delay(0, response_headers={"Retry-After": "3600"}, max_backoff=16.0)
        assert d2 == 16.0

        # 3. x-ratelimit-reset header
        d3 = calculate_backoff_delay(0, response_headers={"x-ratelimit-reset": "3.5"})
        assert d3 == 3.5

        # 4. Invalid Retry-After header string falls back to exponential jitter
        d4 = calculate_backoff_delay(0, response_headers={"Retry-After": "invalid_date_format"})
        assert 1.0 <= d4 <= 2.0

        # 5. Negative attempt index is handled safely
        d5 = calculate_backoff_delay(-5)
        assert 1.0 <= d5 <= 2.0

    def test_config_parse_list_fields_permutations(self) -> None:
        """Verify Settings list validator parses JSON, comma strings, and native lists."""
        # Native list
        assert Settings.parse_list_fields(["memes", "dankmemes"]) == ["memes", "dankmemes"]

        # Valid JSON array string
        assert Settings.parse_list_fields('["memes", "me_irl"]') == ["memes", "me_irl"]

        # Comma-separated string
        assert Settings.parse_list_fields("memes, dankmemes , wholesome") == ["memes", "dankmemes", "wholesome"]

        # Malformed JSON with bracket fallback
        assert Settings.parse_list_fields("[memes, dankmemes") == ["[memes", "dankmemes"]


# ==============================================================================
# SECTION 9: REST API Endpoints Pagination & Validation Hardening
# ==============================================================================

class TestApiV1AdversarialPermutations:
    """Stress FastAPI endpoints with boundary parameters and error permutations."""

    @pytest.mark.asyncio
    async def test_api_latest_boundary_pagination(self, async_client: httpx.AsyncClient) -> None:
        """Test boundary limits (1, 100) and excessive offsets."""
        # Limit = 1
        resp_lim1 = await async_client.get("/api/v1/memes/latest?limit=1&offset=0")
        assert resp_lim1.status_code == 200
        data_lim1 = resp_lim1.json()
        assert len(data_lim1["items"]) == 1
        assert data_lim1["has_more"] is True

        # Offset beyond total
        resp_huge_offset = await async_client.get("/api/v1/memes/latest?limit=20&offset=50000")
        assert resp_huge_offset.status_code == 200
        data_huge = resp_huge_offset.json()
        assert len(data_huge["items"]) == 0
        assert data_huge["has_more"] is False

    @pytest.mark.asyncio
    async def test_api_validation_errors_422(self, async_client: httpx.AsyncClient) -> None:
        """Invalid query parameters return 422 Unprocessable Entity."""
        # Limit < 1
        r1 = await async_client.get("/api/v1/memes/latest?limit=0")
        assert r1.status_code == 422

        # Limit > 100
        r2 = await async_client.get("/api/v1/memes/latest?limit=101")
        assert r2.status_code == 422

        # Offset < 0
        r3 = await async_client.get("/api/v1/memes/latest?offset=-5")
        assert r3.status_code == 422

    @pytest.mark.asyncio
    async def test_api_random_meme_404_on_empty_filter(self, async_client: httpx.AsyncClient) -> None:
        """Requesting a random meme with an unmatched source returns 404."""
        resp = await async_client.get("/api/v1/memes/random?source=nonexistent_subreddit_404")
        assert resp.status_code == 404
        assert "No memes found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_api_root_and_health_endpoints(self, async_client: httpx.AsyncClient) -> None:
        """Verify root / and /health and /api/v1/sources endpoints."""
        # Root index
        resp_root = await async_client.get("/")
        assert resp_root.status_code == 200
        assert "docs_url" in resp_root.json()

        # Health endpoint
        resp_health = await async_client.get("/health")
        assert resp_health.status_code == 200
        health_data = resp_health.json()
        assert health_data["status"] in ("ok", "degraded", "unhealthy")
        assert health_data["total_memes"] >= 0

        # Sources endpoint
        resp_sources = await async_client.get("/api/v1/sources")
        assert resp_sources.status_code == 200
        sources = resp_sources.json()
        assert isinstance(sources, list)
        assert len(sources) > 0
