"""Background ingestion worker for periodic multi-source meme discovery."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.config import get_settings
from app.ingestion.base import BaseSourceFetcher
from app.ingestion.knowyourmeme import KnowYourMemeFetcher
from app.ingestion.reddit import RedditFetcher
from app.models.meme import NormalizedMeme
from app.storage.memory_store import MemoryStore
from app.storage.sqlite_store import SqliteStore

logger = logging.getLogger(__name__)


class MemePollingWorker:
    """Async background polling engine that periodically fetches memes and updates hot cache."""

    def __init__(
        self,
        memory_store: MemoryStore,
        sqlite_store: Optional[SqliteStore] = None,
        poll_interval_seconds: Optional[float] = None,
        fetchers: Optional[List[BaseSourceFetcher]] = None,
    ) -> None:
        settings = get_settings()
        self.memory_store = memory_store
        self.sqlite_store = sqlite_store
        self.poll_interval_seconds = (
            float(poll_interval_seconds)
            if poll_interval_seconds is not None
            else float(settings.POLL_INTERVAL_SECONDS)
        )
        self._fetchers = fetchers
        self._is_running = False
        self._task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

    @property
    def is_running(self) -> bool:
        """Return True if background worker is currently executing."""
        return self._is_running

    @property
    def fetchers(self) -> List[BaseSourceFetcher]:
        """Return list of active source fetchers, building defaults if not provided."""
        if self._fetchers is None:
            self._fetchers = self._build_default_fetchers()
        return self._fetchers

    def _build_default_fetchers(self) -> List[BaseSourceFetcher]:
        """Construct standard fetchers for configured Reddit subreddits and KYM RSS feeds."""
        settings = get_settings()
        fetcher_list: List[BaseSourceFetcher] = []
        for sub in settings.REDDIT_SUBREDDITS:
            clean_sub = sub.lstrip("r/").strip()
            fetcher_list.append(RedditFetcher(subreddit=clean_sub))
        for kym_url in settings.KYM_FEED_URLS:
            cat = "confirmed" if "memes" in kym_url else "news"
            fetcher_list.append(KnowYourMemeFetcher(feed_url=kym_url, category=cat))
        return fetcher_list

    async def fetch_all_sources(self) -> List[NormalizedMeme]:
        """Fetch memes from all registered sources with per-source error isolation."""
        active_fetchers = self.fetchers
        if not active_fetchers:
            return []

        async def _fetch_single(fetcher: BaseSourceFetcher) -> List[NormalizedMeme]:
            try:
                memes = await fetcher.fetch_memes()
                self.memory_store.update_source_status(fetcher.status)
                return memes or []
            except Exception as e:
                logger.warning("Error fetching from %s: %s", fetcher.name, e)
                fail_res = fetcher.update_failure(e)
                if asyncio.iscoroutine(fail_res):
                    await fail_res
                self.memory_store.update_source_status(fetcher.status)
                return []

        results = await asyncio.gather(
            *[_fetch_single(f) for f in active_fetchers],
            return_exceptions=True,
        )

        all_memes: List[NormalizedMeme] = []
        for res in results:
            if isinstance(res, list):
                all_memes.extend(res)
            elif isinstance(res, Exception):
                logger.error("Unexpected unhandled exception in source gather: %s", res)

        return all_memes

    async def poll_once(self) -> Dict[str, Any]:
        """Execute a single polling cycle across all sources and update stores."""
        logger.debug("Executing poll_once cycle...")
        memes = await self.fetch_all_sources()
        new_count = 0

        if memes:
            if self.sqlite_store:
                try:
                    await self.sqlite_store.save_memes(memes)
                except Exception as db_err:
                    logger.error("Failed to persist memes to SQLite during poll_once: %s", db_err)

            self.memory_store.upsert_memes(memes)
            new_count = len(memes)

        total_cached = self.memory_store.count()
        logger.debug(
            "poll_once cycle finished: %d items ingested, %d total in cache.",
            new_count,
            total_cached,
        )
        return {
            "status": "ok",
            "new_items": new_count,
            "total_items": total_cached,
            "sources_polled": len(self.fetchers),
        }

    async def start(self) -> None:
        """Start the background polling task (idempotent)."""
        if self._is_running:
            return
        self._is_running = True
        self._shutdown_event.clear()
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "MemePollingWorker started (polling every %.2fs).", self.poll_interval_seconds
        )

    async def stop(self) -> None:
        """Stop the background polling task gracefully (idempotent)."""
        if not self._is_running:
            return
        self._is_running = False
        self._shutdown_event.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(self._task), timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError, TimeoutError, Exception):
                pass
        self._task = None
        logger.info("MemePollingWorker stopped.")

    async def _run_loop(self) -> None:
        """Continuous background execution loop."""
        while self._is_running and not self._shutdown_event.is_set():
            try:
                await self.poll_once()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Unhandled error in background polling worker cycle: %s", exc)

            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self.poll_interval_seconds,
                )
            except (asyncio.TimeoutError, TimeoutError):
                pass
            except asyncio.CancelledError:
                break
