"""Regression tests for live-only ingestion and provenance fields."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ingestion.base import BaseSourceFetcher
from app.ingestion.reddit import RedditFetcher
from app.ingestion.worker import MemePollingWorker
from app.models.meme import NormalizedMeme, SourcePlatform
from app.storage.memory_store import MemoryStore


def _meme(**overrides: object) -> NormalizedMeme:
    values = {
        "id": "reddit_memes_provenance01",
        "raw_id": "provenance01",
        "title": "A real post",
        "media_url": "https://i.redd.it/provenance01.jpg",
        "source_platform": SourcePlatform.REDDIT,
        "source_community": "r/memes",
        "permalink": "https://www.reddit.com/r/memes/comments/provenance01/",
        "created_at": 1_725_300_000.0,
        "score": 100,
        "num_comments": 10,
    }
    values.update(overrides)
    return NormalizedMeme(**values)


class StubFetcher(BaseSourceFetcher):
    def __init__(self, item: NormalizedMeme) -> None:
        super().__init__("stub:r/memes", SourcePlatform.REDDIT, "r/memes")
        self.item = item

    async def fetch_memes(self) -> list[NormalizedMeme]:
        return [self.item]

    def load_offline_fixtures(self) -> list[NormalizedMeme]:
        return [self.item]


@pytest.mark.asyncio
async def test_worker_excludes_fixture_fallbacks_from_live_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.ingestion.worker.get_settings",
        lambda: SimpleNamespace(OFFLINE_MODE=False, POLL_INTERVAL_SECONDS=60),
    )
    fixture = _meme(data_origin="fixture", metrics_quality="fixture", observed_at=None)
    fetcher = StubFetcher(fixture)
    store = MemoryStore()

    result = await MemePollingWorker(store, fetchers=[fetcher]).fetch_all_sources()

    assert result == []
    assert fetcher.status.status == "degraded"


@pytest.mark.asyncio
async def test_worker_stamps_live_observation_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.ingestion.worker.get_settings",
        lambda: SimpleNamespace(OFFLINE_MODE=False, POLL_INTERVAL_SECONDS=60),
    )
    fetcher = StubFetcher(_meme(data_origin="live", observed_at=None))

    result = await MemePollingWorker(MemoryStore(), fetchers=[fetcher]).fetch_all_sources()

    assert len(result) == 1
    assert result[0].data_origin == "live"
    assert result[0].observed_at is not None


def test_reddit_parser_does_not_invent_gateway_timestamp_or_comments() -> None:
    fetcher = RedditFetcher(subreddit="memes")
    payload = {
        "memes": [
            {
                "url": "https://i.redd.it/no-metrics.jpg",
                "title": "No metrics in gateway response",
                "postLink": "https://www.reddit.com/r/memes/comments/no_metrics/",
                "ups": 123,
            }
        ]
    }

    assert fetcher.parse_gateway_dict(payload) == []
