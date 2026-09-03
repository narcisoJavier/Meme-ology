"""Unit tests for Bluesky AT Protocol public API meme feed extraction."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.ingestion.bluesky import BlueskyFetcher, parse_bluesky_feed, parse_iso8601_date
from app.models.meme import MediaType, NormalizedMeme, SourcePlatform


@pytest.fixture
def raw_bluesky_search_json() -> str:
    """Fixture containing realistic Bluesky AT Protocol XRPC search response."""
    return json.dumps({
        "posts": [
          {
            "uri": "at://did:plc:ragtjsm2j2vknwk6zax4oxfa/app.bsky.feed.post/3muktgcsm4k2m",
            "cid": "bafyreih3vptd7pczv6r2eomf5z36e7r73z5l77g7l5o2q3r5g2k4m3y",
            "author": {
              "did": "did:plc:ragtjsm2j2vknwk6zax4oxfa",
              "handle": "strykie187.bsky.social",
              "displayName": "Strykie",
              "avatar": "https://cdn.bsky.app/img/avatar/plain/did:plc:ragtjsm2j2vknwk6zax4oxfa/bafkreic7x6h3k4y@jpeg"
            },
            "record": {
              "$type": "app.bsky.feed.post",
              "createdAt": "2026-09-02T19:30:00.000Z",
              "text": "When you refactor 1 line of CSS and 497 automated tests unexpectedly pass #dev #meme",
              "embed": {
                "$type": "app.bsky.embed.images",
                "images": [
                  {
                    "alt": "Relieved developer watching green build pipeline",
                    "image": {
                      "$type": "blob",
                      "ref": {"$link": "bafkreibx7y7x3m6m6g2w4r3q7m7w6l5y3r5g2k4m3y"},
                      "mimeType": "image/jpeg",
                      "size": 182340
                    }
                  }
                ]
              }
            },
            "embed": {
              "$type": "app.bsky.embed.images#view",
              "images": [
                {
                  "thumb": "https://cdn.bsky.app/img/feed_thumbnail/plain/did:plc:ragtjsm2j2vknwk6zax4oxfa/bafkreibx7y7x3m6m6g2w4r3q7m7w6l5y3r5g2k4m3y@jpeg",
                  "fullsize": "https://cdn.bsky.app/img/feed_fullsize/plain/did:plc:ragtjsm2j2vknwk6zax4oxfa/bafkreibx7y7x3m6m6g2w4r3q7m7w6l5y3r5g2k4m3y@jpeg",
                  "alt": "Relieved developer watching green build pipeline",
                  "aspectRatio": {"height": 900, "width": 1200}
                }
              ]
            },
            "replyCount": 18,
            "repostCount": 45,
            "likeCount": 240,
            "indexedAt": "2026-09-02T19:31:00.000Z"
          },
          {
            "uri": "at://did:plc:4n7jkw6m5p7q2r3y4t6u8v9w/app.bsky.feed.post/3ldh2k3j2lk23",
            "cid": "bafyreid7x6h3k4y3vptd7pczv6r2eomf5z36e7r73z5l77g7l5o2q3r5g2k",
            "author": {
              "did": "did:plc:4n7jkw6m5p7q2r3y4t6u8v9w",
              "handle": "alice.bsky.social",
              "displayName": "Alice Tech & Humor"
            },
            "record": {
              "$type": "app.bsky.feed.post",
              "createdAt": "2026-09-02T18:45:00.000Z",
              "text": "A genuine decentralised humor post on Bluesky explaining distributed consensus protocols"
            },
            "embed": {
              "$type": "app.bsky.embed.images#view",
              "images": [
                {
                  "thumb": "https://cdn.bsky.app/img/feed_thumbnail/plain/did:plc:4n7jkw6m5p7q2r3y4t6u8v9w/bafkrei01@jpeg",
                  "fullsize": "https://cdn.bsky.app/img/feed_fullsize/plain/did:plc:123/bafkrei01@jpeg",
                  "alt": "Diagram comparing decentralized protocols with funny annotations"
                }
              ]
            },
            "replyCount": 150,
            "repostCount": 210,
            "likeCount": 4200,
            "indexedAt": "2026-09-02T18:46:00.000Z"
          }
        ]
    })


class TestBlueskyParser:
    """Tier 1 & Tier 2 tests for Bluesky AT Protocol parser."""

    def test_parse_bluesky_post_with_image_embed(self, raw_bluesky_search_json: str) -> None:
        """Verify normal AT Protocol post with image embed is correctly parsed."""
        memes = parse_bluesky_feed(raw_bluesky_search_json)
        assert len(memes) == 2

        first = next(m for m in memes if m.id == "bluesky_3muktgcsm4k2m")
        assert first.title == "When you refactor 1 line of CSS and 497 automated tests unexpectedly pass #dev #meme"
        assert first.source_platform == SourcePlatform.BLUESKY or first.source_platform == "bluesky"
        assert first.author == "@strykie187.bsky.social"
        assert first.permalink == "https://bsky.app/profile/strykie187.bsky.social/post/3muktgcsm4k2m"
        assert "cdn.bsky.app" in first.media_url
        assert first.media_type == MediaType.IMAGE
        assert first.score == 240 + (45 * 2)  # likes + reposts*2
        assert first.num_comments == 18
        assert first.created_at > 0
        assert first.is_nsfw is False

    def test_parse_bluesky_skips_text_only_posts(self) -> None:
        """Verify text posts without image/video embeds are skipped."""
        payload = {
            "posts": [
                {
                    "uri": "at://did:plc:123/app.bsky.feed.post/text123",
                    "author": {"handle": "textonly.bsky.social"},
                    "record": {"text": "Just plain text without image attachment"},
                }
            ]
        }
        memes = parse_bluesky_feed(payload)
        assert len(memes) == 0

    def test_parse_bluesky_video_embed(self) -> None:
        """Verify video embed view is parsed as MediaType.VIDEO."""
        payload = {
            "posts": [
                {
                    "uri": "at://did:plc:123/app.bsky.feed.post/vid123",
                    "author": {"handle": "animator.bsky.social"},
                    "record": {"text": "Cool animation loop"},
                    "embed": {
                        "$type": "app.bsky.embed.video#view",
                        "playlist": "https://cdn.bsky.app/video/did:plc:123/vid123/playlist.m3u8",
                        "thumbnail": "https://cdn.bsky.app/video/did:plc:123/vid123/thumb.jpg",
                    },
                    "likeCount": 100,
                    "replyCount": 5,
                }
            ]
        }
        memes = parse_bluesky_feed(payload)
        assert len(memes) == 1
        assert memes[0].media_type == MediaType.VIDEO
        assert "cdn.bsky.app" in memes[0].media_url

    def test_parse_bluesky_handles_empty_feed(self) -> None:
        """Verify empty posts/feed list returns empty list."""
        assert parse_bluesky_feed({"posts": []}) == []
        assert parse_bluesky_feed({"feed": []}) == []
        assert parse_bluesky_feed("{}") == []

    def test_parse_bluesky_handles_malformed_json(self) -> None:
        """Verify malformed JSON string does not raise unhandled exception."""
        assert parse_bluesky_feed("not-a-json-payload") == []
        assert parse_bluesky_feed("") == []

    def test_parse_iso8601_date_formats(self) -> None:
        """Verify ISO 8601 date parsing with and without Z suffix."""
        t1 = parse_iso8601_date("2026-09-02T19:30:00.000Z")
        assert t1 > 1700000000.0

        t2 = parse_iso8601_date("2026-09-02T19:30:00+00:00")
        assert t1 == t2

        t_invalid = parse_iso8601_date("invalid-date")
        assert t_invalid > 0.0

    def test_bluesky_offline_fixture_fallback(self) -> None:
        """Verify loading offline fixture from data/fixtures/bluesky_memes.json."""
        fetcher = BlueskyFetcher()
        memes = fetcher.load_offline_fixtures()
        assert len(memes) > 0
        assert all(m.source_platform == SourcePlatform.BLUESKY for m in memes)
        assert all("cdn.bsky.app" in m.media_url for m in memes)


@pytest.mark.asyncio
class TestBlueskyFetcherLiveAndResilience:
    """Tier 1 & Tier 2 tests for Bluesky live fetching and error fallback."""

    async def test_bluesky_fetch_memes_success(self, raw_bluesky_search_json: str) -> None:
        """Verify live fetch with mocked HTTP 200 response."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = raw_bluesky_search_json
        mock_client.get = AsyncMock(return_value=mock_resp)

        fetcher = BlueskyFetcher(http_client=mock_client)
        memes = await fetcher.fetch_memes()
        assert len(memes) == 2
        assert fetcher.status.status == "ok"
        assert fetcher.status.item_count == 2

    async def test_bluesky_fetch_memes_network_error_fallback(self) -> None:
        """Verify network errors fall back to offline fixtures with degraded status."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with patch("asyncio.sleep", new_callable=AsyncMock):
            fetcher = BlueskyFetcher(http_client=mock_client)
            memes = await fetcher.fetch_memes()
            assert len(memes) > 0
            assert all("cdn.bsky.app" in m.media_url for m in memes)

    async def test_bluesky_fetch_memes_http_429_backoff_and_fallback(self) -> None:
        """Verify HTTP 429 rate limit triggers backoff and falls back to fixtures."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {"Retry-After": "0.01"}
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            fetcher = BlueskyFetcher(http_client=mock_client)
            memes = await fetcher.fetch_memes()
            assert len(memes) > 0
            assert mock_sleep.called
