"""Adversarial stress test suite for Milestone M1: Multi-Platform Authentic Ingestion.

Tests edge cases, malformed payloads, Unicode handles, long texts, network errors,
offline fixture fallbacks, zero-mock policy, and concurrent worker resiliency.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.config import get_settings
from app.ingestion.base import BaseSourceFetcher
from app.ingestion.bluesky import BlueskyFetcher, parse_bluesky_feed, parse_iso8601_date as parse_bsky_date
from app.ingestion.mastodon import (
    MastodonFetcher,
    parse_iso8601_date as parse_masto_date,
    parse_mastodon_timeline,
    strip_html_tags,
)
from app.ingestion.reddit import RedditFetcher, parse_reddit_listing
from app.ingestion.knowyourmeme import KnowYourMemeFetcher
from app.ingestion.worker import MemePollingWorker
from app.models.meme import MediaType, Meme, NormalizedMeme, SourcePlatform
from app.storage.memory_store import MemoryStore
from app.storage.sqlite_store import SqliteStore


# ==============================================================================
# 1. BLUESKY ADVERSARIAL TESTS
# ==============================================================================

class TestBlueskyAdversarial:
    """Stress tests for Bluesky AT Protocol parser and fetcher."""

    @pytest.mark.parametrize(
        "bad_payload",
        [
            "",
            "   ",
            "not-json-at-all",
            "{broken json: true",
            "12345",
            "true",
            "null",
            "[]",
            "{}",
            '{"posts": null}',
            '{"posts": 123}',
            '{"posts": "string_not_list"}',
            '{"posts": [null, 123, "text", true, {}]}',
            '{"feed": null}',
            '{"feed": [null, {}]}',
        ],
    )
    def test_bluesky_malformed_json_inputs(self, bad_payload: str) -> None:
        """Parser must never throw unhandled exceptions on corrupt JSON or invalid types."""
        results = parse_bluesky_feed(bad_payload)
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.parametrize(
        "post_data",
        [
            {},  # completely empty
            {"uri": ""},
            {"uri": "at://did:plc:123/app.bsky.feed.post/123"},  # no media
            {"uri": "at://did:plc:123/app.bsky.feed.post/123", "embed": None},
            {"uri": "at://did:plc:123/app.bsky.feed.post/123", "embed": {}},
            {"uri": "at://did:plc:123/app.bsky.feed.post/123", "embed": {"$type": "app.bsky.embed.external#view"}},
            {"uri": "at://did:plc:123/app.bsky.feed.post/123", "embed": {"$type": "app.bsky.embed.images#view", "images": []}},
            {"uri": "at://did:plc:123/app.bsky.feed.post/123", "embed": {"$type": "app.bsky.embed.images#view", "images": [{}]}},
            {"uri": "at://did:plc:123/app.bsky.feed.post/123", "embed": {"$type": "app.bsky.embed.images#view", "images": [{"fullsize": ""}]}},
            {"uri": "at://did:plc:123/app.bsky.feed.post/123", "embed": {"$type": "app.bsky.embed.recordWithMedia#view", "media": None}},
            {"uri": "at://did:plc:123/app.bsky.feed.post/123", "embed": {"$type": "app.bsky.embed.recordWithMedia#view", "media": {"images": []}}},
            {"uri": "at://did:plc:123/app.bsky.feed.post/123", "embed": {"$type": "app.bsky.embed.video#view", "playlist": ""}},
            {
                "uri": "at://did:plc:123/app.bsky.feed.post/123",
                "record": {"embed": {"$type": "app.bsky.embed.images", "images": [{"image": {"ref": None}}]}},
            },
        ],
    )
    def test_bluesky_missing_or_corrupted_media_returns_none(self, post_data: Dict[str, Any]) -> None:
        """Posts missing direct image/video media must be cleanly ignored."""
        fetcher = BlueskyFetcher()
        meme = fetcher.parse_post_record(post_data)
        assert meme is None

    def test_bluesky_unicode_handles_and_weird_characters(self) -> None:
        """Parser must safely handle Unicode handles, emojis, and unconventional handle strings."""
        handles = [
            "üñîçødé_mèmè.bsky.social",
            "🚀🔥_viral.bsky.social",
            "@prefixed_handle.bsky.social",
            "user@domain.com",
            "日本語ユーザー.bsky.social",
            "",
        ]
        for h in handles:
            payload = {
                "posts": [
                    {
                        "uri": "at://did:plc:test1234/app.bsky.feed.post/post_unicode",
                        "author": {"handle": h, "did": "did:plc:test1234"},
                        "record": {"text": "Testing unicode handles"},
                        "embed": {
                            "$type": "app.bsky.embed.images#view",
                            "images": [{"fullsize": "https://cdn.bsky.app/img/feed_fullsize/plain/did:plc:test1234/bafkrei@jpeg"}],
                        },
                    }
                ]
            }
            memes = parse_bluesky_feed(payload)
            assert len(memes) == 1
            assert memes[0].author.startswith("@")
            assert memes[0].permalink.startswith("https://bsky.app/profile/")

    def test_bluesky_extremely_long_text_and_html_injection(self) -> None:
        """Parser must sanitize HTML and handle arbitrarily long text without crashing."""
        huge_text = "<script>alert('xss')</script> " + ("A" * 50000) + " <p>Safe Text</p>"
        payload = {
            "posts": [
                {
                    "uri": "at://did:plc:longtext/app.bsky.feed.post/rkey123",
                    "author": {"handle": "spammer.bsky.social"},
                    "record": {"text": huge_text},
                    "embed": {
                        "$type": "app.bsky.embed.images#view",
                        "images": [{"fullsize": "https://cdn.bsky.app/img/feed_fullsize/plain/did:plc:longtext/img@jpeg"}],
                    },
                }
            ]
        }
        memes = parse_bluesky_feed(payload)
        assert len(memes) == 1
        assert "<script>" not in memes[0].title
        assert "<p>" not in memes[0].title
        assert len(memes[0].title) > 1000

    def test_bluesky_alt_text_fallback_when_text_empty(self) -> None:
        """When text is empty, title should fall back to image alt text."""
        payload = {
            "posts": [
                {
                    "uri": "at://did:plc:123/app.bsky.feed.post/alt_post",
                    "author": {"handle": "artist.bsky.social"},
                    "record": {"text": ""},
                    "embed": {
                        "$type": "app.bsky.embed.images#view",
                        "images": [
                            {
                                "fullsize": "https://cdn.bsky.app/img/feed_fullsize/plain/did:plc:123/img@jpeg",
                                "alt": "A very descriptive meme alt text explaining the joke",
                            }
                        ],
                    },
                }
            ]
        }
        memes = parse_bluesky_feed(payload)
        assert len(memes) == 1
        assert memes[0].title == "A very descriptive meme alt text explaining the joke"

    def test_bluesky_metric_extremes_and_corrupt_types(self) -> None:
        """Metrics with non-int types, negative numbers, or missing keys must be handled gracefully."""
        payload = {
            "posts": [
                {
                    "uri": "at://did:plc:123/app.bsky.feed.post/metric_post",
                    "author": {"handle": "metrics.bsky.social"},
                    "record": {"text": "Metrics test"},
                    "embed": {
                        "$type": "app.bsky.embed.images#view",
                        "images": [{"fullsize": "https://cdn.bsky.app/img/feed_fullsize/plain/did:plc:123/img@jpeg"}],
                    },
                    "likeCount": "invalid_number",
                    "repostCount": 100,
                    "replyCount": None,
                }
            ]
        }
        memes = parse_bluesky_feed(payload)
        assert len(memes) == 1
        assert memes[0].score == 200  # 0 likes + 100 reposts * 2
        assert memes[0].num_comments == 0
        assert memes[0].trending_score > 0

    def test_bluesky_nsfw_labels_and_keyword_triggers(self) -> None:
        """NSFW labels (porn, sexual, nudity, graphic) or keyword flags must mark is_nsfw=True."""
        test_cases = [
            ({"labels": [{"val": "porn"}]}, "Clean title", True),
            ({"labels": [{"val": "sexual"}]}, "Clean title", True),
            ({"labels": [{"val": "nudity"}]}, "Clean title", True),
            ({"labels": [{"val": "graphic"}]}, "Clean title", True),
            ({}, "Explicit adult NSFW meme content", True),
            ({}, "Completely wholesome meme", False),
        ]
        for extra, text, expected_nsfw in test_cases:
            post = {
                "uri": "at://did:plc:123/app.bsky.feed.post/nsfw_test",
                "author": {"handle": "user.bsky.social"},
                "record": {"text": text},
                "embed": {
                    "$type": "app.bsky.embed.images#view",
                    "images": [{"fullsize": "https://cdn.bsky.app/img/feed_fullsize/plain/did:plc:123/img@jpeg"}],
                },
                **extra,
            }
            memes = parse_bluesky_feed({"posts": [post]})
            assert len(memes) == 1
            assert memes[0].is_nsfw is expected_nsfw

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status_code", [429, 403, 500, 502, 503, 504])
    async def test_bluesky_http_error_codes_fallback_to_fixtures(self, status_code: int) -> None:
        """All HTTP error responses must retry with backoff and fall back to local fixtures."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.headers = {"Retry-After": "0.001"}
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            fetcher = BlueskyFetcher(http_client=mock_client)
            memes = await fetcher.fetch_memes()
            assert len(memes) > 0
            assert all(m.source_platform == SourcePlatform.BLUESKY for m in memes)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exc",
        [
            httpx.TimeoutException("Connection timed out"),
            httpx.ConnectError("Failed to connect"),
            httpx.RemoteProtocolError("Server disconnected"),
        ],
    )
    async def test_bluesky_network_exceptions_fallback_to_fixtures(self, exc: Exception) -> None:
        """Network exceptions must gracefully fall back to local fixtures."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=exc)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            fetcher = BlueskyFetcher(http_client=mock_client)
            memes = await fetcher.fetch_memes()
            assert len(memes) > 0
            assert all(m.source_platform == SourcePlatform.BLUESKY for m in memes)


# ==============================================================================
# 2. MASTODON ADVERSARIAL TESTS
# ==============================================================================

class TestMastodonAdversarial:
    """Stress tests for Mastodon Fediverse parser and fetcher."""

    @pytest.mark.parametrize(
        "bad_payload",
        [
            "",
            "   ",
            "not-json-content",
            "{broken",
            "123",
            "null",
            "[]",
            "[null, 123, 'str', {}]",
            '{"items": null}',
            '{"items": [null, {}]}',
        ],
    )
    def test_mastodon_malformed_json_inputs(self, bad_payload: str) -> None:
        """Parser must handle invalid JSON and payloads gracefully."""
        results = parse_mastodon_timeline(bad_payload)
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.parametrize(
        "status_data",
        [
            {},  # empty
            {"id": ""},  # no id
            {"id": "123", "media_attachments": []},  # no media
            {"id": "123", "media_attachments": None},
            {"id": "123", "media_attachments": [{}]},
            {"id": "123", "media_attachments": [{"url": ""}]},
        ],
    )
    def test_mastodon_missing_or_corrupted_media_ignored(self, status_data: Dict[str, Any]) -> None:
        """Statuses with no valid direct image/video/gif attachment must be ignored."""
        fetcher = MastodonFetcher()
        meme = fetcher.parse_status_dict(status_data)
        assert meme is None

    def test_mastodon_html_stripping_and_whitespace_normalization(self) -> None:
        """Complex HTML tags, breaks, entities, and excessive whitespace must be normalized."""
        complex_html = """
        <p>First paragraph with <a href="https://example.com">link</a>.</p>
        <p>Second paragraph with &amp; &lt;b&gt;bold&lt;/b&gt; &amp; &quot;quotes&quot;.</p>
        <br/><br/>
        <blockquote>Quoted text</blockquote>
        """
        cleaned = strip_html_tags(complex_html)
        assert "<p>" not in cleaned
        assert "<a" not in cleaned
        assert "<blockquote>" not in cleaned
        assert "&amp;" not in cleaned
        assert "&" in cleaned
        assert '"quotes"' in cleaned
        assert "  " not in cleaned  # no consecutive spaces

    def test_mastodon_author_handles_and_instance_attribution(self) -> None:
        """Author attribution must handle local vs remote federated accounts cleanly."""
        test_cases = [
            ({"account": {"username": "local_user", "acct": "local_user"}}, "@local_user@mastodon.social"),
            ({"account": {"username": "remote_user", "acct": "remote_user@remote.instance"}}, "@remote_user@remote.instance"),
            ({"account": {"username": "anon", "acct": ""}}, "@anon@mastodon.social"),
            ({"account": None}, "@anonymous@mastodon.social"),
        ]
        fetcher = MastodonFetcher(instance_url="mastodon.social")
        for payload, expected_author in test_cases:
            status = {
                "id": "1001",
                "content": "<p>Test meme</p>",
                "media_attachments": [{"url": "https://files.mastodon.social/img.png", "type": "image"}],
                **payload,
            }
            meme = fetcher.parse_status_dict(status)
            assert meme is not None
            assert meme.author == expected_author

    def test_mastodon_media_type_detection_variants(self) -> None:
        """Media type detection must correctly classify images, gifs, gifvs, and videos."""
        cases = [
            ({"type": "image", "url": "https://files.mastodon.social/pic.jpg"}, MediaType.IMAGE),
            ({"type": "image", "url": "https://files.mastodon.social/pic.png"}, MediaType.IMAGE),
            ({"type": "image", "url": "https://files.mastodon.social/pic.webp"}, MediaType.IMAGE),
            ({"type": "gifv", "url": "https://files.mastodon.social/anim.mp4"}, MediaType.VIDEO),
            ({"type": "video", "url": "https://files.mastodon.social/clip.mp4"}, MediaType.VIDEO),
            ({"type": "gif", "url": "https://files.mastodon.social/anim.gif"}, MediaType.GIF),
            ({"type": "unknown", "url": "https://files.mastodon.social/anim.gifv"}, MediaType.VIDEO),
        ]
        fetcher = MastodonFetcher()
        for att, expected_type in cases:
            status = {
                "id": "1002",
                "content": "<p>Test meme</p>",
                "media_attachments": [att],
            }
            meme = fetcher.parse_status_dict(status)
            assert meme is not None
            assert meme.media_type == expected_type

    def test_mastodon_spoiler_and_description_fallback_titles(self) -> None:
        """When content HTML is empty, title should fall back to spoiler_text, then media description."""
        fetcher = MastodonFetcher()

        # Spoiler text fallback
        status1 = {
            "id": "2001",
            "content": "",
            "spoiler_text": "CW: Spoilers for Friday meme",
            "media_attachments": [{"url": "https://files.mastodon.social/img.jpg", "type": "image"}],
        }
        m1 = fetcher.parse_status_dict(status1)
        assert m1 is not None
        assert m1.title == "CW: Spoilers for Friday meme"

        # Media description fallback
        status2 = {
            "id": "2002",
            "content": "",
            "spoiler_text": "",
            "media_attachments": [
                {
                    "url": "https://files.mastodon.social/img.jpg",
                    "type": "image",
                    "description": "Image description fallback title",
                }
            ],
        }
        m2 = fetcher.parse_status_dict(status2)
        assert m2 is not None
        assert m2.title == "Image description fallback title"

    def test_mastodon_sensitive_and_nsfw_tags(self) -> None:
        """Sensitive flag, NSFW tags, or keyword triggers must mark is_nsfw=True."""
        test_cases = [
            ({"sensitive": True}, False, True),
            ({"sensitive": False, "tags": [{"name": "nsfw"}]}, False, True),
            ({"sensitive": False, "tags": [{"name": "sensitive"}]}, False, True),
            ({"sensitive": False, "tags": [{"name": "meme"}]}, True, True),  # via keyword in content
            ({"sensitive": False, "tags": [{"name": "meme"}]}, False, False),
        ]
        fetcher = MastodonFetcher()
        for extra, has_nsfw_keyword, expected_nsfw in test_cases:
            content = "<p>Explicit nsfw content</p>" if has_nsfw_keyword else "<p>Wholesome toot</p>"
            status = {
                "id": "3001",
                "content": content,
                "media_attachments": [{"url": "https://files.mastodon.social/img.png", "type": "image"}],
                **extra,
            }
            meme = fetcher.parse_status_dict(status)
            assert meme is not None
            assert meme.is_nsfw is expected_nsfw

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status_code", [429, 403, 500, 502, 503, 504])
    async def test_mastodon_http_error_codes_fallback_to_fixtures(self, status_code: int) -> None:
        """HTTP error responses on all instance endpoints must retry and fall back to fixtures."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.headers = {"Retry-After": "0.001"}
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            fetcher = MastodonFetcher(http_client=mock_client)
            memes = await fetcher.fetch_memes()
            assert len(memes) > 0
            assert all(m.source_platform == SourcePlatform.MASTODON for m in memes)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exc",
        [
            httpx.TimeoutException("Mastodon timed out"),
            httpx.ConnectError("Mastodon connection failed"),
            httpx.RemoteProtocolError("Protocol error"),
        ],
    )
    async def test_mastodon_network_exceptions_fallback_to_fixtures(self, exc: Exception) -> None:
        """Network exceptions on Mastodon instances must fall back to fixtures cleanly."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=exc)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            fetcher = MastodonFetcher(http_client=mock_client)
            memes = await fetcher.fetch_memes()
            assert len(memes) > 0
            assert all(m.source_platform == SourcePlatform.MASTODON for m in memes)


# ==============================================================================
# 3. ZERO-MOCK AND AUTHENTIC DATASET VERIFICATION
# ==============================================================================

class TestZeroMockAndAuthenticDatasets:
    """Verifies that fixtures and live datasets contain 100% authentic items with no fakes."""

    def test_zero_unsplash_or_synthetic_domains_in_fixtures(self) -> None:
        """All fixture JSON files in data/fixtures/ must have zero synthetic fakes or stock photos."""
        fixtures_dir = Path("data/fixtures")
        assert fixtures_dir.exists(), "data/fixtures directory must exist"

        fixture_files = list(fixtures_dir.glob("*.json"))
        assert len(fixture_files) >= 4, "Must have fixtures for all platforms"

        banned_domains = [
            "images.unsplash.com",
            "unsplash.com",
            "example.com",
            "fake.com",
            "mock.local",
            "placeholder.com",
        ]

        for fix in fixture_files:
            content = fix.read_text(encoding="utf-8")
            for banned in banned_domains:
                assert banned not in content, f"Found banned mock domain '{banned}' in fixture {fix.name}"

    def test_live_harvested_dataset_integrity(self) -> None:
        """data/live_harvested_memes.json must contain authentic items across all 4 platforms."""
        dataset_path = Path("data/live_harvested_memes.json")
        assert dataset_path.exists(), "live_harvested_memes.json must exist"

        data = json.loads(dataset_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) >= 80, f"Expected at least 80 authentic memes, found {len(data)}"

        platforms = set()
        for item in data:
            # Model validation roundtrip
            meme = Meme.model_validate(item)
            platforms.add(meme.source_platform)

            # Assert valid URL and permalink
            assert meme.media_url.startswith("http://") or meme.media_url.startswith("https://")
            assert meme.permalink.startswith("http://") or meme.permalink.startswith("https://")
            assert meme.author != ""
            assert "unsplash.com" not in meme.media_url

        # Must span all 4 required platforms
        assert {
            SourcePlatform.REDDIT,
            SourcePlatform.BLUESKY,
            SourcePlatform.KNOWYOURMEME,
            SourcePlatform.MASTODON,
        }.issubset(platforms)


# ==============================================================================
# 4. WORKER CONCURRENCY AND FAULT ISOLATION STRESS TESTS
# ==============================================================================

@pytest.mark.asyncio
class TestWorkerConcurrencyAndFaultIsolation:
    """Stress tests for multi-source polling worker under failure scenarios."""

    async def test_worker_survives_all_sources_exploding(self) -> None:
        """Worker must not crash or leave broken state when all sources throw exceptions."""
        store = MemoryStore()

        f1 = AsyncMock(spec=BaseSourceFetcher)
        f1.name = "reddit:failing"
        f1.status = store.get_sources()[0]
        f1.fetch_memes = AsyncMock(side_effect=RuntimeError("Reddit crashed"))
        f1.update_failure = MagicMock()

        f2 = AsyncMock(spec=BaseSourceFetcher)
        f2.name = "bluesky:failing"
        f2.status = store.get_sources()[0]
        f2.fetch_memes = AsyncMock(side_effect=httpx.TimeoutException("Bluesky timed out"))
        f2.update_failure = MagicMock()

        f3 = AsyncMock(spec=BaseSourceFetcher)
        f3.name = "mastodon:failing"
        f3.status = store.get_sources()[0]
        f3.fetch_memes = AsyncMock(side_effect=Exception("Mastodon network down"))
        f3.update_failure = MagicMock()

        worker = MemePollingWorker(memory_store=store, fetchers=[f1, f2, f3])
        results = await worker.fetch_all_sources()
        assert results == []
        assert f1.update_failure.called
        assert f2.update_failure.called
        assert f3.update_failure.called

        poll_res = await worker.poll_once()
        assert poll_res["status"] == "ok"
        assert poll_res["new_items"] == 0

    async def test_worker_multi_platform_deduplication_and_score_persistence(self, temp_sqlite_db: str) -> None:
        """Worker updates must preserve and maximize engagement across duplicate media items."""
        sqlite = SqliteStore(database_path=temp_sqlite_db)
        await sqlite.initialize()
        store = MemoryStore()

        worker = MemePollingWorker(memory_store=store, sqlite_store=sqlite)

        # Batch 1: lower score
        m1 = NormalizedMeme(
            id="reddit_r1",
            raw_id="r1",
            title="Viral Cross-Platform Meme",
            media_url="https://i.redd.it/viral_shared.jpg",
            media_type=MediaType.IMAGE,
            source_platform=SourcePlatform.REDDIT,
            source_community="r/memes",
            permalink="https://reddit.com/r/memes/comments/r1",
            author="u/redditor",
            score=100,
            num_comments=10,
            created_at=time.time() - 3600,
            content_hash="shared_content_hash_12345",
        )

        with patch.object(worker, "fetch_all_sources", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [m1]
            await worker.poll_once()
            assert store.count() == 1
            stored = store.get_by_id("reddit_r1")
            assert stored is not None
            assert stored.score == 100

        # Batch 2: same content hash posted to Bluesky with higher engagement
        m2 = NormalizedMeme(
            id="bluesky_b1",
            raw_id="b1",
            title="Viral Cross-Platform Meme",
            media_url="https://i.redd.it/viral_shared.jpg",
            media_type=MediaType.IMAGE,
            source_platform=SourcePlatform.BLUESKY,
            source_community="meme",
            permalink="https://bsky.app/profile/user.bsky.social/post/b1",
            author="@user.bsky.social",
            score=5000,
            num_comments=300,
            created_at=time.time() - 1800,
            content_hash="shared_content_hash_12345",
        )

        with patch.object(worker, "fetch_all_sources", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [m2]
            await worker.poll_once()

            # Store deduplicates by content hash or URL
            assert store.count() == 1
            stored = store.get_by_id("reddit_r1")
            assert stored is not None
            assert stored.score == 5000  # Updated to max engagement

        await sqlite.close()
