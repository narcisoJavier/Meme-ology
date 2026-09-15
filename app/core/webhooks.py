"""Webhook alerting service for instant breakout viral memes."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Set
import httpx

from app.config import get_settings
from app.models.meme import NormalizedMeme

logger = logging.getLogger(__name__)

# In-memory registry to prevent duplicate webhook alerts for the same meme
_alerted_meme_ids: Set[str] = set()


def _get_meme_fields(meme: Any) -> Tuple[str, str, str, str]:
    """Safely extract common fields across NormalizedMeme and Meme."""
    plat_raw = getattr(meme, "source_platform", getattr(meme, "source", "reddit"))
    plat_name = (plat_raw.value if hasattr(plat_raw, "value") else str(plat_raw)).capitalize()
    media_url = getattr(meme, "media_url", getattr(meme, "url", ""))
    permalink = getattr(meme, "permalink", "") or media_url
    community = getattr(meme, "source_community", "")
    return plat_name, media_url, permalink, community


def build_discord_embed(meme: Any) -> Dict[str, Any]:
    """Build a rich Discord embed for viral breakout notification."""
    platform, media_url, permalink, community = _get_meme_fields(meme)
    velocity = getattr(meme, "velocity", 0.0)
    velocity_text = f"+{velocity:,.0f}/hr" if velocity > 0 else "High Velocity"
    score_text = f"{getattr(meme, 'score', 0):,}"

    return {
        "username": "Meme Tracker Virality Radar",
        "avatar_url": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f525.png",
        "embeds": [
            {
                "title": f"🔥 VIRAL BREAKOUT: {meme.title[:180]}",
                "url": permalink,
                "description": f"A meme is rapidly spiking on **{platform}** ({community})!",
                "color": 16729856,  # Flame orange-red (0xFF4500)
                "fields": [
                    {"name": "⚡ Growth Velocity", "value": velocity_text, "inline": True},
                    {"name": "▲ Current Score", "value": score_text, "inline": True},
                    {"name": "👤 Creator", "value": getattr(meme, "author", "Unknown") or "Unknown", "inline": True},
                    {"name": "🏷️ Format", "value": "Vertical Short" if getattr(meme, "is_short", False) else str(getattr(meme, "media_type", "image")).capitalize(), "inline": True},
                ],
                "image": {"url": media_url},
                "footer": {"text": "Meme Tracker Virality Engine • Zero-AI Trend Radar"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        ],
    }


def build_slack_message(meme: Any) -> Dict[str, Any]:
    """Build a rich Slack block kit payload."""
    platform, media_url, permalink, community = _get_meme_fields(meme)
    velocity = getattr(meme, "velocity", 0.0)
    velocity_text = f"+{velocity:,.0f}/hr" if velocity > 0 else "High"

    return {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🔥 Viral Meme Breakout Alert!", "emoji": True},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*<{permalink}|{meme.title}>*\n"
                            f"• *Platform:* {platform} ({community})\n"
                            f"• *Velocity:* `{velocity_text}` | *Score:* `{getattr(meme, 'score', 0):,}`\n"
                            f"• *Author:* {getattr(meme, 'author', 'Unknown') or 'Unknown'}",
                },
                "accessory": {
                    "type": "image",
                    "image_url": media_url,
                    "alt_text": meme.title,
                },
            },
        ]
    }


def build_generic_payload(meme: Any) -> Dict[str, Any]:
    """Build a standard JSON payload for generic webhooks."""
    platform, media_url, permalink, community = _get_meme_fields(meme)
    return {
        "event": "meme.viral_breakout",
        "timestamp": time.time(),
        "meme": {
            "id": meme.id,
            "title": meme.title,
            "url": media_url,
            "permalink": permalink,
            "platform": platform.lower(),
            "community": community,
            "score": getattr(meme, "score", 0),
            "velocity": getattr(meme, "velocity", 0.0),
            "acceleration": getattr(meme, "acceleration", 0.0),
            "lifecycle_stage": getattr(meme, "lifecycle_stage", "viral"),
            "author": getattr(meme, "author", "unknown"),
            "is_short": getattr(meme, "is_short", False),
        },
    }


async def dispatch_viral_webhook(meme: NormalizedMeme) -> bool:
    """Dispatch webhook alerts to configured Discord, Slack, or generic URLs."""
    if meme.id in _alerted_meme_ids:
        return False

    settings = get_settings()
    discord_url = getattr(settings, "DISCORD_WEBHOOK_URL", None)
    slack_url = getattr(settings, "SLACK_WEBHOOK_URL", None)
    generic_url = getattr(settings, "GENERIC_WEBHOOK_URL", None)

    if not (discord_url or slack_url or generic_url):
        # No webhook configured, just mark as alerted
        _alerted_meme_ids.add(meme.id)
        return False

    _alerted_meme_ids.add(meme.id)
    success = False

    async with httpx.AsyncClient(timeout=8.0) as client:
        # Discord Webhook
        if discord_url:
            try:
                payload = build_discord_embed(meme)
                resp = await client.post(discord_url, json=payload)
                if resp.status_code in (200, 204):
                    logger.info("Dispatched Discord viral alert for meme %s", meme.id)
                    success = True
                else:
                    logger.warning("Discord webhook returned status %d", resp.status_code)
            except Exception as e:
                logger.error("Failed to send Discord webhook for meme %s: %s", meme.id, e)

        # Slack Webhook
        if slack_url:
            try:
                payload = build_slack_message(meme)
                resp = await client.post(slack_url, json=payload)
                if resp.status_code == 200:
                    logger.info("Dispatched Slack viral alert for meme %s", meme.id)
                    success = True
            except Exception as e:
                logger.error("Failed to send Slack webhook for meme %s: %s", meme.id, e)

        # Generic JSON Webhook
        if generic_url:
            try:
                payload = build_generic_payload(meme)
                resp = await client.post(generic_url, json=payload)
                if resp.status_code in (200, 201, 202, 204):
                    logger.info("Dispatched generic webhook alert for meme %s", meme.id)
                    success = True
            except Exception as e:
                logger.error("Failed to send generic webhook for meme %s: %s", meme.id, e)

    return success
