"""Unit tests for Mastodon public hashtag timeline meme extraction."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.ingestion.mastodon import (
    MastodonFetcher,
    parse_iso8601_date,
    parse_mastodon_timeline,
    strip_html_tags,
)
from app.models.meme import MediaType, NormalizedMeme, SourcePlatform


@pytest.fixture
def raw_mastodon_timeline_json() -> str:
    """Fixture containing realistic Mastodon Status JSON array."""
    return json.dumps([
        {
            "id": "113072034589840155",
            "created_at": "2026-09-02T19:15:00.000Z",
            "sensitive": False,
            "spoiler_text": "",
            "visibility": "public",
            "url": "https://mastodon.social/@fedimemes/113072034589840155",
            "replies_count": 8,
            "reblogs_count": 42,
            "favourites_count": 137,
            "content": "<p>When open source federated memes hit the timeline just right &lt;3 #meme #fediverse</p>",
            "account": {
                "id": "109348123",
                "username": "fedimemes",
                "acct": "fedimemes@mastodon.social",
                "display_name": "Fediverse Meme Vault",
            },
            "media_attachments": [
                {
                    "id": "2291039",
                    "type": "image",
                    "url": "https://files.mastodon.social/media_attachments/files/113/072/034/original/opensource_meme.png",
                    "preview_url": "https://files.mastodon.social/media_attachments/files/113/072/034/small/opensource_meme.png",
                    "description": "Open source diagram comparing closed vs open protocols",
                }
            ],
            "tags": [{"name": "meme"}, {"name": "fediverse"}],
        },
        {
            "id": "114088234512984711",
            "created_at": "2026-09-02T16:45:00.000Z",
            "sensitive": False,
            "spoiler_text": "",
            "visibility": "public",
            "url": "https://mastodon.online/@giflord/114088234512984711",
            "replies_count": 12,
            "reblogs_count": 55,
            "favourites_count": 310,
            "content": "<p>Me waiting for CI/CD build tests to finish running on a Friday afternoon #meme</p>",
            "account": {
                "id": "55192837",
                "username": "giflord",
                "acct": "giflord@mastodon.online",
            },
            "media_attachments": [
                {
                    "id": "4481920",
                    "type": "gifv",
                    "url": "https://files.mastodon.social/media_attachments/files/114/088/234/original/waiting_skeleton.mp4",
                    "description": "Skeleton sitting at office computer desk",
                }
            ],
        }
    ])


class TestMastodonParser:
    """Tier 1 & Tier 2 tests for Mastodon timeline parser."""

    def test_parse_mastodon_status_with_media(self, raw_mastodon_timeline_json: str) -> None:
        """Verify normal Mastodon status with media attachment is correctly parsed."""
        memes = parse_mastodon_timeline(raw_mastodon_timeline_json)
        assert len(memes) == 2

        first = next(m for m in memes if m.id == "mastodon_113072034589840155")
        assert first.title == "When open source federated memes hit the timeline just right <3 #meme #fediverse"
        assert first.source_platform == SourcePlatform.MASTODON or first.source_platform == "mastodon"
        assert first.author == "@fedimemes@mastodon.social"
        assert first.permalink == "https://mastodon.social/@fedimemes/113072034589840155"
        assert "files.mastodon.social" in first.media_url
        assert first.media_type == MediaType.IMAGE
        assert first.score == 137 + (42 * 2)  # favs + reblogs*2
        assert first.num_comments == 8
        assert first.created_at > 0
        assert first.is_nsfw is False

    def test_parse_mastodon_gifv_video_type(self, raw_mastodon_timeline_json: str) -> None:
        """Verify gifv attachment is classified as MediaType.VIDEO or GIF."""
        memes = parse_mastodon_timeline(raw_mastodon_timeline_json)
        gifv = next(m for m in memes if m.id == "mastodon_114088234512984711")
        assert gifv.media_type in (MediaType.VIDEO, MediaType.GIF)

    def test_strip_html_tags_and_unescape(self) -> None:
        """Verify HTML tags (<p>, <a>, <br>) are stripped and HTML entities unescaped."""
        raw = "<p>Check out this &amp; that &lt;3<br/>Another line</p>"
        cleaned = strip_html_tags(raw)
        assert "<p>" not in cleaned
        assert "<br/>" not in cleaned
        assert "&amp;" not in cleaned
        assert "&" in cleaned
        assert "<3" in cleaned

    def test_parse_mastodon_skips_text_only_statuses(self) -> None:
        """Verify statuses without media attachments are excluded."""
        payload = [
            {
                "id": "text_only_status",
                "content": "<p>Text only toot</p>",
                "media_attachments": [],
                "account": {"acct": "user"},
            }
        ]
        memes = parse_mastodon_timeline(payload)
        assert len(memes) == 0

    def test_parse_mastodon_sensitive_nsfw_flag(self) -> None:
        """Verify sensitive=True sets is_nsfw=True."""
        payload = [
            {
                "id": "nsfw_status",
                "content": "<p>Sensitive meme</p>",
                "sensitive": True,
                "media_attachments": [{"url": "https://files.mastodon.social/nsfw.jpg", "type": "image"}],
                "account": {"acct": "nsfw_user"},
            }
        ]
        memes = parse_mastodon_timeline(payload)
        assert len(memes) == 1
        assert memes[0].is_nsfw is True

    def test_parse_mastodon_handles_empty_timeline(self) -> None:
        """Verify empty array returns empty list."""
        assert parse_mastodon_timeline([]) == []
        assert parse_mastodon_timeline("[]") == []

    def test_parse_mastodon_handles_malformed_json(self) -> None:
        """Verify invalid JSON string does not crash parser."""
        assert parse_mastodon_timeline("invalid-json") == []

    def test_mastodon_offline_fixture_fallback(self) -> None:
        """Verify loading offline fixture from data/fixtures/mastodon_memes.json."""
        fetcher = MastodonFetcher()
        memes = fetcher.load_offline_fixtures()
        assert len(memes) > 0
        assert all(m.source_platform == SourcePlatform.MASTODON for m in memes)
        assert all("files.mastodon" in m.media_url or "mastodon" in m.domain for m in memes)


@pytest.mark.asyncio
class TestMastodonFetcherLiveAndResilience:
    """Tier 1 & Tier 2 tests for Mastodon live fetching and error fallback."""

    async def test_mastodon_fetch_memes_success(self, raw_mastodon_timeline_json: str) -> None:
        """Verify live fetch with mocked HTTP 200 response."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = raw_mastodon_timeline_json
        mock_client.get = AsyncMock(return_value=mock_resp)

        fetcher = MastodonFetcher(http_client=mock_client)
        memes = await fetcher.fetch_memes()
        assert len(memes) == 2
        assert fetcher.status.status == "ok"
        assert fetcher.status.item_count == 2

    async def test_mastodon_fetch_memes_network_error_fallback(self) -> None:
        """Verify network errors fall back to offline fixtures."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with patch("asyncio.sleep", new_callable=AsyncMock):
            fetcher = MastodonFetcher(http_client=mock_client)
            memes = await fetcher.fetch_memes()
            assert len(memes) > 0
            assert all(m.source_platform == SourcePlatform.MASTODON for m in memes)

    async def test_mastodon_fetch_memes_http_429_backoff_and_fallback(self) -> None:
        """Verify HTTP 429 rate limit triggers backoff and falls back to fixtures."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {"Retry-After": "0.01"}
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            fetcher = MastodonFetcher(http_client=mock_client)
            memes = await fetcher.fetch_memes()
            assert len(memes) > 0
            assert mock_sleep.called
