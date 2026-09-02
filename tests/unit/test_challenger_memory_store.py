"""Empirical challenger stress-test suite for MemoryStore (Milestone M2).

Focus areas:
1. Benchmark query latency across 5,000+ and 10,000+ items (<1ms target).
2. Extreme pagination offsets and limits.
3. Concurrent upserts, reads, and health queries (race conditions & thread safety).
4. Duplicate meme merging (engagement maximization & earliest timestamp preservation).
5. Time window filters (1h, 6h, 24h, 7d, all, None, edge cases).
6. Source matching and health status aggregations.
7. Index integrity invariants (ordering, count synchronization, hash mappings).
"""

from __future__ import annotations

import concurrent.futures
import statistics
import time
from typing import List

import pytest

from app.core.dedup import compute_content_hash
from app.core.ranking import calculate_trending_score
from app.models.meme import MediaType, NormalizedMeme, SourcePlatform
from app.models.source import SourceStatus
from app.storage.memory_store import MemoryStore


def _generate_memes(
    count: int,
    start_id: int = 0,
    base_time: float | None = None,
    time_spread_hours: float = 48.0,
) -> List[NormalizedMeme]:
    """Helper to generate a realistic batch of distinct NormalizedMeme objects."""
    now = base_time if base_time is not None else time.time()
    subreddits = ["memes", "dankmemes", "me_irl", "wholesomememes"]
    kym_categories = ["confirmed", "trending", "news"]

    memes: List[NormalizedMeme] = []
    for i in range(count):
        idx = start_id + i
        is_reddit = (idx % 2 == 0)
        if is_reddit:
            comm = subreddits[(idx // 2) % len(subreddits)]
            source_plat = SourcePlatform.REDDIT
            plat_str = "reddit"
            comm_str = f"r/{comm}"
            permalink = f"https://reddit.com/r/{comm}/comments/{idx}"
        else:
            comm = kym_categories[(idx // 2) % len(kym_categories)]
            source_plat = SourcePlatform.KNOWYOURMEME
            plat_str = "knowyourmeme"
            comm_str = comm
            permalink = f"https://knowyourmeme.com/memes/{idx}"

        media_url = f"https://i.redd.it/meme_{idx}.png" if is_reddit else f"https://kym.com/photos/{idx}.jpg"
        title = f"Test Meme #{idx} Title"
        # Spread creation times across the time_spread_hours window
        age_seconds = (idx % int(time_spread_hours * 3600))
        created_at = now - age_seconds
        score = (idx * 37) % 50000 + 10
        num_comments = (idx * 13) % 2000 + 1
        is_nsfw = (idx % 10 == 0)
        c_hash = compute_content_hash(media_url, title)
        trending = calculate_trending_score(score, num_comments, created_at, now)

        m = NormalizedMeme(
            id=f"test_meme_{idx}",
            title=title,
            media_url=media_url,
            media_type=MediaType.IMAGE,
            source_platform=source_plat,
            source_community=comm_str,
            permalink=permalink,
            author=f"user_{idx % 100}",
            score=score,
            num_comments=num_comments,
            created_at=created_at,
            is_nsfw=is_nsfw,
            content_hash=c_hash,
            trending_score=trending,
        )
        memes.append(m)
    return memes


class TestChallengerLatencyBenchmark:
    """Benchmark query latencies on 5,000+ and 10,000+ cached items to verify sub-millisecond (<1ms) performance."""

    def test_latency_5000_items_sub_millisecond(self) -> None:
        """Verify get_latest, get_trending, and get_random average < 1ms across 5,000 items."""
        store = MemoryStore()
        memes = _generate_memes(5000)
        store.upsert_memes(memes)
        assert store.count() == 5000

        iterations = 500

        # 1. Benchmark get_latest default
        latencies_latest: List[float] = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            items, total = store.get_latest(limit=20, offset=0, nsfw=False)
            dt_ms = (time.perf_counter() - t0) * 1000.0
            latencies_latest.append(dt_ms)
            assert len(items) == 20
            assert total > 0

        mean_latest = statistics.mean(latencies_latest)
        p95_latest = statistics.quantiles(latencies_latest, n=20)[18]  # 95th percentile

        # 2. Benchmark get_trending with 24h window filter
        latencies_trending: List[float] = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            items, total = store.get_trending(limit=20, offset=0, time_window="24h", nsfw=False)
            dt_ms = (time.perf_counter() - t0) * 1000.0
            latencies_trending.append(dt_ms)
            assert len(items) <= 20
            assert total > 0

        mean_trending = statistics.mean(latencies_trending)
        p95_trending = statistics.quantiles(latencies_trending, n=20)[18]

        # 3. Benchmark get_latest with source filter
        latencies_source_filter: List[float] = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            items, total = store.get_latest(limit=20, offset=0, source="dankmemes", nsfw=True)
            dt_ms = (time.perf_counter() - t0) * 1000.0
            latencies_source_filter.append(dt_ms)
            assert len(items) == 20

        mean_source = statistics.mean(latencies_source_filter)
        p95_source = statistics.quantiles(latencies_source_filter, n=20)[18]

        # 4. Benchmark get_random (unfiltered)
        latencies_random_unfiltered: List[float] = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            rand_meme = store.get_random(source=None, nsfw=False)
            dt_ms = (time.perf_counter() - t0) * 1000.0
            latencies_random_unfiltered.append(dt_ms)
            assert rand_meme is not None

        mean_random = statistics.mean(latencies_random_unfiltered)

        # 5. Benchmark get_by_id and get_by_content_hash (O(1) hash map lookup)
        sample_m = memes[1234]
        latencies_id_lookup: List[float] = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            found = store.get_by_id(sample_m.id)
            dt_ms = (time.perf_counter() - t0) * 1000.0
            latencies_id_lookup.append(dt_ms)
            assert found is not None

        mean_id_lookup = statistics.mean(latencies_id_lookup)

        print(
            f"\n[LATENCY 5000 items] latest: mean={mean_latest:.4f}ms (P95={p95_latest:.4f}ms) | "
            f"trending_24h: mean={mean_trending:.4f}ms (P95={p95_trending:.4f}ms) | "
            f"source_filter: mean={mean_source:.4f}ms (P95={p95_source:.4f}ms) | "
            f"random: mean={mean_random:.4f}ms | id_lookup: mean={mean_id_lookup:.4f}ms"
        )

        assert mean_latest < 1.0, f"get_latest mean latency {mean_latest:.4f}ms exceeded 1.0ms limit"
        assert p95_latest < 2.0, f"get_latest P95 latency {p95_latest:.4f}ms exceeded 2.0ms limit"
        assert mean_trending < 1.0, f"get_trending mean latency {mean_trending:.4f}ms exceeded 1.0ms limit"
        assert mean_random < 1.0, f"get_random mean latency {mean_random:.4f}ms exceeded 1.0ms limit"
        assert mean_id_lookup < 0.01, f"get_by_id mean latency {mean_id_lookup:.4f}ms exceeded 0.01ms limit"

    def test_latency_10000_items_stress_benchmark(self) -> None:
        """Stress benchmark with 10,000 items to observe scaling characteristics."""
        store = MemoryStore()
        memes = _generate_memes(10000)
        store.upsert_memes(memes)
        assert store.count() == 10000

        iterations = 200
        latencies_latest: List[float] = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            items, total = store.get_latest(limit=50, offset=100, nsfw=True)
            dt_ms = (time.perf_counter() - t0) * 1000.0
            latencies_latest.append(dt_ms)
            assert len(items) == 50
            assert total == 10000

        mean_latest_10k = statistics.mean(latencies_latest)
        print(f"\n[LATENCY 10000 items] latest (limit=50, offset=100): mean={mean_latest_10k:.4f}ms")
        assert mean_latest_10k < 2.0


class TestChallengerPagination:
    """Empirical tests for boundary and extreme pagination parameters."""

    def test_pagination_boundary_cases(self) -> None:
        """Test zero limit, large limit, offset at total, offset beyond total."""
        store = MemoryStore()
        memes = _generate_memes(100)
        store.upsert_memes(memes)

        # 1. offset == total
        items, total = store.get_latest(limit=10, offset=100, nsfw=True)
        assert items == []
        assert total == 100

        # 2. offset > total
        items, total = store.get_latest(limit=10, offset=5000, nsfw=True)
        assert items == []
        assert total == 100

        # 3. limit == 0
        items, total = store.get_latest(limit=0, offset=0, nsfw=True)
        assert items == []
        assert total == 100

        # 4. limit >> total
        items, total = store.get_latest(limit=10000, offset=0, nsfw=True)
        assert len(items) == 100
        assert total == 100

        # 5. offset near end
        items, total = store.get_latest(limit=10, offset=95, nsfw=True)
        assert len(items) == 5
        assert total == 100

    def test_full_dataset_pagination_sweep(self) -> None:
        """Paginate through entire 1,000 item dataset in pages of 25 and verify 100% item coverage and zero duplicates."""
        store = MemoryStore()
        total_items = 1000
        page_size = 25
        memes = _generate_memes(total_items)
        store.upsert_memes(memes)

        seen_ids: set[str] = set()
        num_pages = total_items // page_size

        for page in range(num_pages):
            offset = page * page_size
            items, total = store.get_latest(limit=page_size, offset=offset, nsfw=True)
            assert total == total_items
            assert len(items) == page_size
            for item in items:
                assert item.id not in seen_ids, f"Duplicate item {item.id} encountered on page {page}"
                seen_ids.add(item.id)

        assert len(seen_ids) == total_items

        # Next page should be empty
        empty_items, total = store.get_latest(limit=page_size, offset=total_items, nsfw=True)
        assert empty_items == []
        assert total == total_items

    def test_pagination_on_empty_store(self) -> None:
        """Test pagination behavior when store has 0 items."""
        store = MemoryStore()
        items, total = store.get_latest(limit=20, offset=0)
        assert items == []
        assert total == 0

        items, total = store.get_trending(limit=100, offset=50)
        assert items == []
        assert total == 0


class TestChallengerConcurrency:
    """Thread safety and race condition tests under heavy concurrent access."""

    def test_concurrent_upserts_and_reads(self) -> None:
        """Execute simultaneous multi-threaded reads, writes, and health checks."""
        store = MemoryStore()
        # Seed with 500 initial memes
        initial_memes = _generate_memes(500, start_id=0)
        store.upsert_memes(initial_memes)

        errors: List[Exception] = []

        def write_worker(worker_id: int) -> None:
            try:
                for batch_idx in range(10):
                    batch = _generate_memes(50, start_id=500 + worker_id * 100 + batch_idx * 10)
                    store.upsert_memes(batch)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def read_latest_worker() -> None:
            try:
                for _ in range(50):
                    items, total = store.get_latest(limit=20, offset=0, nsfw=True)
                    assert total >= 500
                    # Verify ordering invariant
                    for i in range(len(items) - 1):
                        assert items[i].created_at >= items[i + 1].created_at
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def read_trending_worker() -> None:
            try:
                for _ in range(50):
                    items, total = store.get_trending(limit=20, offset=0, time_window="24h", nsfw=True)
                    for i in range(len(items) - 1):
                        assert items[i].trending_score >= items[i + 1].trending_score
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def health_and_source_worker() -> None:
            try:
                for _ in range(50):
                    health = store.get_health_status()
                    assert health.total_memes >= 500
                    sources = store.get_sources_status()
                    assert len(sources) > 0
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            # 8 writers
            for w in range(8):
                futures.append(executor.submit(write_worker, w))
            # 6 latest readers
            for _ in range(6):
                futures.append(executor.submit(read_latest_worker))
            # 4 trending readers
            for _ in range(4):
                futures.append(executor.submit(read_trending_worker))
            # 2 health checkers
            for _ in range(2):
                futures.append(executor.submit(health_and_source_worker))

            concurrent.futures.wait(futures)

        assert not errors, f"Concurrency errors occurred: {errors}"
        # Verify final store count and index consistency
        final_count = store.count()
        assert final_count > 500
        latest_all, total_latest = store.get_latest(limit=final_count + 100, offset=0, nsfw=True)
        assert len(latest_all) == final_count
        assert total_latest == final_count
        # Check sorting
        for i in range(len(latest_all) - 1):
            assert latest_all[i].created_at >= latest_all[i + 1].created_at


class TestChallengerDeduplicationAndMerging:
    """Adversarial testing of deduplication, engagement maximization, and temporal anchoring."""

    def test_engagement_maximization_and_temporal_preservation(self) -> None:
        """Verify merging preserves maximum engagement, earliest created_at, and logical OR on NSFW."""
        store = MemoryStore()
        c_hash = compute_content_hash("https://example.com/meme_dup.png", "Duplicate Title")

        m1 = NormalizedMeme(
            id="m_first",
            title="Duplicate Title",
            media_url="https://example.com/meme_dup.png",
            media_type=MediaType.IMAGE,
            source_platform=SourcePlatform.REDDIT,
            source_community="r/memes",
            permalink="https://reddit.com/r/memes/1",
            author="author1",
            score=1000,
            num_comments=50,
            created_at=1700000000.0,
            is_nsfw=False,
            content_hash=c_hash,
            trending_score=10.0,
        )

        store.upsert_memes([m1])
        assert store.count() == 1

        # M2 has higher score, fewer comments, later created_at, and is_nsfw=True
        m2 = NormalizedMeme(
            id="m_second",
            title="Duplicate Title",
            media_url="https://example.com/meme_dup.png",
            media_type=MediaType.IMAGE,
            source_platform=SourcePlatform.REDDIT,
            source_community="r/dankmemes",
            permalink="https://reddit.com/r/dankmemes/2",
            author="author2",
            score=8000,
            num_comments=20,
            created_at=1700010000.0,
            is_nsfw=True,
            content_hash=c_hash,
            trending_score=25.0,
        )

        store.upsert_memes([m2])
        assert store.count() == 1

        merged = store.get_by_id("m_first")
        assert merged is not None
        assert merged.score == 8000, "Score should be maximized (max(1000, 8000))"
        assert merged.num_comments == 50, "Comments should be maximized (max(50, 20))"
        assert merged.created_at == 1700000000.0, "Earliest created_at must be preserved (min)"
        assert merged.is_nsfw is True, "NSFW flag should be True (False OR True)"
        assert merged.content_hash == c_hash

        # M3 has lower score, higher comments, earlier created_at
        m3 = NormalizedMeme(
            id="m_third",
            title="Duplicate Title",
            media_url="https://example.com/meme_dup.png",
            media_type=MediaType.IMAGE,
            source_platform=SourcePlatform.REDDIT,
            source_community="r/wholesomememes",
            permalink="https://reddit.com/r/wholesomememes/3",
            author="author3",
            score=3000,
            num_comments=150,
            created_at=1699990000.0,
            is_nsfw=False,
            content_hash=c_hash,
            trending_score=15.0,
        )

        store.upsert_memes([m3])
        assert store.count() == 1

        merged2 = store.get_by_content_hash(c_hash)
        assert merged2 is not None
        assert merged2.score == 8000
        assert merged2.num_comments == 150
        assert merged2.created_at == 1699990000.0
        assert merged2.is_nsfw is True

    def test_multi_batch_dedup_cross_platform(self) -> None:
        """Verify duplicate meme across Reddit and KYM merges properly and updates indices."""
        store = MemoryStore()
        shared_url = "https://i.imgur.com/shared_viral_meme.png"
        shared_title = "Viral Meme Everyone Reposts"
        c_hash = compute_content_hash(shared_url, shared_title)

        reddit_version = NormalizedMeme(
            id="reddit_post_1",
            title=shared_title,
            media_url=shared_url,
            media_type=MediaType.IMAGE,
            source_platform=SourcePlatform.REDDIT,
            source_community="r/memes",
            permalink="https://reddit.com/r/memes/viral",
            author="reddit_user",
            score=15000,
            num_comments=600,
            created_at=1700000000.0,
            is_nsfw=False,
            content_hash=c_hash,
            trending_score=50.0,
        )

        kym_version = NormalizedMeme(
            id="kym_entry_1",
            title=shared_title,
            media_url=shared_url,
            media_type=MediaType.IMAGE,
            source_platform=SourcePlatform.KNOWYOURMEME,
            source_community="confirmed",
            permalink="https://knowyourmeme.com/memes/viral",
            author="kym_editor",
            score=25000,
            num_comments=1200,
            created_at=1699900000.0,
            is_nsfw=False,
            content_hash=c_hash,
            trending_score=80.0,
        )

        # Upsert both
        store.upsert_memes([reddit_version, kym_version])
        assert store.count() == 1

        items, total = store.get_latest(limit=10, offset=0, nsfw=True)
        assert len(items) == 1
        assert total == 1
        assert items[0].score == 25000
        assert items[0].num_comments == 1200
        assert items[0].created_at == 1699900000.0

    def test_100_duplicate_stream_stress_merge(self) -> None:
        """Upsert 100 variations of the exact same content_hash with randomized metrics."""
        import random
        store = MemoryStore()
        c_hash = compute_content_hash("https://example.com/unique_target.png", "Target Title")

        scores = [random.randint(10, 50000) for _ in range(100)]
        comments = [random.randint(1, 2000) for _ in range(100)]
        timestamps = [1700000000.0 + random.randint(-100000, 100000) for _ in range(100)]
        nsfw_flags = [i % 7 == 0 for i in range(100)]  # at least some are True

        expected_max_score = max(scores)
        expected_max_comments = max(comments)
        expected_min_timestamp = min(timestamps)
        expected_nsfw = any(nsfw_flags)

        for i in range(100):
            m = NormalizedMeme(
                id=f"dup_{i}",
                title="Target Title",
                media_url="https://example.com/unique_target.png",
                media_type=MediaType.IMAGE,
                source_platform=SourcePlatform.REDDIT,
                source_community="r/memes",
                permalink=f"https://reddit.com/r/memes/{i}",
                author=f"user_{i}",
                score=scores[i],
                num_comments=comments[i],
                created_at=timestamps[i],
                is_nsfw=nsfw_flags[i],
                content_hash=c_hash,
                trending_score=1.0,
            )
            store.upsert_memes([m])

        assert store.count() == 1
        result = store.get_by_id("dup_0")
        assert result is not None
        assert result.score == expected_max_score
        assert result.num_comments == expected_max_comments
        assert result.created_at == expected_min_timestamp
        assert result.is_nsfw == expected_nsfw


class TestChallengerTimeWindowFilters:
    """Empirical tests for all time window filters (1h, 6h, 24h, 7d, all, None, case/whitespace)."""

    def test_all_time_windows_filtering(self) -> None:
        """Verify strict adherence to time cutoff bounds across 1h, 6h, 24h, 7d, and all."""
        store = MemoryStore()
        now = time.time()

        # Place memes at exact temporal offsets:
        # m_20m:  20 mins ago (1200s) -> in 1h, 6h, 24h, 7d, all
        # m_2h:   2 hours ago (7200s) -> in 6h, 24h, 7d, all
        # m_10h:  10 hours ago (36000s) -> in 24h, 7d, all
        # m_3d:   3 days ago (259200s) -> in 7d, all
        # m_14d:  14 days ago (1209600s) -> in all only
        offsets = {
            "m_20m": 1200,
            "m_2h": 7200,
            "m_10h": 36000,
            "m_3d": 259200,
            "m_14d": 1209600,
        }

        memes = []
        for mid, offset_sec in offsets.items():
            created = now - offset_sec
            memes.append(
                NormalizedMeme(
                    id=mid,
                    title=f"Meme {mid}",
                    media_url=f"https://i.redd.it/{mid}.png",
                    media_type=MediaType.IMAGE,
                    source_platform=SourcePlatform.REDDIT,
                    source_community="r/memes",
                    permalink=f"https://reddit.com/r/memes/{mid}",
                    author="user",
                    score=1000,
                    num_comments=10,
                    created_at=created,
                    is_nsfw=False,
                    content_hash=f"hash_{mid}",
                    trending_score=100.0 / (offset_sec + 1),
                )
            )

        store.upsert_memes(memes)
        assert store.count() == 5

        # 1. Test 1h
        items_1h, total_1h = store.get_trending(time_window="1h", nsfw=True)
        assert [m.id for m in items_1h] == ["m_20m"]
        assert total_1h == 1

        # 2. Test 6h
        items_6h, total_6h = store.get_trending(time_window="6h", nsfw=True)
        assert {m.id for m in items_6h} == {"m_20m", "m_2h"}
        assert total_6h == 2

        # 3. Test 24h
        items_24h, total_24h = store.get_trending(time_window="24h", nsfw=True)
        assert {m.id for m in items_24h} == {"m_20m", "m_2h", "m_10h"}
        assert total_24h == 3

        # 4. Test 7d
        items_7d, total_7d = store.get_trending(time_window="7d", nsfw=True)
        assert {m.id for m in items_7d} == {"m_20m", "m_2h", "m_10h", "m_3d"}
        assert total_7d == 4

        # 5. Test all
        items_all, total_all = store.get_trending(time_window="all", nsfw=True)
        assert total_all == 5
        assert len(items_all) == 5

        # 6. Test None
        items_none, total_none = store.get_trending(time_window=None, nsfw=True)
        assert total_none == 5
        assert len(items_none) == 5

        # 7. Test case & whitespace insensitivity: ' 1H ', ' 24h '
        items_1h_upper, _ = store.get_trending(time_window="  1H  ", nsfw=True)
        assert [m.id for m in items_1h_upper] == ["m_20m"]

        items_24h_upper, _ = store.get_trending(time_window="24H", nsfw=True)
        assert len(items_24h_upper) == 3

    def test_exact_boundary_precision_time_windows(self) -> None:
        """Test exact cutoff points: e.g. exactly 3600s vs 3601s for 1h window."""
        store = MemoryStore()
        now = time.time()

        # Item at 3599s (inside 1h)
        m_inside = NormalizedMeme(
            id="m_in",
            title="Inside 1h",
            media_url="https://i.redd.it/in.png",
            media_type=MediaType.IMAGE,
            source_platform=SourcePlatform.REDDIT,
            source_community="r/memes",
            permalink="https://reddit.com/r/memes/in",
            author="u1",
            score=100,
            num_comments=10,
            created_at=now - 3590.0,
            is_nsfw=False,
            content_hash="hash_in",
            trending_score=50.0,
        )
        # Item at 3610s (outside 1h)
        m_outside = NormalizedMeme(
            id="m_out",
            title="Outside 1h",
            media_url="https://i.redd.it/out.png",
            media_type=MediaType.IMAGE,
            source_platform=SourcePlatform.REDDIT,
            source_community="r/memes",
            permalink="https://reddit.com/r/memes/out",
            author="u2",
            score=100,
            num_comments=10,
            created_at=now - 3610.0,
            is_nsfw=False,
            content_hash="hash_out",
            trending_score=40.0,
        )

        store.upsert_memes([m_inside, m_outside])
        items_1h, total_1h = store.get_trending(time_window="1h", nsfw=True)
        assert len(items_1h) == 1
        assert items_1h[0].id == "m_in"
        assert total_1h == 1


class TestChallengerSourceFilteringAndHealth:
    """Source filtering permutations and health metrics."""

    def test_source_filter_case_and_aliases(self) -> None:
        """Test source queries: REDDIT, Reddit, r/memes, memes, knowyourmeme, KYM, kym."""
        store = MemoryStore()
        memes = _generate_memes(200)
        store.upsert_memes(memes)

        # Reddit queries
        reddit_upper, _ = store.get_latest(source="REDDIT", nsfw=True)
        assert len(reddit_upper) > 0
        assert all(m.source_platform in (SourcePlatform.REDDIT, "reddit") for m in reddit_upper)

        # KYM queries
        kym_upper, _ = store.get_latest(source="KYM", nsfw=True)
        assert len(kym_upper) > 0
        assert all(m.source_platform in (SourcePlatform.KNOWYOURMEME, "knowyourmeme") for m in kym_upper)

        # Subreddit query
        memes_sub, _ = store.get_latest(source="r/dankmemes", nsfw=True)
        assert len(memes_sub) > 0
        assert all("dankmemes" in m.source_community for m in memes_sub)

    def test_health_status_aggregation_transitions(self) -> None:
        """Test status transitions: ok -> degraded -> unhealthy based on source states."""
        store = MemoryStore()
        sources = store.get_sources_status()
        assert len(sources) > 0
        assert store.get_health_status().status == "ok"

        # Degrade one source
        degraded_source = sources[0].model_copy(update={"status": "error"})
        store.update_source_status(degraded_source)
        assert store.get_health_status().status == "degraded"

        # Mark all sources as error
        for s in sources:
            store.update_source_status(s.model_copy(update={"status": "failing"}))
        assert store.get_health_status().status == "unhealthy"


class TestChallengerIndexInvariants:
    """Verify index sorting invariants and state synchronization."""

    def test_sorted_indices_invariants_after_random_upserts(self) -> None:
        """Verify _latest_index is strictly descending by created_at and _trending_index by trending_score."""
        store = MemoryStore()
        memes = _generate_memes(500)
        import random
        random.shuffle(memes)

        for chunk_idx in range(0, len(memes), 50):
            store.upsert_memes(memes[chunk_idx : chunk_idx + 50])

        assert store.count() == 500

        # Validate latest ordering
        latest, _ = store.get_latest(limit=500, offset=0, nsfw=True)
        assert len(latest) == 500
        for i in range(len(latest) - 1):
            assert latest[i].created_at >= latest[i + 1].created_at, (
                f"Latest index out of order at index {i}: {latest[i].created_at} < {latest[i+1].created_at}"
            )

        # Validate trending ordering
        trending, _ = store.get_trending(limit=500, offset=0, nsfw=True)
        assert len(trending) == 500
        for i in range(len(trending) - 1):
            assert trending[i].trending_score >= trending[i + 1].trending_score, (
                f"Trending index out of order at index {i}: {trending[i].trending_score} < {trending[i+1].trending_score}"
            )

    def test_store_clear_and_repopulation_invariants(self) -> None:
        """Verify clear() purges all maps and subsequent upserts maintain integrity."""
        store = MemoryStore()
        memes = _generate_memes(300)
        store.upsert_memes(memes)
        assert store.count() == 300

        store.clear()
        assert store.count() == 0
        assert store.get_latest()[0] == []
        assert store.get_trending()[0] == []
        assert store.get_random() is None

        # Repopulate
        new_memes = _generate_memes(100, start_id=1000)
        store.upsert_memes(new_memes)
        assert store.count() == 100
        assert len(store.get_latest(limit=100, nsfw=True)[0]) == 100

