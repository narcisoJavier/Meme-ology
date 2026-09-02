"""Integration test for FastAPI application lifespan startup and shutdown."""

from __future__ import annotations

import tempfile
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI

from app.main import lifespan
from app.models.meme import NormalizedMeme
from app.storage.memory_store import MemoryStore
from app.storage.sqlite_store import SqliteStore


@pytest.mark.asyncio
async def test_app_lifespan_lifecycle(temp_sqlite_db: str) -> None:
    """Verify application lifespan initializes SQLite, hydrates memory store, and shuts down cleanly."""
    test_app = FastAPI(lifespan=lifespan)
    test_app.state.sqlite_store = SqliteStore(database_path=temp_sqlite_db)
    test_app.state.memory_store = MemoryStore()

    # Pre-seed DB with one meme
    sqlite = test_app.state.sqlite_store
    await sqlite.initialize()
    meme = NormalizedMeme(
        id="test_lifespan_01",
        title="Lifespan test meme",
        media_url="https://i.redd.it/lifespan.png",
        source_platform="reddit",
        source_community="r/memes",
        permalink="https://reddit.com/r/memes/lifespan",
        created_at=1725300000.0,
        score=100,
    )
    await sqlite.save_memes([meme])

    with patch("app.ingestion.worker.MemePollingWorker.start", new_callable=AsyncMock) as mock_start, \
         patch("app.ingestion.worker.MemePollingWorker.stop", new_callable=AsyncMock) as mock_stop:
        async with lifespan(test_app):
            assert test_app.state.memory_store.count() == 1
            assert test_app.state.memory_store.get_by_id("test_lifespan_01") is not None
            mock_start.assert_awaited_once()

        mock_stop.assert_awaited_once()
