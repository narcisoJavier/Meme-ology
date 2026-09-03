"""Unit tests for MemePollingWorker 4-platform concurrent integration and lifecycle."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.ingestion.base import BaseSourceFetcher
from app.ingestion.bluesky import BlueskyFetcher
from app.ingestion.knowyourmeme import KnowYourMemeFetcher
from app.ingestion.mastodon import MastodonFetcher
from app.ingestion.reddit import RedditFetcher
from app.ingestion.worker import MemePollingWorker
from app.models.meme import MediaType, NormalizedMeme, SourcePlatform
from app.storage.memory_store import MemoryStore
from app.storage.sqlite_store import SqliteStore


@pytest.fixture
def mock_4platform_memes() -> list[NormalizedMeme]:
    """Provide normalized memes representing all 4 platforms."""
    return [
        NormalizedMeme(
            id="reddit_memes_test1",
            raw_id="test1",
            title="Reddit Meme 1",
            media_url="https://i.redd.it/reddit1.jpg",
            media_type=MediaType.IMAGE,
            source_platform=SourcePlatform.REDDIT,
            source_community="r/memes",
            permalink="https://reddit.com/r/memes/comments/test1/",
            author="u/red_user",
            score=1000,
            num_comments=50,
            created_at=1725300000.0,
        ),
        NormalizedMeme(
            id="bluesky_bskytest1",
            raw_id="bskytest1",
            title="Bluesky Meme 1",
            media_url="https://cdn.bsky.app/img/feed_fullsize/plain/did:plc:1/bafkreibsky1@jpeg",
            media_type=MediaType.IMAGE,
            source_platform=SourcePlatform.BLUESKY,
            source_community="meme",
            permalink="https://bsky.app/profile/user.bsky.social/post/bskytest1",
            author="@user.bsky.social",
            score=500,
            num_comments=25,
            created_at=1725301000.0,
        ),
        NormalizedMeme(
            id="kym_Entry-9999",
            raw_id="Entry-9999",
            title="KYM Meme 1",
            media_url="https://i.kym-cdn.com/photos/images/original/000/009/999/kym1.jpg",
            media_type=MediaType.IMAGE,
            source_platform=SourcePlatform.KNOWYOURMEME,
            source_community="confirmed",
            permalink="https://knowyourmeme.com/memes/entry-9999",
            author="KYM Staff",
            score=2000,
            num_comments=80,
            created_at=1725302000.0,
        ),
        NormalizedMeme(
            id="mastodon_11223344",
            raw_id="11223344",
            title="Mastodon Meme 1",
            media_url="https://files.mastodon.social/media_attachments/files/112/233/44/original/masto1.png",
            media_type=MediaType.IMAGE,
            source_platform=SourcePlatform.MASTODON,
            source_community="#meme",
            permalink="https://mastodon.social/@fedi/11223344",
            author="@fedi@mastodon.social",
            score=300,
            num_comments=15,
            created_at=1725303000.0,
        ),
    ]


@pytest.mark.asyncio
class TestWorker4PlatformIntegration:
    """Tier 1 & Tier 2 tests for MemePollingWorker across all 4 platforms."""

    async def test_worker_default_fetchers_includes_all_4_platforms(self) -> None:
        """Verify default fetchers assembly contains Reddit, KYM, Bluesky, and Mastodon fetchers."""
        store = MemoryStore()
        worker = MemePollingWorker(memory_store=store)
        fetchers = worker.fetchers

        assert len(fetchers) >= 4
        platforms = {f.platform for f in fetchers}
        assert SourcePlatform.REDDIT in platforms
        assert SourcePlatform.BLUESKY in platforms
        assert SourcePlatform.KNOWYOURMEME in platforms
        assert SourcePlatform.MASTODON in platforms

    async def test_worker_fetch_all_sources_runs_concurrently(
        self, mock_4platform_memes: list[NormalizedMeme]
    ) -> None:
        """Verify fetch_all_sources aggregates items from mock fetchers representing all platforms."""
        store = MemoryStore()

        mock_reddit = AsyncMock(spec=BaseSourceFetcher)
        mock_reddit.name = "reddit:r/memes"
        mock_reddit.status = store.get_sources()[0]
        mock_reddit.fetch_memes = AsyncMock(return_value=[mock_4platform_memes[0]])

        mock_bluesky = AsyncMock(spec=BaseSourceFetcher)
        mock_bluesky.name = "bluesky:meme"
        mock_bluesky.status = store.get_sources()[0]
        mock_bluesky.fetch_memes = AsyncMock(return_value=[mock_4platform_memes[1]])

        mock_kym = AsyncMock(spec=BaseSourceFetcher)
        mock_kym.name = "knowyourmeme:confirmed"
        mock_kym.status = store.get_sources()[0]
        mock_kym.fetch_memes = AsyncMock(return_value=[mock_4platform_memes[2]])

        mock_mastodon = AsyncMock(spec=BaseSourceFetcher)
        mock_mastodon.name = "mastodon:#meme"
        mock_mastodon.status = store.get_sources()[0]
        mock_mastodon.fetch_memes = AsyncMock(return_value=[mock_4platform_memes[3]])

        worker = MemePollingWorker(
            memory_store=store,
            fetchers=[mock_reddit, mock_bluesky, mock_kym, mock_mastodon],
        )

        all_memes = await worker.fetch_all_sources()
        assert len(all_memes) == 4
        assert {m.source_platform for m in all_memes} == {
            SourcePlatform.REDDIT,
            SourcePlatform.BLUESKY,
            SourcePlatform.KNOWYOURMEME,
            SourcePlatform.MASTODON,
        }

    async def test_worker_isolates_single_platform_failure(
        self, mock_4platform_memes: list[NormalizedMeme]
    ) -> None:
        """Verify an error in Mastodon or Bluesky fetcher does not fail other platforms."""
        store = MemoryStore()

        mock_ok1 = AsyncMock(spec=BaseSourceFetcher)
        mock_ok1.name = "reddit:r/memes"
        mock_ok1.status = store.get_sources()[0]
        mock_ok1.fetch_memes = AsyncMock(return_value=[mock_4platform_memes[0]])

        mock_ok2 = AsyncMock(spec=BaseSourceFetcher)
        mock_ok2.name = "bluesky:meme"
        mock_ok2.status = store.get_sources()[0]
        mock_ok2.fetch_memes = AsyncMock(return_value=[mock_4platform_memes[1]])

        mock_fail = AsyncMock(spec=BaseSourceFetcher)
        mock_fail.name = "mastodon:#meme"
        mock_fail.status = store.get_sources()[0]
        mock_fail.fetch_memes = AsyncMock(side_effect=httpx.ConnectError("Mastodon timeout"))
        mock_fail.update_failure = MagicMock()

        worker = MemePollingWorker(
            memory_store=store,
            fetchers=[mock_ok1, mock_ok2, mock_fail],
        )

        results = await worker.fetch_all_sources()
        assert len(results) == 2
        assert mock_fail.update_failure.called

    async def test_worker_poll_once_hydrates_both_memory_and_sqlite(
        self, temp_sqlite_db: str, mock_4platform_memes: list[NormalizedMeme]
    ) -> None:
        """Verify poll_once persists 4-platform memes to both MemoryStore and SqliteStore."""
        sqlite = SqliteStore(database_path=temp_sqlite_db)
        await sqlite.initialize()
        store = MemoryStore()

        worker = MemePollingWorker(
            memory_store=store, sqlite_store=sqlite, poll_interval_seconds=1.0
        )

        with patch.object(worker, "fetch_all_sources", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_4platform_memes
            summary = await worker.poll_once()

            assert summary["status"] == "ok"
            assert store.count() == 4
            assert await sqlite.count() == 4

        await sqlite.close()

    async def test_worker_start_stop_idempotent(self) -> None:
        """Verify worker startup and shutdown lifecycle."""
        store = MemoryStore()
        worker = MemePollingWorker(memory_store=store, poll_interval_seconds=0.05)

        with patch.object(worker, "poll_once", new_callable=AsyncMock) as mock_poll:
            mock_poll.return_value = {"status": "ok", "items": 0}

            await worker.start()
            await worker.start()  # Idempotent call
            assert worker.is_running is True

            await asyncio.sleep(0.12)
            assert mock_poll.call_count >= 1

            await worker.stop()
            await worker.stop()  # Idempotent call
            assert worker.is_running is False
