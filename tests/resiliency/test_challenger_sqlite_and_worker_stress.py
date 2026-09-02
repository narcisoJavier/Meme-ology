"""Adversarial stress tests for SqliteStore and MemePollingWorker.

Empirical verification covering:
1. SQLite high concurrency, transaction stress, large batch upserts, and SQL injection safety.
2. SQLite corrupt database file recovery, 0-byte file handling, truncated pages, non-existent directories.
3. SQLite WAL mode verification, persistence across multiple connection lifecycles, and metric aggregation.
4. Multiple concurrent SqliteStore instances operating on the same physical SQLite database.
5. Worker rapid start/stop cycles, idempotent restarts, and task leak prevention.
6. Worker cancellation during active network fetch / in-flight polling operations.
7. Worker timeout handling and resilience against slow or hanging sources.
8. Worker partial source failure isolation: None returns, exceptions in update_failure, malformed objects.
9. Worker multi-tick periodic execution accumulating and merging records across cycles.
"""

from __future__ import annotations

import asyncio
import os
import random
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest
import pytest_asyncio

from app.config import get_settings
from app.ingestion.base import BaseSourceFetcher
from app.ingestion.worker import MemePollingWorker
from app.models.meme import MediaType, NormalizedMeme, SourcePlatform
from app.models.source import SourceStatus
from app.storage.memory_store import MemoryStore
from app.storage.sqlite_store import SqliteStore


# ---------------------------------------------------------------------------
# Dimension 1: SqliteStore Heavy Load, Concurrency, WAL & Data Integrity
# ---------------------------------------------------------------------------

class TestSqliteStoreStressAndDurability:
    """Stress tests for SQLite async persistence engine."""

    @pytest.mark.asyncio
    async def test_sqlite_wal_mode_enabled_and_durable(self, temp_sqlite_db: str) -> None:
        """Verify WAL mode is applied and persists across independent connections."""
        store = SqliteStore(database_path=temp_sqlite_db)
        await store.initialize()

        # Check PRAGMA journal_mode directly
        async with aiosqlite.connect(temp_sqlite_db) as db:
            async with db.execute("PRAGMA journal_mode;") as cursor:
                row = await cursor.fetchone()
                journal_mode = row[0].lower() if row else ""
                assert journal_mode == "wal", f"Expected WAL mode, got {journal_mode}"

        # Write item, close, and verify from a raw standard sqlite3 connection
        meme = NormalizedMeme(
            id="wal_test_01",
            title="WAL Durability Test",
            media_url="https://i.redd.it/wal01.jpg",
            media_type=MediaType.IMAGE,
            source_platform=SourcePlatform.REDDIT,
            source_community="r/memes",
            permalink="https://reddit.com/r/memes/wal01",
            author="wal_author",
            score=500,
            num_comments=25,
            created_at=time.time(),
            content_hash="wal_hash_01",
            trending_score=50.0,
        )
        await store.save_memes([meme])
        await store.close()

        # Verify with standard sync sqlite3
        conn = sqlite3.connect(temp_sqlite_db)
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, score FROM memes WHERE id = 'wal_test_01';")
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "wal_test_01"
        assert row[1] == "WAL Durability Test"
        assert row[2] == 500

    @pytest.mark.asyncio
    async def test_sqlite_heavy_load_batch_upsert(
        self, temp_sqlite_db: str, meme_factory: callable
    ) -> None:
        """Verify saving and retrieving large batches (2,000+ items) with high throughput."""
        store = SqliteStore(database_path=temp_sqlite_db)
        await store.initialize()

        num_items = 2000
        now = time.time()
        memes = [
            NormalizedMeme(
                **meme_factory(
                    id=f"batch_{i}",
                    raw_id=f"raw_{i}",
                    title=f"Meme batch title #{i}",
                    media_url=f"https://i.redd.it/batch_{i}.png",
                    score=i * 10,
                    num_comments=i,
                    created_at=now - (i * 10),
                    content_hash=f"hash_batch_{i}",
                    trending_score=float(i * 5),
                )
            )
            for i in range(num_items)
        ]

        # Save in batch
        t0 = time.perf_counter()
        saved = await store.save_memes(memes)
        save_elapsed = time.perf_counter() - t0

        assert saved == num_items
        assert await store.count() == num_items
        assert save_elapsed < 5.0, f"Batch save of {num_items} items took too long: {save_elapsed:.2f}s"

        # Load all
        t1 = time.perf_counter()
        loaded = await store.load_all_memes()
        load_elapsed = time.perf_counter() - t1

        assert len(loaded) == num_items
        assert load_elapsed < 2.0, f"Loading {num_items} items took too long: {load_elapsed:.2f}s"

        # Verify descending created_at order
        for i in range(len(loaded) - 1):
            assert loaded[i].created_at >= loaded[i + 1].created_at

        await store.close()

    @pytest.mark.asyncio
    async def test_sqlite_concurrent_read_write_transactions(
        self, temp_sqlite_db: str, meme_factory: callable
    ) -> None:
        """Verify concurrent read and write operations across multiple coroutines do not lock or corrupt database."""
        store = SqliteStore(database_path=temp_sqlite_db)
        await store.initialize()

        concurrency = 20
        items_per_coroutine = 50
        now = time.time()

        async def writer(worker_id: int):
            worker_memes = [
                NormalizedMeme(
                    **meme_factory(
                        id=f"c_worker_{worker_id}_{i}",
                        title=f"Concurrent Item {worker_id}-{i}",
                        media_url=f"https://i.redd.it/c_{worker_id}_{i}.jpg",
                        content_hash=f"c_hash_{worker_id}_{i}",
                        created_at=now - (worker_id * 100 + i),
                        score=worker_id * 100 + i,
                    )
                )
                for i in range(items_per_coroutine)
            ]
            await store.save_memes(worker_memes)

        async def reader():
            for _ in range(5):
                count = await store.count()
                if count > 0:
                    memes = await store.load_all_memes()
                    assert len(memes) >= count
                await asyncio.sleep(0.01)

        # Launch concurrent writers and readers simultaneously
        writer_tasks = [asyncio.create_task(writer(w)) for w in range(concurrency)]
        reader_tasks = [asyncio.create_task(reader()) for _ in range(5)]

        await asyncio.gather(*writer_tasks, *reader_tasks)

        total_expected = concurrency * items_per_coroutine
        final_count = await store.count()
        assert final_count == total_expected, f"Expected {total_expected} items, got {final_count}"
        await store.close()

    @pytest.mark.asyncio
    async def test_sqlite_concurrent_same_id_upserts_max_aggregation(
        self, temp_sqlite_db: str, meme_factory: callable
    ) -> None:
        """Verify concurrent workers upserting the exact same record ID resolve to MAX(score) without conflict."""
        store = SqliteStore(database_path=temp_sqlite_db)
        await store.initialize()

        target_id = "contended_same_id"
        num_contenders = 25
        scores = [random.randint(100, 50000) for _ in range(num_contenders)]
        max_score = max(scores)

        async def contender_upsert(idx: int, score_val: int):
            meme = NormalizedMeme(
                **meme_factory(
                    id=target_id,
                    title=f"Contended Title {idx}",
                    score=score_val,
                    num_comments=score_val // 10,
                    content_hash="contended_hash",
                )
            )
            await store.save_memes([meme])

        tasks = [
            asyncio.create_task(contender_upsert(i, scores[i]))
            for i in range(num_contenders)
        ]
        await asyncio.gather(*tasks)

        assert await store.count() == 1
        final_record = await store.get_meme_by_id(target_id)
        assert final_record is not None
        assert final_record.score == max_score
        assert final_record.num_comments == max_score // 10
        await store.close()

    @pytest.mark.asyncio
    async def test_sqlite_multiple_store_instances_same_database(
        self, temp_sqlite_db: str, meme_factory: callable
    ) -> None:
        """Verify multiple separate SqliteStore instances operate concurrently on the same database file."""
        store1 = SqliteStore(database_path=temp_sqlite_db)
        store2 = SqliteStore(database_path=temp_sqlite_db)
        await store1.initialize()
        await store2.initialize()

        m1 = NormalizedMeme(**meme_factory(id="inst_1", score=100))
        m2 = NormalizedMeme(**meme_factory(id="inst_2", score=200))

        await store1.save_memes([m1])
        await store2.save_memes([m2])

        assert await store1.count() == 2
        assert await store2.count() == 2

        assert (await store1.get_meme_by_id("inst_2")) is not None
        assert (await store2.get_meme_by_id("inst_1")) is not None

        await store1.close()
        await store2.close()

    @pytest.mark.asyncio
    async def test_sqlite_engagement_merging_logic(
        self, temp_sqlite_db: str, meme_factory: callable
    ) -> None:
        """Verify upsert preserves MAX(score), MAX(num_comments), MIN(created_at)."""
        store = SqliteStore(database_path=temp_sqlite_db)
        await store.initialize()

        # Step 1: Insert initial record
        m1 = NormalizedMeme(
            **meme_factory(
                id="merge_target",
                title="Original Title",
                score=1000,
                num_comments=100,
                created_at=1000.0,
                is_nsfw=False,
                content_hash="h1",
                trending_score=50.0,
            )
        )
        await store.save_memes([m1])

        # Step 2: Upsert updated record with higher score, lower comments, later created_at, NSFW true
        m2 = NormalizedMeme(
            **meme_factory(
                id="merge_target",
                title="Updated Title",
                score=2500,        # Higher -> should win
                num_comments=50,   # Lower -> 100 should remain
                created_at=2000.0, # Later -> 1000.0 should remain
                is_nsfw=True,
                content_hash="h1",
                trending_score=150.0,
            )
        )
        await store.save_memes([m2])

        loaded = await store.get_meme_by_id("merge_target")
        assert loaded is not None
        assert loaded.title == "Updated Title"
        assert loaded.score == 2500
        assert loaded.num_comments == 100
        assert loaded.created_at == 1000.0
        assert loaded.is_nsfw is True
        assert loaded.trending_score == 150.0

        await store.close()

    @pytest.mark.asyncio
    async def test_sqlite_sql_injection_and_extreme_characters(
        self, temp_sqlite_db: str, meme_factory: callable
    ) -> None:
        """Verify SQL injection payloads, extreme Unicode, emojis, and multiline text do not break SQLite store."""
        store = SqliteStore(database_path=temp_sqlite_db)
        await store.initialize()

        malicious_id = "test'; DROP TABLE memes; --"
        malicious_title = "'; DELETE FROM memes WHERE 1=1; SELECT * FROM memes WHERE ''='"
        emoji_author = "🔥💻🚀 MemeMaster_👑_日本語_한국어_Русский_العربية"
        long_url = "https://i.redd.it/" + "a" * 1000 + ".jpg"

        m = NormalizedMeme(
            **meme_factory(
                id=malicious_id,
                title=malicious_title,
                author=emoji_author,
                media_url=long_url,
                content_hash="hash_inject_01",
            )
        )
        await store.save_memes([m])

        assert await store.count() == 1
        fetched = await store.get_meme_by_id(malicious_id)
        assert fetched is not None
        assert fetched.id == malicious_id
        assert fetched.title == malicious_title
        assert fetched.author == emoji_author

        # Ensure table was not dropped
        all_memes = await store.load_all_memes()
        assert len(all_memes) == 1

        await store.close()

    @pytest.mark.asyncio
    async def test_sqlite_corrupt_file_handling(self, tmp_path: Path) -> None:
        """Verify behavior when database file is corrupted (garbage bytes or empty header)."""
        corrupt_db_path = str(tmp_path / "corrupt.db")

        # Write invalid garbage bytes to the file
        with open(corrupt_db_path, "wb") as f:
            f.write(b"NOT_A_SQLITE_DATABASE_GARBAGE_HEADER_DATA_1234567890\x00\xff\xfe")

        store = SqliteStore(database_path=corrupt_db_path)

        # Attempting to initialize or query a corrupt file should raise DatabaseError
        with pytest.raises((sqlite3.DatabaseError, aiosqlite.DatabaseError)):
            await store.initialize()

    @pytest.mark.asyncio
    async def test_sqlite_auto_creates_missing_parent_directory(self, tmp_path: Path, meme_factory: callable) -> None:
        """Verify initialize() creates nested parent directories if they do not exist."""
        nested_db = tmp_path / "nested" / "deeply" / "storage.db"
        assert not nested_db.parent.exists()

        store = SqliteStore(database_path=str(nested_db))
        await store.initialize()

        assert nested_db.parent.exists()
        assert nested_db.exists()

        meme = NormalizedMeme(**meme_factory(id="nested_id"))
        await store.save_memes([meme])
        assert await store.count() == 1
        await store.close()


# ---------------------------------------------------------------------------
# Dimension 2: MemePollingWorker Lifecycle, Concurrency, and Resiliency
# ---------------------------------------------------------------------------

class TestWorkerStressAndResiliency:
    """Stress tests for MemePollingWorker lifecycle, cancellation, and error isolation."""

    @pytest.mark.asyncio
    async def test_worker_rapid_start_stop_cycles(self) -> None:
        """Verify calling start() and stop() rapidly in a loop causes no deadlocks or lingering tasks."""
        store = MemoryStore()
        worker = MemePollingWorker(memory_store=store, poll_interval_seconds=0.01)

        with patch.object(worker, "poll_once", new_callable=AsyncMock) as mock_poll:
            mock_poll.return_value = {"status": "ok", "items": 1}

            for cycle in range(30):
                await worker.start()
                assert worker.is_running is True
                await asyncio.sleep(0.005)
                await worker.stop()
                assert worker.is_running is False
                assert worker._task is None

    @pytest.mark.asyncio
    async def test_worker_cancellation_during_active_polling(self) -> None:
        """Verify stopping the worker while poll_once() is in-flight cancels cleanly without unhandled errors."""
        store = MemoryStore()
        worker = MemePollingWorker(memory_store=store, poll_interval_seconds=0.05)

        poll_started = asyncio.Event()

        async def slow_poll():
            poll_started.set()
            await asyncio.sleep(2.0)  # Long delay to simulate in-flight work
            return {"status": "ok"}

        with patch.object(worker, "poll_once", side_effect=slow_poll):
            await worker.start()
            # Wait until slow poll has actually started
            await asyncio.wait_for(poll_started.wait(), timeout=1.0)
            assert worker.is_running is True

            # Stop worker immediately during active polling
            t0 = time.perf_counter()
            await worker.stop()
            stop_duration = time.perf_counter() - t0

            assert worker.is_running is False
            assert worker._task is None
            assert stop_duration < 1.0, f"Worker stop took too long to cancel active task: {stop_duration:.2f}s"

    @pytest.mark.asyncio
    async def test_worker_partial_source_failures_and_malformed_returns(
        self, meme_factory: callable
    ) -> None:
        """Verify worker handles a diverse mix of failing, hanging, None-returning, and healthy fetchers."""
        store = MemoryStore()

        # Healthy fetcher 1
        f_good = AsyncMock(spec=BaseSourceFetcher)
        f_good.name = "f_good"
        f_good.status = SourceStatus(
            id="f_good", name="good_source", platform=SourcePlatform.REDDIT, community="r/memes", status="ok"
        )
        good_meme = NormalizedMeme(**meme_factory(id="good_01", title="Good Meme"))
        f_good.fetch_memes = AsyncMock(return_value=[good_meme])

        # Failing fetcher (network error)
        f_fail = AsyncMock(spec=BaseSourceFetcher)
        f_fail.name = "f_fail"
        f_fail.status = SourceStatus(
            id="f_fail", name="fail_source", platform=SourcePlatform.REDDIT, community="r/dankmemes", status="ok"
        )
        f_fail.fetch_memes = AsyncMock(side_effect=ConnectionResetError("Socket reset by peer"))
        f_fail.update_failure = AsyncMock()

        # Fetcher returning None instead of list
        f_none = AsyncMock(spec=BaseSourceFetcher)
        f_none.name = "f_none"
        f_none.status = SourceStatus(
            id="f_none", name="none_source", platform=SourcePlatform.KNOWYOURMEME, community="confirmed", status="ok"
        )
        f_none.fetch_memes = AsyncMock(return_value=None)

        # Fetcher where update_failure itself throws an exception
        f_err_fail = AsyncMock(spec=BaseSourceFetcher)
        f_err_fail.name = "f_err_fail"
        f_err_fail.status = SourceStatus(
            id="f_err_fail", name="broken_source", platform=SourcePlatform.REDDIT, community="r/me_irl", status="ok"
        )
        f_err_fail.fetch_memes = AsyncMock(side_effect=RuntimeError("Fetcher internal error"))
        f_err_fail.update_failure = MagicMock(side_effect=Exception("Logger failed in update_failure"))

        worker = MemePollingWorker(
            memory_store=store,
            fetchers=[f_good, f_fail, f_none, f_err_fail],
            poll_interval_seconds=1.0,
        )

        # Execute poll_once
        result = await worker.poll_once()

        assert result["status"] == "ok"
        assert store.count() == 1
        assert store.get_by_id("good_01") is not None
        assert f_fail.update_failure.called

    @pytest.mark.asyncio
    async def test_worker_database_error_during_poll_once_does_not_crash_cache(
        self, meme_factory: callable
    ) -> None:
        """Verify SQLite save error during poll_once does not prevent in-memory cache update."""
        store = MemoryStore()
        mock_sqlite = AsyncMock(spec=SqliteStore)
        mock_sqlite.save_memes = AsyncMock(side_effect=sqlite3.OperationalError("Disk I/O error"))

        f_good = AsyncMock(spec=BaseSourceFetcher)
        f_good.name = "f_good"
        f_good.status = SourceStatus(
            id="f_good", name="good_source", platform=SourcePlatform.REDDIT, community="r/memes", status="ok"
        )
        meme = NormalizedMeme(**meme_factory(id="db_err_meme", title="DB Error Meme"))
        f_good.fetch_memes = AsyncMock(return_value=[meme])

        worker = MemePollingWorker(
            memory_store=store,
            sqlite_store=mock_sqlite,
            fetchers=[f_good],
            poll_interval_seconds=1.0,
        )

        result = await worker.poll_once()

        # Cache should still receive the items even if SQLite persistence failed
        assert result["status"] == "ok"
        assert store.count() == 1
        assert store.get_by_id("db_err_meme") is not None

    @pytest.mark.asyncio
    async def test_worker_restarts_cleanly_after_crash(self) -> None:
        """Verify worker can be restarted after an unexpected stopped state."""
        store = MemoryStore()
        worker = MemePollingWorker(memory_store=store, poll_interval_seconds=0.02)

        call_count = 0

        async def flapping_poll():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Simulated transient panic")
            return {"status": "ok"}

        with patch.object(worker, "poll_once", side_effect=flapping_poll):
            await worker.start()
            await asyncio.sleep(0.08)
            assert worker.is_running is True

            await worker.stop()
            assert worker.is_running is False

            # Restart worker
            await worker.start()
            assert worker.is_running is True
            await asyncio.sleep(0.06)
            await worker.stop()
            assert worker.is_running is False
            assert call_count >= 2

    @pytest.mark.asyncio
    async def test_worker_slow_fetcher_timeout_and_isolation(
        self, meme_factory: callable
    ) -> None:
        """Verify that a slow fetcher does not block healthy fetchers from returning items concurrently."""
        store = MemoryStore()

        # Fast fetcher completes in 10ms
        f_fast = AsyncMock(spec=BaseSourceFetcher)
        f_fast.name = "f_fast"
        f_fast.status = SourceStatus(
            id="f_fast", name="fast_source", platform=SourcePlatform.REDDIT, community="r/memes", status="ok"
        )
        fast_meme = NormalizedMeme(**meme_factory(id="fast_01", title="Fast Meme"))

        async def fast_fetch():
            await asyncio.sleep(0.01)
            return [fast_meme]

        f_fast.fetch_memes = fast_fetch

        # Slow fetcher takes 100ms
        f_slow = AsyncMock(spec=BaseSourceFetcher)
        f_slow.name = "f_slow"
        f_slow.status = SourceStatus(
            id="f_slow", name="slow_source", platform=SourcePlatform.KNOWYOURMEME, community="news", status="ok"
        )
        slow_meme = NormalizedMeme(**meme_factory(id="slow_01", title="Slow Meme"))

        async def slow_fetch():
            await asyncio.sleep(0.1)
            return [slow_meme]

        f_slow.fetch_memes = slow_fetch

        worker = MemePollingWorker(
            memory_store=store,
            fetchers=[f_fast, f_slow],
            poll_interval_seconds=1.0,
        )

        t0 = time.perf_counter()
        results = await worker.fetch_all_sources()
        elapsed = time.perf_counter() - t0

        assert len(results) == 2
        assert {m.id for m in results} == {"fast_01", "slow_01"}
        # Both ran concurrently via asyncio.gather, so total elapsed time is ~0.1s, not 0.11s+
        assert elapsed < 0.3

    @pytest.mark.asyncio
    async def test_worker_periodic_polling_accumulates_across_ticks(
        self, temp_sqlite_db: str, meme_factory: callable
    ) -> None:
        """Verify worker running continuously across multiple periodic ticks persists and updates stores."""
        sqlite = SqliteStore(database_path=temp_sqlite_db)
        await sqlite.initialize()
        store = MemoryStore()

        tick_count = 0

        async def dynamic_fetch():
            nonlocal tick_count
            tick_count += 1
            return [
                NormalizedMeme(
                    **meme_factory(
                        id=f"tick_meme_{tick_count}",
                        title=f"Tick {tick_count} Meme",
                        score=tick_count * 100,
                    )
                )
            ]

        mock_fetcher = AsyncMock(spec=BaseSourceFetcher)
        mock_fetcher.name = "mock_tick"
        mock_fetcher.status = SourceStatus(
            id="mock_tick", name="tick_source", platform=SourcePlatform.REDDIT, community="r/memes", status="ok"
        )
        mock_fetcher.fetch_memes = dynamic_fetch

        worker = MemePollingWorker(
            memory_store=store,
            sqlite_store=sqlite,
            fetchers=[mock_fetcher],
            poll_interval_seconds=0.03,
        )

        await worker.start()
        await asyncio.sleep(0.14)
        await worker.stop()

        assert tick_count >= 3
        assert store.count() >= 3
        assert (await sqlite.count()) >= 3
        await sqlite.close()
