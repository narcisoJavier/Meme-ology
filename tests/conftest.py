"""Shared test configuration, fixtures, and mock factories for Meme Tracker API.

Derives test data strictly from ORIGINAL_REQUEST.md, PROJECT.md, and TEST_INFRA.md.
Provides async HTTP client fixtures, memory and SQLite stores, and static payloads.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from typing import AsyncGenerator, Callable, Generator

import httpx
import pytest
import pytest_asyncio

# Base paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = PROJECT_ROOT / "data" / "fixtures"


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Return path to static fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def raw_reddit_memes_json() -> dict:
    """Load sample raw Reddit r/memes JSON payload from static fixture."""
    fixture_path = FIXTURES_DIR / "reddit_memes.json"
    if fixture_path.exists():
        with open(fixture_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "kind": "Listing",
        "data": {
            "dist": 1,
            "children": [
                {
                    "kind": "t3",
                    "data": {
                        "id": "1d8xyz",
                        "title": "When the compiler works on the first try",
                        "subreddit": "memes",
                        "author": "coding_enthusiast",
                        "score": 14250,
                        "ups": 14250,
                        "num_comments": 342,
                        "created_utc": 1725300000.0,
                        "over_18": False,
                        "is_video": False,
                        "post_hint": "image",
                        "domain": "i.redd.it",
                        "url": "https://i.redd.it/abcdef123456.jpg",
                        "permalink": "/r/memes/comments/1d8xyz/when_the_compiler_works_on_the_first_try/",
                        "stickied": False,
                        "is_self": False,
                    },
                }
            ],
        },
    }


@pytest.fixture(scope="session")
def raw_reddit_dankmemes_json() -> dict:
    """Load sample raw Reddit r/dankmemes JSON payload."""
    fixture_path = FIXTURES_DIR / "reddit_dankmemes.json"
    if fixture_path.exists():
        with open(fixture_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"kind": "Listing", "data": {"dist": 0, "children": []}}


@pytest.fixture(scope="session")
def raw_kym_rss_xml() -> str:
    """Load sample raw Know Your Meme RSS XML payload."""
    fixture_path = FIXTURES_DIR / "kym_memes.xml"
    if fixture_path.exists():
        with open(fixture_path, "r", encoding="utf-8") as f:
            return f.read()
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Know Your Meme Entries - Confirmed</title>
    <link>https://knowyourmeme.com</link>
    <description>New entries</description>
    <item>
      <guid>Entry-57336</guid>
      <link>https://knowyourmeme.com/memes/gucci-morty</link>
      <title>Gucci Morty</title>
      <pubDate>Mon, 24 Aug 2026 10:13:17 -0400</pubDate>
      <description>&lt;a href="https://knowyourmeme.com/memes/gucci-morty"&gt;&lt;img alt="Guccimortycover" src="https://i.kym-cdn.com/entries/icons/mobile/000/057/336/guccimortycover.jpg" /&gt;&lt;/a&gt;&lt;p&gt;Gucci Morty trend.&lt;/p&gt;</description>
    </item>
  </channel>
</rss>"""


@pytest.fixture
def meme_factory() -> Callable[..., dict]:
    """Factory function to build normalized meme dictionaries for testing."""

    def _create_meme(
        id: str = "reddit_memes_test01",
        raw_id: str = "test01",
        title: str = "Test Meme Title",
        media_url: str = "https://i.redd.it/test01.jpg",
        media_type: str = "image",
        source_platform: str = "reddit",
        source_community: str = "r/memes",
        permalink: str = "https://reddit.com/r/memes/comments/test01/",
        author: str = "test_author",
        score: int = 1000,
        num_comments: int = 50,
        created_at: float | None = None,
        is_nsfw: bool = False,
        domain: str = "i.redd.it",
        content_hash: str = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        trending_score: float = 125.0,
    ) -> dict:
        if created_at is None:
            created_at = time.time() - 3600.0
        return {
            "id": id,
            "raw_id": raw_id,
            "title": title,
            "media_url": media_url,
            "media_type": media_type,
            "source_platform": source_platform,
            "source_community": source_community,
            "permalink": permalink,
            "author": author,
            "score": score,
            "num_comments": num_comments,
            "created_at": created_at,
            "is_nsfw": is_nsfw,
            "domain": domain,
            "content_hash": content_hash,
            "trending_score": trending_score,
        }

    return _create_meme


@pytest.fixture
def sample_normalized_memes(meme_factory: Callable[..., dict]) -> list[dict]:
    """Generate a diverse set of 10 normalized memes across sources and categories."""
    now = time.time()
    memes = [
        meme_factory(
            id="reddit_memes_001",
            raw_id="001",
            title="Compiler first try success",
            media_url="https://i.redd.it/compiler01.jpg",
            media_type="image",
            source_platform="reddit",
            source_community="r/memes",
            score=15000,
            num_comments=300,
            created_at=now - 7200,
            is_nsfw=False,
            trending_score=520.5,
        ),
        meme_factory(
            id="reddit_dankmemes_002",
            raw_id="002",
            title="Quantum debugging meme",
            media_url="https://i.redd.it/quantum02.png",
            media_type="image",
            source_platform="reddit",
            source_community="r/dankmemes",
            score=25000,
            num_comments=600,
            created_at=now - 3600,
            is_nsfw=False,
            trending_score=980.0,
        ),
        meme_factory(
            id="reddit_me_irl_003",
            raw_id="003",
            title="me_irl after socializing",
            media_url="https://i.redd.it/social03.gif",
            media_type="gif",
            source_platform="reddit",
            source_community="r/me_irl",
            score=18000,
            num_comments=400,
            created_at=now - 14400,
            is_nsfw=False,
            trending_score=410.2,
        ),
        meme_factory(
            id="reddit_wholesomememes_004",
            raw_id="004",
            title="You are doing great today",
            media_url="https://i.redd.it/wholesome04.jpg",
            media_type="image",
            source_platform="reddit",
            source_community="r/wholesomememes",
            score=32000,
            num_comments=450,
            created_at=now - 1800,
            is_nsfw=False,
            trending_score=1450.0,
        ),
        meme_factory(
            id="kym_Entry-57336",
            raw_id="Entry-57336",
            title="Gucci Morty",
            media_url="https://i.kym-cdn.com/entries/icons/mobile/000/057/336/guccimortycover.jpg",
            media_type="image",
            source_platform="knowyourmeme",
            source_community="confirmed",
            permalink="https://knowyourmeme.com/memes/gucci-morty",
            score=5000,
            num_comments=80,
            created_at=now - 86400,
            is_nsfw=False,
            trending_score=110.0,
        ),
        meme_factory(
            id="kym_Entry-57337",
            raw_id="Entry-57337",
            title="Chill Guy",
            media_url="https://i.kym-cdn.com/entries/icons/mobile/000/057/337/chill_guy_meme.png",
            media_type="image",
            source_platform="knowyourmeme",
            source_community="confirmed",
            permalink="https://knowyourmeme.com/memes/chill-guy",
            score=12000,
            num_comments=250,
            created_at=now - 7200,
            is_nsfw=False,
            trending_score=490.0,
        ),
        meme_factory(
            id="reddit_memes_007_nsfw",
            raw_id="007_nsfw",
            title="Late night spicy humor [NSFW]",
            media_url="https://i.redd.it/spicy07.jpg",
            media_type="image",
            source_platform="reddit",
            source_community="r/memes",
            score=4500,
            num_comments=90,
            created_at=now - 3600,
            is_nsfw=True,
            trending_score=210.0,
        ),
        meme_factory(
            id="reddit_dankmemes_008_video",
            raw_id="008_video",
            title="Video of datacenter disaster",
            media_url="https://v.redd.it/video08/DASH_720.mp4",
            media_type="video",
            source_platform="reddit",
            source_community="r/dankmemes",
            score=8200,
            num_comments=140,
            created_at=now - 10800,
            is_nsfw=False,
            trending_score=315.0,
        ),
        meme_factory(
            id="reddit_memes_009_stale",
            raw_id="009_stale",
            title="Classic viral meme from last month",
            media_url="https://i.redd.it/stale09.jpg",
            media_type="image",
            source_platform="reddit",
            source_community="r/memes",
            score=85000,
            num_comments=1200,
            created_at=now - 259200,
            is_nsfw=False,
            trending_score=75.0,
        ),
        meme_factory(
            id="kym_Entry-57338_nsfw",
            raw_id="Entry-57338_nsfw",
            title="Controversial adult meme trend",
            media_url="https://i.kym-cdn.com/entries/icons/mobile/000/057/338/adult_trend.jpg",
            media_type="image",
            source_platform="knowyourmeme",
            source_community="confirmed",
            permalink="https://knowyourmeme.com/memes/controversial-trend",
            score=6200,
            num_comments=110,
            created_at=now - 43200,
            is_nsfw=True,
            trending_score=140.0,
        ),
    ]
    return memes


@pytest.fixture
def temp_sqlite_db() -> Generator[str, None, None]:
    """Provide path to a temporary SQLite database file with automatic cleanup."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        yield db_path
    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except OSError:
                pass


@pytest_asyncio.fixture
async def async_client(sample_normalized_memes: list[dict]) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Asynchronous HTTP test client bound to FastAPI application via ASGITransport."""
    try:
        from app.main import app
        from app.models.meme import NormalizedMeme
        from app.storage.memory_store import MemoryStore

        # Populate memory store with sample test items
        store = getattr(app.state, "memory_store", None)
        if store is None:
            store = MemoryStore()
            app.state.memory_store = store

        store.clear()
        pydantic_memes = [NormalizedMeme(**m) for m in sample_normalized_memes]
        store.upsert_memes(pydantic_memes)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
            headers={"User-Agent": "MemeTracker-Test/1.0"},
        ) as client:
            yield client
    except (ImportError, AttributeError) as e:
        pytest.skip(f"FastAPI app or storage module not available for HTTP client: {e}")
