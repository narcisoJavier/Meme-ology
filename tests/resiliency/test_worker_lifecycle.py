"""Tests for background polling worker lifecycle, periodic execution, and graceful shutdown.

Validates:
- Background worker startup and shutdown states.
- poll_once execution cycle and cache hydration.
- Graceful cancellation handling without unhandled CancelledError.
- Loop fault tolerance: exception during one cycle does not terminate worker thread/task.
- Idempotent start() and stop() calls.
- Worker status reporting and poll interval configuration.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.models.meme import NormalizedMeme

try:
    from app.ingestion.worker import MemePollingWorker
    from app.storage.memory_store import MemoryStore
except ImportError:
    MemePollingWorker = None  # type: ignore
    MemoryStore = None  # type: ignore


@pytest.fixture(autouse=True)
def check_worker_implemented():
    """Ensure worker and storage modules are available or skip."""
    if MemePollingWorker is None or MemoryStore is None:
        pytest.skip("app.ingestion.worker or app.storage not yet implemented (Milestone M2)")


class TestWorkerLifecycle:
    """Tier 1 & Tier 2 tests for background polling worker task."""

    @pytest.mark.asyncio
    async def test_worker_initial_state_and_properties(self) -> None:
        """Verify worker starts in stopped state."""
        store = MemoryStore()
        worker = MemePollingWorker(memory_store=store, poll_interval_seconds=1.0)
        assert worker.is_running is False

    @pytest.mark.asyncio
    async def test_worker_poll_once_hydrates_memory_store(
        self, sample_normalized_memes: list[dict]
    ) -> None:
        """Verify executing poll_once populates the memory store."""
        store = MemoryStore()
        worker = MemePollingWorker(memory_store=store, poll_interval_seconds=1.0)

        pydantic_memes = [NormalizedMeme(**m) for m in sample_normalized_memes]

        with patch.object(worker, "fetch_all_sources", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = pydantic_memes
            result = await worker.poll_once()

            assert store.count() > 0
            assert result.get("new_items", 0) > 0 or result.get("total_items", 0) > 0

    @pytest.mark.asyncio
    async def test_worker_start_and_graceful_stop(self) -> None:
        """Verify worker can be started as background task and cleanly stopped."""
        store = MemoryStore()
        worker = MemePollingWorker(memory_store=store, poll_interval_seconds=0.05)

        with patch.object(worker, "poll_once", new_callable=AsyncMock) as mock_poll:
            mock_poll.return_value = {"status": "ok", "items": 5}

            await worker.start()
            assert worker.is_running is True

            await asyncio.sleep(0.12)
            assert mock_poll.call_count >= 1

            await worker.stop()
            assert worker.is_running is False

    @pytest.mark.asyncio
    async def test_worker_survives_exception_in_poll_loop(self) -> None:
        """Verify an uncaught exception during a single poll iteration does not kill the worker loop."""
        store = MemoryStore()
        worker = MemePollingWorker(memory_store=store, poll_interval_seconds=0.05)

        with patch.object(worker, "poll_once", new_callable=AsyncMock) as mock_poll:
            mock_poll.side_effect = [RuntimeError("Transient database lock"), {"status": "ok"}]

            await worker.start()
            await asyncio.sleep(0.15)
            assert worker.is_running is True

            await worker.stop()
            assert worker.is_running is False

    @pytest.mark.asyncio
    async def test_worker_double_start_stop_idempotent(self) -> None:
        """Verify calling start() or stop() multiple times causes no errors."""
        store = MemoryStore()
        worker = MemePollingWorker(memory_store=store, poll_interval_seconds=0.1)

        await worker.start()
        await worker.start()
        assert worker.is_running is True

        await worker.stop()
        await worker.stop()
        assert worker.is_running is False

    @pytest.mark.asyncio
    async def test_worker_respects_custom_poll_interval(self) -> None:
        """Verify worker poll interval setting is stored and respected."""
        store = MemoryStore()
        worker = MemePollingWorker(memory_store=store, poll_interval_seconds=120.0)
        assert worker.poll_interval_seconds == 120.0

    @pytest.mark.asyncio
    async def test_worker_empty_poll_does_not_corrupt_existing_cache(
        self, sample_normalized_memes: list[dict]
    ) -> None:
        """Verify worker poll returning 0 items keeps current cache intact."""
        store = MemoryStore()
        pydantic_memes = [NormalizedMeme(**m) for m in sample_normalized_memes]
        store.upsert_memes(pydantic_memes)
        initial_count = store.count()

        worker = MemePollingWorker(memory_store=store, poll_interval_seconds=1.0)
        with patch.object(worker, "fetch_all_sources", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = []
            await worker.poll_once()
            assert store.count() == initial_count

    @pytest.mark.asyncio
    async def test_worker_default_fetchers_initialization(self) -> None:
        """Verify worker initializes default Reddit and KYM fetchers if none provided."""
        store = MemoryStore()
        worker = MemePollingWorker(memory_store=store)
        fetchers = worker.fetchers
        assert len(fetchers) > 0
        assert any(f.platform.value == "reddit" for f in fetchers)
        assert any(f.platform.value == "knowyourmeme" for f in fetchers)

    @pytest.mark.asyncio
    async def test_worker_poll_once_with_sqlite_persistence(
        self, temp_sqlite_db: str, sample_normalized_memes: list[dict]
    ) -> None:
        """Verify poll_once saves memes to SqliteStore when configured."""
        from app.storage.sqlite_store import SqliteStore

        sqlite = SqliteStore(database_path=temp_sqlite_db)
        await sqlite.initialize()
        store = MemoryStore()

        worker = MemePollingWorker(memory_store=store, sqlite_store=sqlite, poll_interval_seconds=1.0)
        pydantic_memes = [NormalizedMeme(**m) for m in sample_normalized_memes]

        with patch.object(worker, "fetch_all_sources", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = pydantic_memes
            await worker.poll_once()

            assert store.count() == len(pydantic_memes)
            assert await sqlite.count() == len(pydantic_memes)

        await sqlite.close()

    @pytest.mark.asyncio
    async def test_worker_fetch_all_sources_isolates_failing_fetcher(
        self, sample_normalized_memes: list[dict]
    ) -> None:
        """Verify an individual fetcher throwing an exception does not prevent other fetchers from returning items."""
        store = MemoryStore()

        mock_ok_fetcher = AsyncMock()
        mock_ok_fetcher.name = "mock_ok"
        mock_ok_fetcher.status = store.get_sources()[0]
        pydantic_memes = [NormalizedMeme(**m) for m in sample_normalized_memes[:3]]
        mock_ok_fetcher.fetch_memes = AsyncMock(return_value=pydantic_memes)

        mock_fail_fetcher = AsyncMock()
        mock_fail_fetcher.name = "mock_fail"
        mock_fail_fetcher.status = store.get_sources()[1]
        mock_fail_fetcher.fetch_memes = AsyncMock(side_effect=RuntimeError("Network timeout"))
        mock_fail_fetcher.update_failure = AsyncMock()

        worker = MemePollingWorker(
            memory_store=store,
            fetchers=[mock_ok_fetcher, mock_fail_fetcher],
        )

        results = await worker.fetch_all_sources()
        assert len(results) == len(pydantic_memes)
        assert mock_fail_fetcher.update_failure.called
