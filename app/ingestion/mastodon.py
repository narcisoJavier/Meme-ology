"""Mastodon / Fediverse public hashtag timeline meme ingestion engine."""

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


def strip_html_tags(content_html: Optional[str]) -> str:
    """Strip HTML markup, replace line breaks with spaces, and unescape entities."""
    if not content_html:
        return ""
    # Replace <br> and </p> with spaces to avoid smashing words together
    spaced = re.sub(r"</?(?:p|br|div|blockquote)[^>]*>", " ", content_html, flags=re.IGNORECASE)
    # Remove remaining HTML tags
    clean = re.sub(r"<[^>]+>", " ", spaced)
    # Unescape HTML entities
    unescaped = html.unescape(clean)
    # Collapse multiple whitespaces
    return " ".join(unescaped.split()).strip()


def parse_mastodon_timeline(
    payload: Union[List[Any], Dict[str, Any], str], tag: str = "meme"
) -> List[NormalizedMeme]:
    """Top-level helper function to parse raw Mastodon timeline JSON or dictionary."""
    fetcher = MastodonFetcher(tag=tag)
    if isinstance(payload, str):
        return fetcher.parse_timeline_json(payload)
    elif isinstance(payload, list):
        return fetcher.parse_timeline_list(payload)
    elif isinstance(payload, dict):
        if "items" in payload and isinstance(payload["items"], list):
            return fetcher.parse_timeline_list(payload["items"])
        meme = fetcher.parse_status_dict(payload)
        return [meme] if meme else []
    return []


class MastodonFetcher(BaseSourceFetcher):
    """Fetches and normalizes meme posts from Mastodon / Fediverse public hashtag timelines."""

    def __init__(
        self,
        instance_url: str = "mastodon.social",
        tag: str = "meme",
        http_client: Optional[httpx.AsyncClient] = None,
        fixture_path: Optional[Path] = None,
    ) -> None:
        clean_instance = instance_url.replace("https://", "").replace("http://", "").strip().rstrip("/")
        clean_tag = tag.lstrip("#").strip()
        super().__init__(
            name=f"mastodon:{clean_instance}:#{clean_tag}",
            platform=SourcePlatform.MASTODON,
            community=f"#{clean_tag}",
        )
        self.instance_url = clean_instance or "mastodon.social"
        self.tag = clean_tag
        self._custom_client = http_client
        self.fixture_path = fixture_path or self._resolve_default_fixture_path()

    def _resolve_default_fixture_path(self) -> Path:
        """Resolve path to local offline mock fixture JSON file."""
        root = Path(__file__).resolve().parent.parent.parent
        return root / "data" / "fixtures" / "mastodon_memes.json"

    def _extract_media(
        self, status_data: Dict[str, Any]
    ) -> Tuple[Optional[str], MediaType, Optional[str]]:
        """Extract direct media attachment URL, media type, and description."""
        attachments = status_data.get("media_attachments")
        if not isinstance(attachments, list) or not attachments:
            return None, MediaType.IMAGE, None

        for att in attachments:
            if not isinstance(att, dict):
                continue
            att_type = str(att.get("type") or "").lower()
            url = att.get("url") or att.get("preview_url") or att.get("remote_url")
            desc = att.get("description")

            if not url or not isinstance(url, str):
                continue

            lower_url = url.lower()
            if att_type in ("video", "gifv") or lower_url.endswith((".mp4", ".webm", ".gifv")):
                return url, MediaType.VIDEO, desc
            elif att_type == "gif" or lower_url.endswith(".gif"):
                return url, MediaType.GIF, desc
            elif att_type == "image" or any(lower_url.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
                return url, MediaType.IMAGE, desc

        # Fallback to first non-empty attachment if type wasn't explicitly standard
        first = attachments[0]
        if isinstance(first, dict):
            url = first.get("url") or first.get("preview_url")
            if url and isinstance(url, str):
                return url, MediaType.IMAGE, first.get("description")

        return None, MediaType.IMAGE, None

    def parse_status_dict(self, status_data: Any) -> Optional[NormalizedMeme]:
        """Parse an individual Mastodon Status JSON dictionary into NormalizedMeme."""
        if not isinstance(status_data, dict):
            return None

        status_id = str(status_data.get("id") or "").strip()
        if not status_id:
            return None

        media_url, media_type, media_desc = self._extract_media(status_data)
        if not media_url:
            return None

        # Author handle attribution
        account = status_data.get("account") if isinstance(status_data.get("account"), dict) else {}
        acct = str(account.get("acct") or "").strip()
        if not acct:
            acct = str(account.get("username") or "anonymous")
        if "@" not in acct:
            acct = f"{acct}@{self.instance_url}"
        author_handle = f"@{acct}" if not acct.startswith("@") else acct

        # Content / Title
        content_html = status_data.get("content")
        clean_title = strip_html_tags(str(content_html) if content_html is not None else "")
        if not clean_title:
            spoiler = str(status_data.get("spoiler_text") or "").strip()
            if spoiler:
                clean_title = spoiler
            elif media_desc:
                clean_title = str(media_desc).strip()
            else:
                clean_title = f"Mastodon #{self.tag} {status_id}"

        # Direct post permalink
        raw_permalink = status_data.get("url") or status_data.get("uri")
        permalink = str(raw_permalink) if raw_permalink else f"https://{self.instance_url}/@{acct}/{status_id}"

        # Engagement metrics
        try:
            favs = int(status_data.get("favourites_count") or 0)
        except (ValueError, TypeError):
            favs = 0
        try:
            reblogs = int(status_data.get("reblogs_count") or 0)
        except (ValueError, TypeError):
            reblogs = 0
        score = favs + (reblogs * 2)

        try:
            replies = int(status_data.get("replies_count") or 0)
        except (ValueError, TypeError):
            replies = 0

        # Timestamp
        created_str = status_data.get("created_at")
        created_at = parse_iso8601_date(created_str) if created_str else time.time()

        # NSFW flag
        is_nsfw = bool(status_data.get("sensitive", False))
        if re.search(r"\b(nsfw|explicit|adult)\b", clean_title.lower()):
            is_nsfw = True
        tags = status_data.get("tags", [])
        if isinstance(tags, list):
            for t in tags:
                if isinstance(t, dict) and str(t.get("name", "")).lower() in ("nsfw", "sensitive"):
                    is_nsfw = True
                    break

        domain = "files.mastodon.social"
        try:
            parsed = urlparse(media_url)
            if parsed.netloc:
                domain = parsed.netloc
        except Exception:
            pass

        meme_id = f"mastodon_{status_id}"
        content_hash = compute_content_hash(media_url, clean_title)
        trending_score = calculate_trending_score(score, replies, created_at)

        return NormalizedMeme(
            id=meme_id,
            raw_id=status_id,
            title=clean_title,
            media_url=media_url,
            media_type=media_type,
            source_platform=SourcePlatform.MASTODON,
            source_community=self.community,
            permalink=permalink,
            author=author_handle,
            score=score,
            num_comments=replies,
            created_at=created_at,
            is_nsfw=is_nsfw,
            domain=domain,
            content_hash=content_hash,
            trending_score=trending_score,
        )

    def parse_timeline_list(self, payload: Any) -> List[NormalizedMeme]:
        """Parse list of Mastodon status dictionaries into normalized memes."""
        if not isinstance(payload, list):
            return []

        results: List[NormalizedMeme] = []
        for status_item in payload:
            try:
                meme = self.parse_status_dict(status_item)
                if meme:
                    results.append(meme)
            except Exception as e:
                logger.debug("Skipping malformed Mastodon status: %s", e)
                continue

        return results

    def parse_timeline_json(self, raw_json: str) -> List[NormalizedMeme]:
        """Parse Mastodon timeline JSON string into normalized memes."""
        if not isinstance(raw_json, str) or not raw_json.strip():
            return []
        try:
            payload = json.loads(raw_json)
        except Exception as e:
            logger.warning("Failed to parse Mastodon JSON: %s", e)
            return []

        if isinstance(payload, list):
            return self.parse_timeline_list(payload)
        elif isinstance(payload, dict):
            if "items" in payload and isinstance(payload["items"], list):
                return self.parse_timeline_list(payload["items"])
            meme = self.parse_status_dict(payload)
            return [meme] if meme else []
        return []

    def load_offline_fixtures(self) -> List[NormalizedMeme]:
        """Load memes from local offline Mastodon fixture file."""
        path = self.fixture_path
        if not path.exists():
            logger.warning("Mastodon fixture file not found: %s", path)
            self.update_failure(FileNotFoundError(f"Fixture {path} not found"))
            return []

        try:
            content = path.read_text(encoding="utf-8")
            memes = self.parse_timeline_json(content)
            if memes:
                self.update_success(len(memes), latency_ms=0.5)
            else:
                self.update_failure(ValueError("Fixture contained zero valid memes"))
            return memes
        except Exception as e:
            self.update_failure(e)
            logger.error("Error loading Mastodon fixture %s: %s", path, e)
            return []

    async def fetch_memes(self) -> List[NormalizedMeme]:
        """Fetch memes from live Mastodon hashtag timeline with instance failover and fixture fallback."""
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
            f"https://{self.instance_url}/api/v1/timelines/tag/{self.tag}?limit=40",
            f"https://mastodon.social/api/v1/timelines/tag/{self.tag}?limit=40",
            f"https://mastodon.online/api/v1/timelines/tag/{self.tag}?limit=40",
        ]

        try:
            for endpoint in endpoints:
                for attempt in range(settings.MAX_RETRIES):
                    try:
                        domain = urlparse(endpoint).netloc
                        await _rate_limiter.throttle(domain)
                        headers = get_request_headers(
                            accept="application/json, text/plain, */*"
                        )
                        resp = await client.get(endpoint, headers=headers)

                        if resp.status_code == 200:
                            memes = self.parse_timeline_json(resp.text)
                            if memes:
                                latency_ms = (time.monotonic() - start_time) * 1000.0
                                self.update_success(len(memes), latency_ms)
                                return memes

                        if resp.status_code in (429, 403, 500, 502, 503, 504):
                            backoff = calculate_backoff_delay(attempt, resp.headers)
                            logger.warning(
                                "Mastodon [%s] HTTP %d. Attempt %d/%d, backing off %.2fs",
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
                            "Mastodon [%s] network error: %s. Retrying in %.2fs",
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


MastodonMemeFetcher = MastodonFetcher
