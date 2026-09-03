"""Bluesky AT Protocol public search and feed meme ingestion engine."""

from __future__ import annotations

import asyncio
import datetime
import html
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.core.dedup import compute_content_hash, normalize_url
from app.core.ranking import calculate_trending_score
from app.core.security import (
    PoliteRateLimiter,
    calculate_backoff_delay,
    get_request_headers,
)
from app.ingestion.base import BaseSourceFetcher
from app.models.meme import MediaType, NormalizedMeme, SourcePlatform

logger = logging.getLogger(__name__)

# Global per-domain rate limiter
_rate_limiter = PoliteRateLimiter(min_interval_seconds=1.0)


def parse_iso8601_date(date_str: Optional[str]) -> float:
    """Parse ISO 8601 date string to Unix timestamp in seconds."""
    if not date_str:
        return time.time()
    clean_str = date_str.strip()
    try:
        if clean_str.endswith("Z"):
            clean_str = clean_str[:-1] + "+00:00"
        dt = datetime.datetime.fromisoformat(clean_str)
        return dt.timestamp()
    except Exception as e:
        logger.debug("Failed to parse ISO 8601 date '%s': %s", date_str, e)
        return time.time()


def parse_bluesky_feed(
    payload: Union[Dict[str, Any], str], feed_name: str = "meme"
) -> List[NormalizedMeme]:
    """Top-level helper function to parse raw Bluesky search/feed JSON or dictionary."""
    fetcher = BlueskyFetcher(feed_name=feed_name)
    if isinstance(payload, str):
        return fetcher.parse_search_json(payload)
    elif isinstance(payload, dict):
        return fetcher.parse_search_dict(payload)
    elif isinstance(payload, list):
        results: List[NormalizedMeme] = []
        for item in payload:
            m = fetcher.parse_post_record(item)
            if m:
                results.append(m)
        return results
    return []


class BlueskyFetcher(BaseSourceFetcher):
    """Fetches and normalizes meme posts from Bluesky via public AT Protocol XRPC endpoints."""

    def __init__(
        self,
        feed_name: str = "meme",
        http_client: Optional[httpx.AsyncClient] = None,
        fixture_path: Optional[Path] = None,
    ) -> None:
        clean_feed = feed_name.strip()
        super().__init__(
            name=f"bluesky:{clean_feed}",
            platform=SourcePlatform.BLUESKY,
            community=clean_feed,
        )
        self.feed_name = clean_feed
        self._custom_client = http_client
        self.fixture_path = fixture_path or self._resolve_default_fixture_path()

    def _resolve_default_fixture_path(self) -> Path:
        """Resolve path to local offline mock fixture JSON file."""
        root = Path(__file__).resolve().parent.parent.parent
        primary_path = root / "data" / "fixtures" / "bluesky_memes.json"
        if primary_path.exists():
            return primary_path
        alt_path = root / "data" / "fixtures" / "bsky_memes.json"
        if alt_path.exists():
            return alt_path
        return primary_path

    def _extract_media(
        self, post_data: Dict[str, Any], author_did: str = ""
    ) -> Tuple[Optional[str], MediaType, Optional[str]]:
        """Extract direct media URL, media type, and alt text from AT Protocol post payload."""
        embed = post_data.get("embed")
        record = post_data.get("record") if isinstance(post_data.get("record"), dict) else {}
        record_embed = record.get("embed") if isinstance(record.get("embed"), dict) else {}

        # 1. Inspect embed in top-level view
        if isinstance(embed, dict):
            embed_type = embed.get("$type", "")

            # Images view
            if "embed.images" in embed_type or "images" in embed:
                images = embed.get("images", [])
                if isinstance(images, list) and images:
                    first_img = images[0]
                    if isinstance(first_img, dict):
                        url = first_img.get("fullsize") or first_img.get("thumb")
                        alt = first_img.get("alt")
                        if url and isinstance(url, str):
                            lower_url = url.lower()
                            media_type = (
                                MediaType.GIF if lower_url.endswith(".gif") else MediaType.IMAGE
                            )
                            return url, media_type, alt

            # Video view
            if "embed.video" in embed_type or "video" in embed:
                vid_url = embed.get("playlist") or embed.get("thumbnail")
                alt = embed.get("alt")
                if vid_url and isinstance(vid_url, str):
                    return vid_url, MediaType.VIDEO, alt

            # Record with media view
            if "embed.recordWithMedia" in embed_type or "media" in embed:
                media = embed.get("media")
                if isinstance(media, dict):
                    media_images = media.get("images", [])
                    if isinstance(media_images, list) and media_images:
                        first_img = media_images[0]
                        if isinstance(first_img, dict):
                            url = first_img.get("fullsize") or first_img.get("thumb")
                            alt = first_img.get("alt")
                            if url and isinstance(url, str):
                                lower_url = url.lower()
                                media_type = (
                                    MediaType.GIF
                                    if lower_url.endswith(".gif")
                                    else MediaType.IMAGE
                                )
                                return url, media_type, alt

        # 2. Inspect record-level embed (raw AT Protocol record)
        if isinstance(record_embed, dict):
            rec_type = record_embed.get("$type", "")
            if "embed.images" in rec_type or "images" in record_embed:
                images = record_embed.get("images", [])
                if isinstance(images, list) and images:
                    first_img = images[0]
                    if isinstance(first_img, dict):
                        alt = first_img.get("alt")
                        # Raw blob reference
                        img_obj = first_img.get("image")
                        if isinstance(img_obj, dict):
                            ref = img_obj.get("ref", {})
                            cid = ref.get("$link") if isinstance(ref, dict) else None
                            if cid and author_did:
                                cdn_url = f"https://cdn.bsky.app/img/feed_fullsize/plain/{author_did}/{cid}@jpeg"
                                return cdn_url, MediaType.IMAGE, alt

        return None, MediaType.IMAGE, None

    def parse_post_record(self, post_data: Any) -> Optional[NormalizedMeme]:
        """Parse an individual Bluesky AT Protocol post JSON dictionary into NormalizedMeme."""
        if not isinstance(post_data, dict):
            return None

        # Unwrap if nested under 'post' key in feed views
        item = post_data.get("post") if isinstance(post_data.get("post"), dict) else post_data

        uri = str(item.get("uri") or "").strip()
        cid = str(item.get("cid") or "").strip()
        if not uri and not cid and not item.get("id"):
            return None

        # Extract record key (rkey) from AT URI: at://did:plc:.../app.bsky.feed.post/{rkey}
        rkey = ""
        author_did = ""
        if uri.startswith("at://"):
            parts = uri[5:].split("/")
            if len(parts) >= 1:
                author_did = parts[0]
            if len(parts) >= 3:
                rkey = parts[-1]
        if not rkey:
            rkey = str(item.get("id") or cid or str(int(time.time())))
            rkey = rkey.replace("bluesky_", "")

        # Extract author
        author_obj = item.get("author") if isinstance(item.get("author"), dict) else {}
        handle = str(author_obj.get("handle") or "").strip()
        if not author_did and author_obj.get("did"):
            author_did = str(author_obj.get("did"))
        author_handle = f"@{handle}" if handle and not handle.startswith("@") else (handle or "@unknown.bsky.social")

        # Extract media
        media_url, media_type, alt_text = self._extract_media(item, author_did)
        if not media_url:
            return None

        # Extract text / title
        record = item.get("record") if isinstance(item.get("record"), dict) else {}
        text = str(record.get("text") or item.get("text") or "").strip()
        clean_text = html.unescape(re.sub(r"<[^>]+>", " ", text)).strip()
        clean_text = " ".join(clean_text.split())

        if not clean_text:
            if alt_text:
                clean_text = html.unescape(alt_text).strip()
            else:
                clean_text = f"Bluesky Meme #{rkey}"

        # Clean handle for permalink
        clean_handle = handle or author_did or "profile"
        permalink = str(item.get("permalink") or item.get("url") or "")
        if not permalink or not permalink.startswith("http"):
            permalink = f"https://bsky.app/profile/{clean_handle}/post/{rkey}"

        # Engagement metrics
        try:
            likes = int(item.get("likeCount") or 0)
        except (ValueError, TypeError):
            likes = 0
        try:
            reposts = int(item.get("repostCount") or 0)
        except (ValueError, TypeError):
            reposts = 0
        score = likes + (reposts * 2)

        try:
            reply_count = int(item.get("replyCount") or 0)
        except (ValueError, TypeError):
            reply_count = 0

        # Timestamp
        created_str = record.get("createdAt") or item.get("indexedAt")
        created_at = parse_iso8601_date(created_str) if created_str else time.time()

        # NSFW flag
        labels = item.get("labels", [])
        is_nsfw = False
        if isinstance(labels, list):
            for label in labels:
                if isinstance(label, dict):
                    val = str(label.get("val") or "").lower()
                    if val in ("porn", "nsfw", "sexual", "nudity", "graphic"):
                        is_nsfw = True
                        break
        if re.search(r"\b(nsfw|explicit|adult)\b", clean_text.lower()):
            is_nsfw = True

        domain = "cdn.bsky.app"
        try:
            parsed_domain = urlparse(media_url).netloc
            if parsed_domain:
                domain = parsed_domain
        except Exception:
            pass

        meme_id = f"bluesky_{rkey}"
        content_hash = compute_content_hash(media_url, clean_text)
        trending_score = calculate_trending_score(score, reply_count, created_at)

        return NormalizedMeme(
            id=meme_id,
            raw_id=rkey,
            title=clean_text,
            media_url=media_url,
            media_type=media_type,
            source_platform=SourcePlatform.BLUESKY,
            source_community=self.community,
            permalink=permalink,
            author=author_handle,
            score=score,
            num_comments=reply_count,
            created_at=created_at,
            is_nsfw=is_nsfw,
            domain=domain,
            content_hash=content_hash,
            trending_score=trending_score,
        )

    def parse_search_dict(self, payload: Any) -> List[NormalizedMeme]:
        """Parse Bluesky search or feed dictionary response into normalized memes."""
        if not isinstance(payload, dict):
            return []

        # Primary key in app.bsky.feed.searchPosts is 'posts'
        posts = payload.get("posts")
        if not isinstance(posts, list):
            # Feed generators use 'feed'
            posts = payload.get("feed")
        if not isinstance(posts, list):
            return []

        results: List[NormalizedMeme] = []
        for post_item in posts:
            try:
                meme = self.parse_post_record(post_item)
                if meme:
                    results.append(meme)
            except Exception as e:
                logger.debug("Skipping malformed Bluesky post: %s", e)
                continue

        return results

    def parse_search_json(self, raw_json: str) -> List[NormalizedMeme]:
        """Parse Bluesky JSON payload string into normalized memes."""
        if not isinstance(raw_json, str) or not raw_json.strip():
            return []
        try:
            payload = json.loads(raw_json)
        except Exception as e:
            logger.warning("Failed to parse Bluesky JSON: %s", e)
            return []

        if isinstance(payload, dict):
            return self.parse_search_dict(payload)
        elif isinstance(payload, list):
            results: List[NormalizedMeme] = []
            for item in payload:
                m = self.parse_post_record(item)
                if m:
                    results.append(m)
            return results
        return []

    def load_offline_fixtures(self) -> List[NormalizedMeme]:
        """Load memes from local offline Bluesky fixture file."""
        path = self.fixture_path
        if not path.exists():
            # Try alternate names
            alt = path.parent / "bsky_memes.json"
            if alt.exists():
                path = alt
            else:
                logger.warning("Bluesky fixture file not found: %s", path)
                self.update_failure(FileNotFoundError(f"Fixture {path} not found"))
                return []

        try:
            content = path.read_text(encoding="utf-8")
            memes = self.parse_search_json(content)
            if memes:
                self.update_success(len(memes), latency_ms=0.5)
            else:
                self.update_failure(ValueError("Fixture contained zero valid memes"))
            return memes
        except Exception as e:
            self.update_failure(e)
            logger.error("Error loading Bluesky fixture %s: %s", path, e)
            return []

    async def fetch_memes(self) -> List[NormalizedMeme]:
        """Fetch memes from live Bluesky AT Protocol public endpoints with retry and fixture fallback."""
        settings = get_settings()

        if settings.OFFLINE_MODE:
            return self.load_offline_fixtures()

        start_time = time.monotonic()
        client = self._custom_client or httpx.AsyncClient(
            timeout=settings.REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        should_close = self._custom_client is None

        endpoints = [
            f"https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q={self.feed_name}&limit=50",
            f"https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?q={self.feed_name}&limit=50",
        ]

        try:
            for endpoint in endpoints:
                for attempt in range(settings.MAX_RETRIES):
                    try:
                        await _rate_limiter.throttle("bsky.app")
                        headers = get_request_headers(
                            accept="application/json, text/plain, */*"
                        )
                        resp = await client.get(endpoint, headers=headers)

                        if resp.status_code == 200:
                            memes = self.parse_search_json(resp.text)
                            if memes:
                                latency_ms = (time.monotonic() - start_time) * 1000.0
                                self.update_success(len(memes), latency_ms)
                                return memes

                        if resp.status_code in (429, 403, 500, 502, 503, 504):
                            backoff = calculate_backoff_delay(attempt, resp.headers)
                            logger.warning(
                                "Bluesky [%s] HTTP %d. Attempt %d/%d, backing off %.2fs",
                                self.name,
                                resp.status_code,
                                attempt + 1,
                                settings.MAX_RETRIES,
                                backoff,
                            )
                            await asyncio.sleep(backoff)
                            continue

                        break

                    except (httpx.TimeoutException, httpx.NetworkError) as net_err:
                        backoff = calculate_backoff_delay(attempt)
                        logger.warning(
                            "Bluesky [%s] network error: %s. Retrying in %.2fs",
                            self.name,
                            net_err,
                            backoff,
                        )
                        await asyncio.sleep(backoff)

            logger.info("Live fetch failed for %s; falling back to offline fixtures.", self.name)
            return self.load_offline_fixtures()

        except Exception as exc:
            self.update_failure(exc)
            logger.error("Ingestion failed for %s: %s", self.name, exc)
            return self.load_offline_fixtures()

        finally:
            if should_close:
                await client.aclose()


BlueskyMemeFetcher = BlueskyFetcher
