"""Unit and integration tests for location detection, language identification, content validation, and global trending radar."""

from __future__ import annotations

import time
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.classifier import is_valid_meme_content
from app.core.location import detect_language_from_text, detect_meme_location, SUPPORTED_REGIONS
from app.core.ranking import calculate_global_trending_score
from app.main import app
from app.models.meme import NormalizedMeme, SourcePlatform
from app.storage.memory_store import MemoryStore


class TestLocationAndLanguageDetection:
    """Verify accurate community-based and text-based location/language detection."""

    def test_detect_meme_location_from_german_community(self) -> None:
        country, lang = detect_meme_location(
            title="Der Moment wenn der Chef reinkommt",
            source_community="r/ich_iel",
            source_platform="reddit",
        )
        assert country == "DE"
        assert lang == "de"

    def test_detect_meme_location_from_french_community(self) -> None:
        country, lang = detect_meme_location(
            title="Moi quand je mange une baguette",
            source_community="r/rance",
            source_platform="reddit",
        )
        assert country == "FR"
        assert lang == "fr"

    def test_detect_meme_location_from_brazilian_community(self) -> None:
        country, lang = detect_meme_location(
            title="Eu tentando entender o que aconteceu no trabalho hoje",
            source_community="r/eu_nvr",
            source_platform="reddit",
        )
        assert country == "BR"
        assert lang == "pt"

    def test_detect_meme_location_from_german_text_on_generic_platform(self) -> None:
        country, lang = detect_meme_location(
            title="Warum erschießt ein Jäger alle Tiere im Rhein?",
            source_community="meme",
            source_platform="bluesky",
        )
        assert country == "DE"
        assert lang == "de"

    def test_detect_meme_location_default_global(self) -> None:
        country, lang = detect_meme_location(
            title="When you fix the bug on the first try",
            source_community="r/memes",
            source_platform="reddit",
        )
        assert country == "GLOBAL"
        assert lang == "en"

    def test_supported_regions_completeness(self) -> None:
        assert "US" in SUPPORTED_REGIONS
        assert "DE" in SUPPORTED_REGIONS
        assert "FR" in SUPPORTED_REGIONS
        assert "BR" in SUPPORTED_REGIONS
        assert "GLOBAL" in SUPPORTED_REGIONS


class TestContentValidationAndSpamFiltering:
    """Verify rejection of spam, homographs without meme intent, and hoaxes."""

    def test_reject_french_quand_meme_without_intent(self) -> None:
        title = "40M d'automobilistes quand un cycliste grille un feu rouge quand même"
        assert is_valid_meme_content(title, "https://cdn.bsky.app/img/feed_fullsize/test.jpg") is False

    def test_reject_french_meme_si_without_intent(self) -> None:
        title = "Même si en pensant grand cou, j'imaginais plus ce style"
        assert is_valid_meme_content(title, "https://cdn.bsky.app/img/feed_fullsize/test.jpg") is False

    def test_accept_french_actual_meme(self) -> None:
        # Legitimate French meme on r/rance or with meme humor intent
        title = "Un meme super drôle sur la politique française lol #humour"
        assert is_valid_meme_content(title, "https://cdn.bsky.app/img/feed_fullsize/test.jpg") is True

    def test_reject_spam_domains(self) -> None:
        assert is_valid_meme_content("Tune into FunHouseRadio.com #meme", "https://funhouseradio.com/stream") is False
        assert is_valid_meme_content("Check out totagoal.com live stream", "https://totagoal.com/match") is False

    def test_reject_obituary_hoax(self) -> None:
        title = "RIP Gloria Steinem, you will always be remembered as an inspiration"
        assert is_valid_meme_content(title, "https://cdn.bsky.app/img/feed_fullsize/test.jpg") is False


class TestGlobalTrendingRadar:
    """Verify cross-platform multiplier and velocity calculations for global trending radar."""

    def test_cross_platform_score_boost(self) -> None:
        now = time.time()
        single_platform = calculate_global_trending_score(
            score=1000,
            comments=100,
            created_at=now - 3600,
            cross_platform_count=1,
            velocity=50.0,
            current_time=now,
        )
        multi_platform = calculate_global_trending_score(
            score=1000,
            comments=100,
            created_at=now - 3600,
            cross_platform_count=3,
            velocity=50.0,
            current_time=now,
        )
        assert multi_platform > single_platform
        # 3 platforms gives a 2.0x multiplier
        assert multi_platform >= single_platform * 1.5


@pytest.mark.asyncio
class TestLocalizedAndGlobalTrendEndpoints:
    """Integration tests for GET /api/v1/memes/local and GET /api/v1/memes/trends/global."""

    async def test_get_local_memes_endpoint(self) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/memes/local?country=US")
            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data
            assert isinstance(data["items"], list)
            assert "total" in data

    async def test_get_global_trends_endpoint(self) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/memes/trends/global")
            assert resp.status_code == 200
            data = resp.json()
            assert "top_topics" in data
            assert "top_memes" in data
            assert "active_regions" in data
            assert isinstance(data["top_topics"], list)
            if data["top_topics"]:
                first = data["top_topics"][0]
                assert "topic" in first
                assert "count" in first
                assert "trending_score" in first
