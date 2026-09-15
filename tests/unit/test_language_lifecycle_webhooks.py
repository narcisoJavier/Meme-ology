"""Unit tests for language detection, virality lifecycle calculations, and webhooks."""

import time
import pytest
from app.core.language import is_english_content
from app.core.lifecycle import (
    calculate_velocity_and_acceleration,
    classify_lifecycle_stage,
    LifecycleStage,
)
from app.core.webhooks import (
    build_discord_embed,
    build_slack_message,
    build_generic_payload,
    dispatch_viral_webhook,
)
from app.models.meme import MediaType, NormalizedMeme, SourcePlatform


def test_is_english_content_basic():
    # English meme titles
    assert is_english_content("Me when the code compiles on the first try") is True
    assert is_english_content("Bro got infinite aura in Ohio", declared_language="en") is True
    assert is_english_content("Real sigma rizz moment", declared_language=None) is True
    assert is_english_content("Why did the chicken cross the road?") is True

    # Declared non-English languages
    assert is_english_content("Hola amigos", declared_language="es") is False
    assert is_english_content("Guten Morgen", declared_language="de") is False
    assert is_english_content("Bonjour tout le monde", declared_language="fr") is False

    # Cyrillic, Arabic, CJK, etc.
    assert is_english_content("Этот мем очень смешной") is False
    assert is_english_content("هذا ميم رائع جدا") is False
    assert is_english_content("这是一个有趣的模因") is False

    # Spanish punctuation / characters
    assert is_english_content("¿Por qué pasa esto?") is False
    assert is_english_content("¡Qué buen meme!") is False

    # Foreign stopwords dominance
    assert is_english_content("el gato con botas come pan en la casa") is False


def test_calculate_velocity_and_acceleration():
    now = time.time()
    # 0 points
    v, a = calculate_velocity_and_acceleration([])
    assert v == 0.0
    assert a == 0.0

    # 1 point
    v, a = calculate_velocity_and_acceleration([(now - 3600, 100)])
    assert v == 0.0
    assert a == 0.0

    # 2 points (100 score in 1 hour -> velocity 100/hr)
    snaps_2 = [(now - 3600, 100), (now, 200)]
    v, a = calculate_velocity_and_acceleration(snaps_2)
    assert v == pytest.approx(100.0, rel=1e-2)
    assert a == 0.0

    # 3 points with acceleration (first hour: +100, second hour: +300 -> acceleration +200)
    snaps_3 = [(now - 7200, 100), (now - 3600, 200), (now, 500)]
    v, a = calculate_velocity_and_acceleration(snaps_3)
    assert v == pytest.approx(300.0, rel=1e-2)
    assert a == pytest.approx(200.0, rel=1e-2)


def test_classify_lifecycle_stage():
    now = time.time()
    # High velocity Reddit post -> VIRAL
    stage = classify_lifecycle_stage(
        velocity=1500.0,
        acceleration=100.0,
        created_at=now - 3600,
        platform="reddit",
        total_score=2000,
    )
    assert stage == LifecycleStage.VIRAL

    # Post with high score but dropping acceleration and lower velocity -> PEAK
    stage_peak = classify_lifecycle_stage(
        velocity=200.0,
        acceleration=-25.0,
        created_at=now - 7200,
        platform="reddit",
        total_score=5000,
    )
    assert stage_peak == LifecycleStage.PEAK

    # Old post with low velocity -> COOLING
    stage_cooling = classify_lifecycle_stage(
        velocity=10.0,
        acceleration=0.0,
        created_at=now - 100000,  # > 24 hours ago
        platform="reddit",
        total_score=3000,
    )
    assert stage_cooling == LifecycleStage.COOLING

    # Fresh post with moderate velocity -> EMERGING
    stage_emerging = classify_lifecycle_stage(
        velocity=400.0,
        acceleration=10.0,
        created_at=now - 1800,
        platform="reddit",
        total_score=200,
    )
    assert stage_emerging == LifecycleStage.EMERGING


def test_webhook_payload_builders():
    meme = NormalizedMeme(
        id="reddit_test123",
        title="Epic Breakout Meme",
        media_url="https://i.redd.it/epic.jpg",
        media_type=MediaType.IMAGE,
        source_platform=SourcePlatform.REDDIT,
        source_community="r/dankmemes",
        permalink="https://reddit.com/r/dankmemes/comments/test123",
        author="meme_god",
        score=15000,
        num_comments=450,
        created_at=time.time() - 3600,
        domain="i.redd.it",
        velocity=2500.0,
        acceleration=400.0,
        lifecycle_stage="viral",
    )

    discord_payload = build_discord_embed(meme)
    assert "embeds" in discord_payload
    assert "VIRAL BREAKOUT" in discord_payload["embeds"][0]["title"]
    assert discord_payload["embeds"][0]["color"] == 16729856

    slack_payload = build_slack_message(meme)
    assert "blocks" in slack_payload
    assert len(slack_payload["blocks"]) >= 2

    generic_payload = build_generic_payload(meme)
    assert generic_payload["event"] == "meme.viral_breakout"
    assert generic_payload["meme"]["velocity"] == 2500.0


@pytest.mark.asyncio
async def test_dispatch_viral_webhook_unconfigured():
    meme = NormalizedMeme(
        id="test_unconfigured_webhook",
        title="Unconfigured Test",
        media_url="https://example.com/test.jpg",
        source_community="r/dankmemes",
        created_at=time.time(),
        source_platform=SourcePlatform.REDDIT,
    )
    # No webhooks configured by default -> returns False without error
    result = await dispatch_viral_webhook(meme)
    assert result is False
