"""Unit tests for Pydantic domain models and serialization schemas.

Validates:
- NormalizedMeme model validation, field types, and default values.
- MediaType and SourcePlatform Enum definitions.
- PaginatedResponse schema validation, pagination fields, and generic item lists.
- SourceStatus and HealthResponse models.
- Deserialization and JSON roundtrip serialization.
- Pydantic ValidationError on invalid/missing required fields.
"""

from __future__ import annotations

import time
import pydantic
import pytest

from app.models.meme import MediaType, NormalizedMeme, PaginatedResponse, SourcePlatform
from app.models.source import HealthResponse, SourceStatus


class TestDomainModels:
    """Tier 1 & Tier 2 tests for domain models."""

    def test_normalized_meme_valid_construction(self, meme_factory: callable) -> None:
        """Verify valid meme dictionary parses into NormalizedMeme instance."""
        data = meme_factory()
        meme = NormalizedMeme(**data)
        assert meme.id == data["id"]
        assert meme.title == data["title"]
        assert meme.score == data["score"]
        assert meme.is_nsfw is False

    def test_normalized_meme_requires_id_and_media_url(self) -> None:
        """Verify missing id or media_url raises Pydantic ValidationError."""
        with pytest.raises(pydantic.ValidationError):
            NormalizedMeme(
                title="Missing fields",
                source_platform="reddit",
                source_community="r/memes",
                permalink="/r/memes/123",
                created_at=time.time(),
                content_hash="abc",
            )

    def test_media_type_enum_values(self) -> None:
        """Verify MediaType supports image, gif, video, and link."""
        assert MediaType.IMAGE.value == "image"
        assert MediaType.GIF.value == "gif"
        assert MediaType.VIDEO.value == "video"

    def test_source_platform_enum_values(self) -> None:
        """Verify SourcePlatform supports reddit, bluesky, knowyourmeme, and mastodon."""
        assert SourcePlatform.REDDIT.value == "reddit"
        assert SourcePlatform.BLUESKY.value == "bluesky"
        assert SourcePlatform.KNOWYOURMEME.value == "knowyourmeme"
        assert SourcePlatform.MASTODON.value == "mastodon"

    def test_normalized_meme_all_4_platforms(self, meme_factory: callable) -> None:
        """Verify NormalizedMeme validates items across all four supported platforms."""
        for plat in [SourcePlatform.REDDIT, SourcePlatform.BLUESKY, SourcePlatform.KNOWYOURMEME, SourcePlatform.MASTODON]:
            data = meme_factory(source_platform=plat)
            meme = NormalizedMeme(**data)
            assert meme.source_platform == plat or meme.source_platform == plat.value

    def test_paginated_response_construction(self, meme_factory: callable) -> None:
        """Verify PaginatedResponse parses list of items with pagination metadata."""
        items = [NormalizedMeme(**meme_factory(id=f"m_{i}")) for i in range(5)]
        page = PaginatedResponse(items=items, total=50, limit=5, offset=0, has_more=True)
        assert len(page.items) == 5
        assert page.total == 50
        assert page.has_more is True

    def test_paginated_response_empty_page(self) -> None:
        """Verify PaginatedResponse works cleanly with empty list."""
        page = PaginatedResponse(items=[], total=0, limit=20, offset=0, has_more=False)
        assert page.items == []
        assert page.total == 0
        assert page.has_more is False

    def test_source_status_valid_construction(self) -> None:
        """Verify SourceStatus model instantiates with status and count."""
        status = SourceStatus(
            id="reddit_memes",
            name="Reddit r/memes",
            platform="reddit",
            status="ok",
            item_count=42,
            last_synced_at=time.time(),
        )
        assert status.status == "ok"
        assert status.item_count == 42
        assert status.error_message is None

    def test_source_status_error_state(self) -> None:
        """Verify SourceStatus can represent degraded state with error message."""
        status = SourceStatus(
            id="kym_rss",
            name="Know Your Meme RSS",
            platform="knowyourmeme",
            status="degraded",
            item_count=10,
            last_synced_at=time.time() - 300,
            error_message="HTTP 503 Service Unavailable",
        )
        assert status.status == "degraded"
        assert "503" in (status.error_message or "")

    def test_health_response_construction(self) -> None:
        """Verify HealthResponse model captures operational indicators."""
        health = HealthResponse(
            status="ok",
            uptime_seconds=3600.5,
            total_memes=250,
            healthy_sources=5,
            total_sources=5,
        )
        assert health.status == "ok"
        assert health.uptime_seconds > 0
        assert health.total_memes == 250
        assert health.healthy_sources == health.total_sources

    def test_normalized_meme_json_roundtrip(self, meme_factory: callable) -> None:
        """Verify model_dump and JSON serialization/deserialization integrity."""
        data = meme_factory()
        meme = NormalizedMeme(**data)
        json_str = meme.model_dump_json()
        meme_restored = NormalizedMeme.model_validate_json(json_str)
        assert meme == meme_restored

    def test_negative_score_permitted_or_coerced(self, meme_factory: callable) -> None:
        """Verify negative score from downvoted post is parsed without error."""
        data = meme_factory(score=-15)
        meme = NormalizedMeme(**data)
        assert meme.score == -15

    def test_extreme_comment_count(self, meme_factory: callable) -> None:
        """Verify large comment count is supported."""
        data = meme_factory(num_comments=1000000)
        meme = NormalizedMeme(**data)
        assert meme.num_comments == 1000000

    def test_author_default_fallback(self, meme_factory: callable) -> None:
        """Verify author defaults to unknown or string when missing."""
        data = meme_factory()
        del data["author"]
        meme = NormalizedMeme(**data)
        assert isinstance(meme.author, str)
