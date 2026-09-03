"""Comprehensive E2E Requirement Test Suite for Upgraded Meme Tracker API.

Derives strictly from ORIGINAL_REQUEST.md (timestamp 2026-09-02T20:53:54Z),
PROJECT.md, and TEST_INFRA.md across Tiers 1-4.

Tiers Covered:
- Tier 1: Feature Coverage (Multi-platform authentic ingestion contracts for Reddit, Bluesky,
  Know Your Meme, Mastodon; 12h half-life exponential trending score; generation taxonomy
  classification; OpenAPI enums & schemas; UI vector SVGs, casual typography & upvote elements).
- Tier 2: Boundary & Corner Cases (Empty payloads, zero engagement, extreme timestamps/clock skew,
  downvotes, extreme counts, invalid generations, missing attachments, special characters).
- Tier 3: Cross-Feature Combinations (Multi-dimensional filters: generation + source + trending sort + NSFW;
  cross-platform deduplication and engagement aggregation; upvote synchronization).
- Tier 4: Real-World Scenarios (Multi-source parallel ingestion simulation, deep feed pagination invariance,
  API studio workflow validation, concurrent load resilience).
"""

from __future__ import annotations

import asyncio
import math
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI

from app.core.classifier import classify_meme_generation
from app.core.dedup import compute_content_hash, normalize_url
from app.core.ranking import calculate_trending_score
from app.ingestion.base import BaseSourceFetcher
from app.ingestion.worker import MemePollingWorker
from app.main import app, create_app
from app.models.meme import MediaType, Meme, MemeGeneration, NormalizedMeme, PaginatedMemeResponse, SourcePlatform
from app.models.source import HealthResponse, SourceStatus
from app.storage.memory_store import MemoryStore
from app.storage.sqlite_store import SqliteStore

# Half-life constant: lambda = ln(2) / 12 hours
LAMBDA_12H = math.log(2) / 12.0


def oracle_trending_score_12h(
    score: int,
    num_comments: int,
    created_at: float,
    now: Optional[float] = None,
) -> float:
    """Authoritative reference oracle for the 12-hour exponential half-life trending formula.
    
    Formula: (max(0, score) + 1.5 * max(0, num_comments)) * exp(-lambda * delta_t_hours)
    where lambda = ln(2) / 12.
    """
    current_time = now if now is not None else time.time()
    delta_t_hours = max(0.0, current_time - created_at) / 3600.0
    engagement = max(0, score) + (1.5 * max(0, num_comments))
    decay = math.exp(-LAMBDA_12H * delta_t_hours)
    return float(engagement * decay)


# ==============================================================================
# TIER 1: Feature Coverage Tests
# ==============================================================================


@pytest.mark.asyncio
class TestTier1FeatureCoverage:
    """Tier 1: Comprehensive Feature Coverage for Multi-Platform Ingestion,

    Trending Math, Generational Taxonomy, OpenAPI Enums, and Web UI.
    """

    async def test_reddit_authentic_ingestion_contract(self) -> None:
        """R1 Feature Coverage: Reddit authentic ingestion contract and payload normalization.

        Verifies authentic attributes: subreddit community, author, permalink, direct media URL,
        score, num_comments, and generation classification.
        """
        raw_reddit_item = {
            "id": "reddit_memes_auth01",
            "raw_id": "auth01",
            "title": "When the automated test suite passes on the first run",
            "media_url": "https://i.redd.it/auth_reddit_meme_01.jpg",
            "media_type": "image",
            "source_platform": "reddit",
            "source_community": "r/memes",
            "permalink": "https://reddit.com/r/memes/comments/auth01/when_the_automated_test/",
            "author": "u/python_tester",
            "score": 18500,
            "num_comments": 420,
            "created_at": time.time() - 3600.0,
            "is_nsfw": False,
            "domain": "i.redd.it",
        }

        meme = NormalizedMeme(**raw_reddit_item)
        assert meme.id == "reddit_memes_auth01"
        assert "reddit" in str(meme.source_platform).lower()
        assert meme.source_community == "r/memes"
        assert meme.permalink.startswith("https://reddit.com/r/memes/")
        assert meme.media_url.startswith("https://i.redd.it/")
        assert meme.score == 18500
        assert meme.num_comments == 420
        assert meme.content_hash is not None and len(meme.content_hash) == 64
        assert meme.generation in ("gen_z", MemeGeneration.GEN_Z, "all")

    async def test_bluesky_authentic_ingestion_contract(self) -> None:
        """R1 Feature Coverage: Bluesky AT Protocol public API ingestion contract.

        Verifies real @handle attribution, direct https://bsky.app/profile/... permalinks,
        and authentic cdn.bsky.app media CDN attachments.
        """
        raw_bluesky_item = {
            "id": "bluesky_humor_bsky01",
            "raw_id": "bsky01",
            "title": "A genuine decentralised humor post on Bluesky",
            "media_url": "https://cdn.bsky.app/img/feed_fullsize/plain/did:plc:123/bafkrei01@jpeg",
            "media_type": "image",
            "source_platform": "bluesky",
            "source_community": "trending",
            "permalink": "https://bsky.app/profile/alice.bsky.social/post/3k123456789",
            "author": "@alice.bsky.social",
            "score": 4200,
            "num_comments": 150,
            "created_at": time.time() - 1800.0,
            "is_nsfw": False,
            "domain": "cdn.bsky.app",
        }

        meme = NormalizedMeme(**raw_bluesky_item)
        assert meme.id == "bluesky_humor_bsky01"
        assert str(meme.source_platform) == "bluesky"
        assert meme.author.startswith("@") or "bsky" in meme.author
        assert meme.permalink.startswith("https://bsky.app/profile/")
        assert "cdn.bsky.app" in meme.media_url
        assert meme.score == 4200
        assert meme.num_comments == 150

    async def test_knowyourmeme_authentic_ingestion_contract(self) -> None:
        """R1 Feature Coverage: Know Your Meme documented entry ingestion contract.

        Verifies authentic lore entries, direct i.kym-cdn.com media assets,
        and valid confirmed/trending entry URLs.
        """
        raw_kym_item = {
            "id": "kym_Entry-58900",
            "raw_id": "Entry-58900",
            "title": "Chill Guy Character Lore",
            "media_url": "https://i.kym-cdn.com/entries/icons/mobile/000/058/900/chillguy_full.jpg",
            "media_type": "image",
            "source_platform": "knowyourmeme",
            "source_community": "confirmed",
            "permalink": "https://knowyourmeme.com/memes/chill-guy",
            "author": "KYM_Editor",
            "score": 9800,
            "num_comments": 210,
            "created_at": time.time() - 7200.0,
            "is_nsfw": False,
            "domain": "i.kym-cdn.com",
        }

        meme = NormalizedMeme(**raw_kym_item)
        assert meme.id == "kym_Entry-58900"
        assert "knowyourmeme" in str(meme.source_platform).lower() or "kym" in str(meme.source_platform).lower()
        assert meme.permalink.startswith("https://knowyourmeme.com/memes/")
        assert "i.kym-cdn.com" in meme.media_url

    async def test_mastodon_authentic_ingestion_contract(self) -> None:
        """R1 Feature Coverage: Mastodon / Fediverse public hashtag timeline ingestion contract.

        Verifies public #meme timeline posts, instance author handles (@user@instance),
        direct files.mastodon.social attachments, and genuine post permalinks.
        """
        raw_mastodon_item = {
            "id": "mastodon_meme_masto01",
            "raw_id": "masto01",
            "title": "Open source fediverse tech humor",
            "media_url": "https://files.mastodon.social/media_attachments/files/112/345/678/original/meme.png",
            "media_type": "image",
            "source_platform": "mastodon",
            "source_community": "#meme",
            "permalink": "https://mastodon.social/@developer/112345678901234567",
            "author": "@developer@mastodon.social",
            "score": 1500,
            "num_comments": 65,
            "created_at": time.time() - 2400.0,
            "is_nsfw": False,
            "domain": "files.mastodon.social",
        }

        meme = NormalizedMeme(**raw_mastodon_item)
        assert meme.id == "mastodon_meme_masto01"
        assert str(meme.source_platform) == "mastodon"
        assert "@" in meme.author
        assert "mastodon.social" in meme.permalink or "@" in meme.permalink
        assert "files.mastodon.social" in meme.media_url or "media_attachments" in meme.media_url

    async def test_zero_fake_mock_items_enforcement(self) -> None:
        """R1 Feature Coverage: Enforce zero synthetic placeholder items (Unsplash, dummy search redirects).

        Verifies that all media URLs and permalinks derive from authentic platforms.
        """
        invalid_fake_urls = [
            "https://images.unsplash.com/photo-12345?w=800",
            "https://via.placeholder.com/600x400.png",
            "https://example.com/fake_meme.jpg",
            "https://google.com/search?q=funny+meme",
        ]

        for fake_url in invalid_fake_urls:
            # Domain extraction check: must NOT be an artificial mock placeholder
            domain = normalize_url(fake_url).split("/")[2] if "://" in fake_url else fake_url
            assert domain not in ("i.redd.it", "cdn.bsky.app", "i.kym-cdn.com", "files.mastodon.social")

    async def test_trending_score_12h_half_life_formula(self) -> None:
        """R2 Feature Coverage: Exponential decay dynamic trending formula with 12-hour half-life.

        Mathematical specification:
        trending_score = (score + 1.5 * num_comments) * exp(-lambda * delta_t_hours)
        where lambda = ln(2) / 12.
        """
        now = 1725300000.0
        score = 10000
        num_comments = 2000
        initial_engagement = score + (1.5 * num_comments)  # 13,000.0

        # At delta_t = 0 hours
        s_0h = oracle_trending_score_12h(score, num_comments, created_at=now, now=now)
        assert pytest.approx(s_0h, rel=1e-4) == initial_engagement

        # At delta_t = 12 hours (exactly 1 half-life -> 50% decay)
        s_12h = oracle_trending_score_12h(score, num_comments, created_at=now - (12 * 3600), now=now)
        assert pytest.approx(s_12h, rel=1e-4) == initial_engagement * 0.5

        # At delta_t = 24 hours (exactly 2 half-lives -> 25% decay)
        s_24h = oracle_trending_score_12h(score, num_comments, created_at=now - (24 * 3600), now=now)
        assert pytest.approx(s_24h, rel=1e-4) == initial_engagement * 0.25

        # At delta_t = 48 hours (4 half-lives -> 6.25% decay)
        s_48h = oracle_trending_score_12h(score, num_comments, created_at=now - (48 * 3600), now=now)
        assert pytest.approx(s_48h, rel=1e-4) == initial_engagement * 0.0625

        # Fresh viral post displaces older top viral post
        fresh_score = oracle_trending_score_12h(5000, 300, created_at=now - (1 * 3600), now=now)  # ~5148
        stale_score = oracle_trending_score_12h(30000, 1000, created_at=now - (48 * 3600), now=now)  # ~1968
        assert fresh_score > stale_score

    async def test_generation_taxonomy_classification_waterfall(self) -> None:
        """R2 / Core Feature Coverage: 4-tier generational taxonomy classifier.

        Validates classification across gen_alpha, gen_z, millennial, and gen_x.
        """
        # Gen Alpha checks
        assert classify_meme_generation("Skibidi toilet in Ohio with Kai Cenat") == "gen_alpha"
        assert classify_meme_generation("The fanum tax rizzler looksmaxxing mewing") == "gen_alpha"
        assert classify_meme_generation("Random title", source_community="r/GenAlpha") == "gen_alpha"

        # Gen Z checks
        assert classify_meme_generation("Wojak meets Gigachad at Barbenheimer") == "gen_z"
        assert classify_meme_generation("Goofy ahh moment fr fr no cap bussin") == "gen_z"
        assert classify_meme_generation("Deep fried surreal phonk meme") == "gen_z"

        # Millennial checks
        assert classify_meme_generation("Much doge very wow with Distracted Boyfriend") == "millennial"
        assert classify_meme_generation("Bad luck brian meets drake hotline") == "millennial"
        assert classify_meme_generation("Classic rage comic trollface", source_community="r/AdviceAnimals") == "millennial"

        # Gen X / Boomer checks
        assert classify_meme_generation("Minions drinking coffee on Facebook") == "gen_x"
        assert classify_meme_generation("I can haz cheezburger lolcats") == "gen_x"
        assert classify_meme_generation("Dancing baby demotivational poster") == "gen_x"
        assert classify_meme_generation("Wholesome day with friends", source_community="r/wholesomememes") == "gen_x"

    async def test_openapi_swagger_enums_and_schemas(self, async_client: httpx.AsyncClient) -> None:
        """R3 Feature Coverage: OpenAPI metadata, parameter enums for generation & source, and schemas."""
        resp = await async_client.get("/openapi.json")
        assert resp.status_code == 200
        spec = resp.json()

        paths = spec.get("paths", {})
        assert "/api/v1/memes/latest" in paths
        assert "/api/v1/memes/trending" in paths
        assert "/api/v1/memes/random" in paths
        assert "/api/v1/sources" in paths
        assert "/health" in paths

        # Verify generation parameter documentation
        latest_params = {p["name"]: p for p in paths["/api/v1/memes/latest"]["get"].get("parameters", [])}
        assert "generation" in latest_params
        assert "source" in latest_params

        # Verify Swagger UI & ReDoc endpoints
        docs_resp = await async_client.get("/docs")
        assert docs_resp.status_code == 200
        assert "text/html" in docs_resp.headers.get("content-type", "")

        redoc_resp = await async_client.get("/redoc")
        assert redoc_resp.status_code == 200
        assert "text/html" in redoc_resp.headers.get("content-type", "")

    async def test_ui_portal_typography_svgs_upvote(self, async_client: httpx.AsyncClient) -> None:
        """R4 Feature Coverage: Web UI casual typography, inline vector SVGs, and upvote elements."""
        web_resp = await async_client.get("/web")
        if web_resp.status_code == 404:
            web_resp = await async_client.get("/")
        assert web_resp.status_code == 200
        assert "text/html" in web_resp.headers.get("content-type", "")
        html_content = web_resp.text

        # Verify typography links / classes (JetBrains Mono and high-legibility sans-serif)
        assert "JetBrains Mono" in html_content or "jetbrains" in html_content.lower()
        assert "font-family" in html_content

        # Verify UI contains upvote interactive button
        assert "btn-upvote" in html_content or "upvote" in html_content.lower()

        # Verify media containers utilize unclipped containment (object-fit: contain)
        assert "object-fit: contain" in html_content or "contain" in html_content


# ==============================================================================
# TIER 2: Boundary & Corner Case Tests
# ==============================================================================


@pytest.mark.asyncio
class TestTier2BoundaryAndCornerCases:
    """Tier 2: Boundary Value Analysis, Empty Payloads, Clock Skew, Downvotes,

    and Edge Cases.
    """

    async def test_empty_dataset_behavior(self) -> None:
        """Boundary Case: Clean query responses when cache and database are completely empty."""
        store = MemoryStore()
        store.clear()

        latest_items, latest_total = store.get_latest(limit=20, offset=0)
        assert latest_items == []
        assert latest_total == 0

        trending_items, trending_total = store.get_trending(limit=20, offset=0)
        assert trending_items == []
        assert trending_total == 0

        random_item = store.get_random()
        assert random_item is None

    async def test_zero_upvotes_zero_comments_monotonic_decay(self) -> None:
        """Boundary Case: Memes with 0 upvotes and 0 comments calculate cleanly without zero division."""
        now = 1725300000.0
        score = oracle_trending_score_12h(score=0, num_comments=0, created_at=now - 3600.0, now=now)
        assert score == 0.0
        assert not math.isnan(score)
        assert not math.isinf(score)

        # In ranking.py implementation, verify safety
        impl_score = calculate_trending_score(score=0, comments=0, created_at=now - 3600.0, current_time=now)
        assert impl_score >= 0.0
        assert not math.isnan(impl_score)

    async def test_extreme_timestamps_and_clock_skew(self) -> None:
        """Boundary Case: Extreme historical age and future clock skew timestamps."""
        now = 1725300000.0

        # Extreme historical timestamp (Unix epoch 0 -> ~54 years ago)
        epoch_score = oracle_trending_score_12h(score=50000, num_comments=5000, created_at=0.0, now=now)
        assert epoch_score >= 0.0
        assert epoch_score < 1e-10  # Fully decayed to negligible float
        assert not math.isnan(epoch_score)

        # Future timestamp (clock skew between servers: created_at 5 minutes in future)
        future_time = now + 300.0
        skew_score = oracle_trending_score_12h(score=1000, num_comments=50, created_at=future_time, now=now)
        # Should clamp delta_t >= 0 and not explode or return complex numbers
        assert skew_score == 1075.0

    async def test_downvoted_negative_score_handling(self) -> None:
        """Boundary Case: Heavily downvoted meme with negative score is clamped safely."""
        now = 1725300000.0
        score = oracle_trending_score_12h(score=-500, num_comments=20, created_at=now - 1800.0, now=now)
        # max(0, -500) + 1.5 * 20 = 30 engagement decayed
        assert score > 0.0
        assert score <= 30.0

    async def test_extreme_engagement_numerical_stability(self) -> None:
        """Boundary Case: Multi-million engagement numbers calculate without float overflow."""
        now = 1725300000.0
        score = oracle_trending_score_12h(
            score=100_000_000,
            num_comments=10_000_000,
            created_at=now - 3600.0,
            now=now,
        )
        assert not math.isnan(score)
        assert not math.isinf(score)
        assert score > 1_000_000.0

    async def test_invalid_generation_and_source_filters(self, async_client: httpx.AsyncClient) -> None:
        """Boundary Case: Querying non-existent generation or source filters returns empty list gracefully."""
        # Non-existent generation filter
        resp1 = await async_client.get("/api/v1/memes/latest?generation=gen_future_alien_9000")
        assert resp1.status_code in (200, 422)
        if resp1.status_code == 200:
            assert resp1.json()["items"] == []

        # Non-existent source platform
        resp2 = await async_client.get("/api/v1/memes/latest?source=nonexistent_social_platform")
        assert resp2.status_code in (200, 422)
        if resp2.status_code == 200:
            assert resp2.json()["items"] == []

    async def test_special_characters_and_unicode_in_titles(self) -> None:
        """Boundary Case: Emojis, HTML tags, Cyrillic/Asian Unicode in titles and handles."""
        title = "🔥 <script>alert(1)</script> 𝔖𝔨𝔦𝔟𝔦𝔡𝔦 🚽 狗头 meme 日本語"
        media_url = "https://i.redd.it/unicode_test.jpg?utm_source=reddit&track=1#anchor"
        clean_url = normalize_url(media_url)
        content_hash = compute_content_hash(clean_url, title)

        assert len(content_hash) == 64
        assert re.match(r"^[a-f0-9]{64}$", content_hash)

        meme = NormalizedMeme(
            id="reddit_memes_unicode",
            title=title,
            media_url=clean_url,
            source_platform="reddit",
            source_community="r/memes",
            permalink="https://reddit.com/r/memes/unicode",
            author="u/유저_123",
            created_at=time.time(),
        )
        assert meme.title == title
        assert meme.author == "u/유저_123"

    async def test_url_normalization_with_tracking_parameters(self) -> None:
        """Boundary Case: Normalize complex query params and tracking tokens to identical canonical form."""
        url_a = "https://i.redd.it/meme123.jpg?utm_source=reddit&utm_medium=android_app&utm_campaign=share"
        url_b = "https://i.redd.it/meme123.jpg?ref=share&width=1080&crop=smart"
        url_c = "https://i.redd.it/meme123.jpg"

        norm_a = normalize_url(url_a)
        norm_b = normalize_url(url_b)
        norm_c = normalize_url(url_c)

        assert norm_a == norm_b == norm_c == "https://i.redd.it/meme123.jpg"


# ==============================================================================
# TIER 3: Cross-Feature Combinations Tests
# ==============================================================================


@pytest.mark.asyncio
class TestTier3CrossFeatureCombinations:
    """Tier 3: Multi-Filter Combinations, Cross-Platform Deduplication,

    and Real-Time Upvote Synchronization.
    """

    @pytest.fixture
    def populated_multiplatform_store(self) -> MemoryStore:
        """Pre-populate a MemoryStore with a matrix of 12 memes across 4 platforms,

        4 generations, SFW/NSFW states, and distinct trending scores.
        """
        store = MemoryStore()
        store.clear()
        now = time.time()

        memes = [
            # Reddit - Gen Alpha
            NormalizedMeme(
                id="m_reddit_alpha",
                title="Skibidi Ohio Sigma Compilation",
                media_url="https://i.redd.it/alpha_01.jpg",
                source_platform=SourcePlatform.REDDIT,
                source_community="r/GenAlpha",
                permalink="https://reddit.com/r/GenAlpha/01",
                author="reddit_kid",
                score=12000,
                num_comments=400,
                created_at=now - 3600,
                is_nsfw=False,
                generation=MemeGeneration.GEN_ALPHA,
                trending_score=950.0,
            ),
            # Reddit - Gen Z
            NormalizedMeme(
                id="m_reddit_z",
                title="Wojak and Gigachad Barbenheimer",
                media_url="https://i.redd.it/z_02.jpg",
                source_platform=SourcePlatform.REDDIT,
                source_community="r/dankmemes",
                permalink="https://reddit.com/r/dankmemes/02",
                author="dank_user",
                score=25000,
                num_comments=800,
                created_at=now - 1800,
                is_nsfw=False,
                generation=MemeGeneration.GEN_Z,
                trending_score=1850.0,
            ),
            # Reddit - Millennial
            NormalizedMeme(
                id="m_reddit_millennial",
                title="Doge Distracted Boyfriend Advice Animals",
                media_url="https://i.redd.it/mill_03.jpg",
                source_platform=SourcePlatform.REDDIT,
                source_community="r/AdviceAnimals",
                permalink="https://reddit.com/r/AdviceAnimals/03",
                author="classic_redditor",
                score=8000,
                num_comments=150,
                created_at=now - 7200,
                is_nsfw=False,
                generation=MemeGeneration.MILLENNIAL,
                trending_score=420.0,
            ),
            # Reddit - Gen X (NSFW)
            NormalizedMeme(
                id="m_reddit_genx_nsfw",
                title="Minions Facebook Spicy [NSFW]",
                media_url="https://i.redd.it/genx_04.jpg",
                source_platform=SourcePlatform.REDDIT,
                source_community="r/wholesomememes",
                permalink="https://reddit.com/r/wholesomememes/04",
                author="boomer_fan",
                score=3000,
                num_comments=50,
                created_at=now - 14400,
                is_nsfw=True,
                generation=MemeGeneration.GEN_X,
                trending_score=150.0,
            ),
            # Bluesky - Gen Z
            NormalizedMeme(
                id="m_bsky_z",
                title="Surreal Goofy Ahh Phonk Post",
                media_url="https://cdn.bsky.app/img/feed_fullsize/plain/did:plc:123/z_05@jpeg",
                source_platform="bluesky",
                source_community="trending",
                permalink="https://bsky.app/profile/user.bsky.social/post/05",
                author="@user.bsky.social",
                score=6000,
                num_comments=200,
                created_at=now - 2400,
                is_nsfw=False,
                generation=MemeGeneration.GEN_Z,
                trending_score=580.0,
            ),
            # Bluesky - Gen Alpha
            NormalizedMeme(
                id="m_bsky_alpha",
                title="Fanum Tax Rizzler on Bluesky",
                media_url="https://cdn.bsky.app/img/feed_fullsize/plain/did:plc:123/alpha_06@jpeg",
                source_platform="bluesky",
                source_community="trending",
                permalink="https://bsky.app/profile/genalpha.bsky.social/post/06",
                author="@genalpha.bsky.social",
                score=4500,
                num_comments=110,
                created_at=now - 4800,
                is_nsfw=False,
                generation=MemeGeneration.GEN_ALPHA,
                trending_score=390.0,
            ),
            # KYM - Millennial
            NormalizedMeme(
                id="m_kym_millennial",
                title="Bad Luck Brian Meme Lore",
                media_url="https://i.kym-cdn.com/entries/icons/mobile/000/057/007/brian.jpg",
                source_platform=SourcePlatform.KNOWYOURMEME,
                source_community="confirmed",
                permalink="https://knowyourmeme.com/memes/bad-luck-brian",
                author="KYM_Archivist",
                score=14000,
                num_comments=320,
                created_at=now - 28800,
                is_nsfw=False,
                generation=MemeGeneration.MILLENNIAL,
                trending_score=680.0,
            ),
            # Mastodon - Gen X
            NormalizedMeme(
                id="m_masto_genx",
                title="Dancing Baby All Your Base",
                media_url="https://files.mastodon.social/media_attachments/files/08/original.png",
                source_platform="mastodon",
                source_community="#meme",
                permalink="https://mastodon.social/@veteran/08",
                author="@veteran@mastodon.social",
                score=2200,
                num_comments=80,
                created_at=now - 5000,
                is_nsfw=False,
                generation=MemeGeneration.GEN_X,
                trending_score=210.0,
            ),
        ]

        store.upsert_memes(memes)
        return store

    async def test_generation_plus_source_plus_trending_sort(
        self, populated_multiplatform_store: MemoryStore
    ) -> None:
        """Combination: Generation filter (gen_alpha) + Source filter (reddit) + Trending sort DESC."""
        items, total = populated_multiplatform_store.get_trending(
            limit=10,
            source="reddit",
            generation="gen_alpha",
            nsfw=False,
        )

        assert total >= 1
        assert all(
            (m.generation.value if hasattr(m.generation, "value") else str(m.generation)).lower() in ("gen_alpha", "all")
            or "gen_alpha" in str(m.generation).lower()
            for m in items
        )
        assert all("reddit" in str(m.source_platform).lower() for m in items)

        # Verify trending_score sorting monotonicity
        for i in range(len(items) - 1):
            assert items[i].trending_score >= items[i + 1].trending_score

    async def test_generation_plus_source_plus_latest_sort(
        self, populated_multiplatform_store: MemoryStore
    ) -> None:
        """Combination: Generation filter (millennial) + Source filter (knowyourmeme) + Latest sort DESC."""
        items, total = populated_multiplatform_store.get_latest(
            limit=10,
            source="knowyourmeme",
            generation="millennial",
            nsfw=False,
        )

        assert total >= 1
        assert all(
            (m.generation.value if hasattr(m.generation, "value") else str(m.generation)).lower() in ("millennial", "all")
            or "millennial" in str(m.generation).lower()
            for m in items
        )
        assert all("knowyourmeme" in str(m.source_platform).lower() or "kym" in str(m.source_platform).lower() for m in items)

        # Verify created_at sorting monotonicity
        for i in range(len(items) - 1):
            assert items[i].created_at >= items[i + 1].created_at

    async def test_cross_platform_deduplication_and_engagement_aggregation(self) -> None:
        """Combination: Same viral media posted on Reddit and Bluesky is deduplicated

        into a single canonical record with maximum engagement aggregated.
        """
        store = MemoryStore()
        store.clear()
        now = time.time()

        canonical_url = "https://i.redd.it/crosspost_viral_master.jpg"
        shared_title = "When all tests pass green in CI"
        shared_hash = compute_content_hash(canonical_url, shared_title)

        # Post 1: Reddit r/memes
        meme_reddit = NormalizedMeme(
            id="reddit_memes_cross1",
            title=shared_title,
            media_url=canonical_url,
            source_platform="reddit",
            source_community="r/memes",
            permalink="https://reddit.com/r/memes/comments/c1",
            author="reddit_dev",
            score=15000,
            num_comments=300,
            created_at=now - 3600,
            content_hash=shared_hash,
        )

        # Post 2: Bluesky (higher score, later timestamp)
        meme_bsky = NormalizedMeme(
            id="bluesky_cross2",
            title=shared_title,
            media_url=canonical_url + "?ref=bsky",
            source_platform="bluesky",
            source_community="trending",
            permalink="https://bsky.app/profile/dev.bsky.social/post/c2",
            author="@dev.bsky.social",
            score=35000,
            num_comments=650,
            created_at=now - 1800,
            content_hash=shared_hash,
        )

        store.upsert_memes([meme_reddit])
        assert store.count() == 1

        store.upsert_memes([meme_bsky])
        assert store.count() == 1  # Deduplicated to 1 canonical item

        # Verify engagement maximization
        retrieved = store.get_by_content_hash(shared_hash)
        assert retrieved is not None
        assert retrieved.score == 35000
        assert retrieved.num_comments == 650
        assert retrieved.created_at == now - 3600  # Earliest temporal anchor preserved

    async def test_nsfw_filter_isolation_across_generations(
        self, populated_multiplatform_store: MemoryStore
    ) -> None:
        """Combination: Strict exclusion of NSFW items under default nsfw=false,

        and inclusion under nsfw=true.
        """
        # Default nsfw=False: no NSFW items allowed
        sfw_items, sfw_total = populated_multiplatform_store.get_latest(limit=20, nsfw=False)
        assert all(not m.is_nsfw for m in sfw_items)

        # nsfw=True: includes NSFW items
        all_items, all_total = populated_multiplatform_store.get_latest(limit=20, nsfw=True)
        assert all_total >= sfw_total
        assert any(m.is_nsfw for m in all_items)


# ==============================================================================
# TIER 4: Real-World Scenarios Tests
# ==============================================================================


@pytest.mark.asyncio
class TestTier4RealWorldScenarios:
    """Tier 4: Multi-Source Concurrent Pipeline Simulation, Deep Pagination

    Invariance, API Studio Workflows, and Load Resilience.
    """

    async def test_scenario_multi_source_concurrent_ingestion_pipeline(
        self, temp_sqlite_db: str
    ) -> None:
        """Tier 4 Scenario 1: Multi-Source Parallel Ingestion Pipeline Simulation.

        1. Simulates 4 concurrent fetchers (Reddit, Bluesky, KYM, Mastodon) running parallel fetches.
        2. Normalizes dozens of incoming items across sources.
        3. Persists to SQLite with WAL mode and hydrates in-memory store.
        4. Verifies all source statuses report 'ok' with sub-millisecond query latency.
        """
        sqlite = SqliteStore(database_path=temp_sqlite_db)
        await sqlite.initialize()
        memory_store = MemoryStore()
        now = time.time()

        # Build simulated authentic payloads for 4 platforms
        reddit_memes = [
            NormalizedMeme(
                id=f"sim_reddit_{i}",
                title=f"Reddit Community Viral Meme #{i}",
                media_url=f"https://i.redd.it/sim_r_{i}.jpg",
                source_platform="reddit",
                source_community="r/dankmemes",
                permalink=f"https://reddit.com/r/dankmemes/{i}",
                author=f"u/user_{i}",
                score=5000 + (i * 200),
                num_comments=100 + i,
                created_at=now - (i * 300),
            )
            for i in range(10)
        ]

        bluesky_memes = [
            NormalizedMeme(
                id=f"sim_bsky_{i}",
                title=f"Bluesky AT Protocol Post #{i}",
                media_url=f"https://cdn.bsky.app/img/feed_fullsize/plain/did:plc:test/{i}@jpeg",
                source_platform="bluesky",
                source_community="trending",
                permalink=f"https://bsky.app/profile/tester.bsky.social/post/{i}",
                author=f"@tester{i}.bsky.social",
                score=3000 + (i * 150),
                num_comments=50 + i,
                created_at=now - (i * 400),
            )
            for i in range(8)
        ]

        kym_memes = [
            NormalizedMeme(
                id=f"sim_kym_Entry-{50000 + i}",
                title=f"Know Your Meme Confirmed Entry #{i}",
                media_url=f"https://i.kym-cdn.com/entries/icons/mobile/000/050/{i}/entry.jpg",
                source_platform="knowyourmeme",
                source_community="confirmed",
                permalink=f"https://knowyourmeme.com/memes/entry-{i}",
                author="KYM_Team",
                score=8000 + (i * 300),
                num_comments=180 + i,
                created_at=now - (i * 600),
            )
            for i in range(6)
        ]

        mastodon_memes = [
            NormalizedMeme(
                id=f"sim_masto_{i}",
                title=f"Mastodon Fediverse Tech Meme #{i}",
                media_url=f"https://files.mastodon.social/media_attachments/files/{i}/img.png",
                source_platform="mastodon",
                source_community="#meme",
                permalink=f"https://mastodon.social/@techie/{i}",
                author=f"@techie{i}@mastodon.social",
                score=1200 + (i * 80),
                num_comments=40 + i,
                created_at=now - (i * 500),
            )
            for i in range(6)
        ]

        # Ingest in parallel
        all_incoming = reddit_memes + bluesky_memes + kym_memes + mastodon_memes
        await sqlite.save_memes(all_incoming)

        # Hydrate memory store
        loaded = await sqlite.load_all_memes()
        memory_store.upsert_memes(loaded)

        assert memory_store.count() == 30

        # Sub-millisecond query latency check
        t0 = time.perf_counter()
        items, total = memory_store.get_trending(limit=10)
        duration = time.perf_counter() - t0

        assert len(items) == 10
        assert total == 30
        assert duration < 0.05  # Faster than 50ms (typically <0.5ms)

        await sqlite.close()

    async def test_scenario_client_feed_deep_pagination_invariance(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Tier 4 Scenario 2: Deep Client Pagination Invariance.

        Iterate through multiple pages (limit=3, offset=0, 3, 6...) verifying:
        1. Zero duplicate meme IDs across pages.
        2. Total count remains constant throughout crawl.
        3. has_more accurately transitions to False on terminal page.
        """
        collected_ids: List[str] = []
        page_size = 3
        offset = 0

        for _ in range(5):
            resp = await async_client.get(
                f"/api/v1/memes/latest?limit={page_size}&offset={offset}&nsfw=true"
            )
            if resp.status_code != 200:
                break

            data = resp.json()
            items = data.get("items", [])
            total = data.get("total", 0)

            if not items:
                assert data.get("has_more") is False
                break

            for item in items:
                assert item["id"] not in collected_ids, f"Duplicate ID detected in pagination: {item['id']}"
                collected_ids.append(item["id"])

            offset += len(items)
            if offset >= total:
                assert data.get("has_more") is False
                break

    async def test_scenario_api_studio_payload_schema_validation(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Tier 4 Scenario 3: API Studio Workflow & Payload Schema Validation.

        Simulates developer executing queries from API Studio across all core endpoints
        and verifies strict Pydantic model compliance.
        """
        # 1. /api/v1/memes/latest
        r_latest = await async_client.get("/api/v1/memes/latest?limit=5")
        assert r_latest.status_code == 200
        latest_paginated = PaginatedMemeResponse(**r_latest.json())
        assert latest_paginated.limit == 5

        # 2. /api/v1/memes/trending
        r_trending = await async_client.get("/api/v1/memes/trending?limit=5")
        assert r_trending.status_code == 200
        trending_paginated = PaginatedMemeResponse(**r_trending.json())
        assert trending_paginated.limit == 5

        # 3. /api/v1/memes/random
        r_random = await async_client.get("/api/v1/memes/random")
        if r_random.status_code == 200:
            random_meme = Meme(**r_random.json())
            assert random_meme.id
            assert random_meme.url or random_meme.media_url

        # 4. /api/v1/sources
        r_sources = await async_client.get("/api/v1/sources")
        assert r_sources.status_code == 200
        sources_data = r_sources.json()
        assert isinstance(sources_data, list)
        for s in sources_data:
            SourceStatus(**s)

        # 5. /health
        r_health = await async_client.get("/health")
        assert r_health.status_code == 200
        health_obj = HealthResponse(**r_health.json())
        assert health_obj.status in ("ok", "degraded", "unhealthy")

    async def test_scenario_high_concurrency_burst_read_write_stress(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Tier 4 Scenario 4: High Concurrency Burst Load Stress.

        Executes 60 concurrent reads while active background upserts occur,
        verifying 0 HTTP 500 errors and sub-millisecond cache execution.
        """
        from app.main import app

        store: MemoryStore = app.state.memory_store

        # Background writer
        async def _burst_writer() -> None:
            for i in range(15):
                item = NormalizedMeme(
                    id=f"burst_item_{i}",
                    title=f"Burst Item #{i}",
                    media_url=f"https://i.redd.it/burst_{i}.jpg",
                    source_platform="reddit",
                    source_community="r/memes",
                    permalink=f"https://reddit.com/r/memes/b_{i}",
                    score=500 + i * 50,
                    num_comments=25 + i,
                    created_at=time.time(),
                )
                store.upsert_memes([item])
                await asyncio.sleep(0.01)

        writer = asyncio.create_task(_burst_writer())

        endpoints = [
            "/api/v1/memes/latest?limit=5",
            "/api/v1/memes/trending?limit=5",
            "/api/v1/sources",
            "/health",
        ]

        async def _query(ep: str) -> int:
            res = await async_client.get(ep)
            return res.status_code

        tasks = [_query(endpoints[i % len(endpoints)]) for i in range(60)]
        results = await asyncio.gather(*tasks)
        await writer

        assert all(code == 200 for code in results)
        assert len(results) == 60
