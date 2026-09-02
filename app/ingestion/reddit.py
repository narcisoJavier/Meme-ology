"""Reddit multi-subreddit meme ingestion engine."""

import asyncio
import html
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx

from app.config import get_settings
from app.core.security import (
    PoliteRateLimiter,
    calculate_backoff_delay,
    get_request_headers,
)
from app.core.dedup import compute_content_hash, normalize_url
from app.core.ranking import calculate_trending_score
from app.ingestion.base import BaseSourceFetcher
from app.models.meme import MediaType, NormalizedMeme, SourcePlatform

logger = logging.getLogger(__name__)

# Global per-domain rate limiter
_rate_limiter = PoliteRateLimiter(min_interval_seconds=1.0)


def parse_reddit_listing(
    payload: Union[Dict[str, Any], str], subreddit: str = "r/memes"
) -> List[NormalizedMeme]:
    """Top-level helper function to parse raw Reddit listing dictionary or JSON string."""
    clean_sub = subreddit.lstrip("r/").strip()
    fetcher = RedditFetcher(subreddit=clean_sub)
    if isinstance(payload, str):
        return fetcher.parse_listing_json(payload, sub_override=clean_sub)
    elif isinstance(payload, dict):
        return fetcher.parse_listing_dict(payload, sub_override=clean_sub)
    return []


class RedditFetcher(BaseSourceFetcher):
    """Fetches and normalizes meme submissions from Reddit subreddits."""

    def __init__(
        self,
        subreddit: str = "memes",
        http_client: Optional[httpx.AsyncClient] = None,
        fixture_path: Optional[Path] = None,
    ) -> None:
        clean_sub = subreddit.lstrip("r/").strip()
        super().__init__(
            name=f"reddit:r/{clean_sub}",
            platform=SourcePlatform.REDDIT,
            community=f"r/{clean_sub}",
        )
        self.subreddit = clean_sub
        self._custom_client = http_client
        self.fixture_path = fixture_path or self._resolve_default_fixture_path(clean_sub)

    def _resolve_default_fixture_path(self, sub: Optional[str] = None) -> Path:
        """Resolve path to local mock fixture JSON file."""
        sub_name = sub or self.subreddit
        root = Path(__file__).resolve().parent.parent.parent
        return root / "data" / "fixtures" / f"reddit_{sub_name}.json"

    def _extract_media_url_and_type(
        self, data: Optional[Dict[str, Any]]
    ) -> Tuple[Optional[str], MediaType, str]:
        """Extract direct media URL and determine media type following the extraction hierarchy."""
        if not isinstance(data, dict):
            return None, MediaType.IMAGE, ""

        raw_domain = data.get("domain")
        domain = str(raw_domain) if raw_domain is not None else ""
        raw_url = data.get("url")
        url = str(raw_url) if raw_url is not None else ""
        raw_post_hint = data.get("post_hint")
        post_hint = str(raw_post_hint) if raw_post_hint is not None else ""
        is_video = bool(data.get("is_video", False))
        raw_media = data.get("media")
        media = raw_media if isinstance(raw_media, dict) else {}
        raw_secure_media = data.get("secure_media")
        secure_media = raw_secure_media if isinstance(raw_secure_media, dict) else {}

        # 1. Native Reddit Video (v.redd.it)
        if is_video or domain == "v.redd.it" or "reddit_video" in media or "reddit_video" in secure_media:
            raw_vid = media.get("reddit_video") if isinstance(media.get("reddit_video"), dict) else None
            if not raw_vid:
                raw_vid = secure_media.get("reddit_video") if isinstance(secure_media.get("reddit_video"), dict) else None
            video_obj = raw_vid if isinstance(raw_vid, dict) else {}
            fallback_url = video_obj.get("fallback_url")
            if fallback_url and isinstance(fallback_url, str):
                clean_video_url = html.unescape(fallback_url)
                return clean_video_url, MediaType.VIDEO, domain

        # 2. Direct Image / GIF by URL extension (strip query params for extension check)
        clean_url = html.unescape(url) if url else ""
        lower_url = clean_url.lower()
        lower_path = re.sub(r"\?.*$", "", lower_url)
        if any(lower_path.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
            return clean_url, MediaType.IMAGE, domain
        if lower_path.endswith(".gif") or lower_path.endswith(".gifv"):
            if lower_path.endswith(".gifv"):
                mp4_url = re.sub(r"\.gifv(\?.*)?$", r".mp4\1", clean_url, flags=re.IGNORECASE)
                return mp4_url, MediaType.VIDEO, domain
            return clean_url, MediaType.GIF, domain
        if lower_path.endswith(".webm") or lower_path.endswith(".mp4"):
            return clean_url, MediaType.VIDEO, domain

        # 3. Imgur Link Normalization
        if ("imgur.com" in domain or "imgur.com" in lower_path) and clean_url:
            match = re.search(r"imgur\.com/(?:gallery/|a/)?([a-zA-Z0-9]+)", clean_url)
            if match:
                img_id = match.group(1)
                canonical_imgur = f"https://i.imgur.com/{img_id}.jpg"
                return canonical_imgur, MediaType.IMAGE, "i.imgur.com"

        # 4. Reddit Gallery Post
        is_gallery = bool(data.get("is_gallery", False) or post_hint == "gallery")
        raw_gallery_data = data.get("gallery_data")
        gallery_data = raw_gallery_data if isinstance(raw_gallery_data, dict) else {}
        raw_media_metadata = data.get("media_metadata")
        media_metadata = raw_media_metadata if isinstance(raw_media_metadata, dict) else {}
        if (is_gallery or gallery_data) and media_metadata:
            items = gallery_data.get("items") if isinstance(gallery_data.get("items"), list) else []
            media_id = None
            if items and isinstance(items[0], dict):
                media_id = items[0].get("media_id")
            if not media_id and isinstance(media_metadata, dict):
                media_id = next(iter(media_metadata.keys()), None)
            if media_id and media_id in media_metadata:
                item_info = media_metadata.get(media_id)
                if isinstance(item_info, dict):
                    source_info = item_info.get("s") if isinstance(item_info.get("s"), dict) else {}
                    raw_gallery_url = source_info.get("u") or source_info.get("gif") or source_info.get("mp4")
                    if not raw_gallery_url and isinstance(item_info.get("p"), list) and len(item_info["p"]) > 0:
                        last_p = item_info["p"][-1]
                        if isinstance(last_p, dict):
                            raw_gallery_url = last_p.get("u")
                    if raw_gallery_url and isinstance(raw_gallery_url, str):
                        clean_gallery_url = html.unescape(raw_gallery_url)
                        media_type = MediaType.GIF if item_info.get("m") == "image/gif" else MediaType.IMAGE
                        return clean_gallery_url, media_type, "preview.redd.it"

        # 5. Check crosspost parent if available
        crosspost_parents = data.get("crosspost_parent_list")
        if isinstance(crosspost_parents, list) and crosspost_parents:
            for parent_data in crosspost_parents:
                if isinstance(parent_data, dict):
                    p_url, p_type, p_domain = self._extract_media_url_and_type(parent_data)
                    if p_url:
                        return p_url, p_type, p_domain

        # 6. Preview Source Fallback
        raw_preview = data.get("preview")
        preview = raw_preview if isinstance(raw_preview, dict) else {}
        images = preview.get("images") if isinstance(preview.get("images"), list) else []
        if images and isinstance(images[0], dict):
            source = images[0].get("source") if isinstance(images[0].get("source"), dict) else {}
            raw_preview_url = source.get("url")
            if raw_preview_url and isinstance(raw_preview_url, str):
                clean_preview_url = html.unescape(raw_preview_url)
                return clean_preview_url, MediaType.IMAGE, "preview.redd.it"

        # 7. Post hint == image fallback
        if post_hint == "image" and url:
            return clean_url, MediaType.IMAGE, domain

        return None, MediaType.IMAGE, domain

    def parse_post_data(self, post_data: Any, sub_override: Optional[str] = None) -> Optional[NormalizedMeme]:
        """Parse raw Reddit post JSON dictionary into NormalizedMeme instance."""
        if not isinstance(post_data, dict):
            return None

        if post_data.get("stickied", False) or post_data.get("pinned", False):
            return None

        if post_data.get("is_self", False):
            return None

        raw_author = post_data.get("author")
        author = str(raw_author) if raw_author is not None else "unknown"
        if not author:
            author = "unknown"
        if author == "[deleted]" or post_data.get("selftext") == "[removed]":
            return None

        media_url, media_type, domain = self._extract_media_url_and_type(post_data)
        if not media_url:
            return None

        raw_id = str(post_data.get("id") or "").strip()
        if not raw_id:
            return None

        sub = sub_override or self.subreddit
        meme_id = f"reddit_{sub}_{raw_id}"
        raw_title = post_data.get("title")
        title = html.unescape(str(raw_title) if raw_title is not None else "").strip()
        raw_permalink = post_data.get("permalink")
        permalink = str(raw_permalink) if raw_permalink is not None else ""
        if permalink and not permalink.startswith("http"):
            permalink = f"https://www.reddit.com{permalink}"

        raw_score = post_data.get("score")
        if raw_score is None:
            raw_score = post_data.get("ups")
        try:
            score = int(raw_score) if raw_score is not None else 0
        except (ValueError, TypeError):
            score = 0

        raw_comments = post_data.get("num_comments")
        try:
            num_comments = int(raw_comments) if raw_comments is not None else 0
        except (ValueError, TypeError):
            num_comments = 0

        raw_created = post_data.get("created_utc")
        try:
            created_utc = float(raw_created) if raw_created is not None else time.time()
        except (ValueError, TypeError):
            created_utc = time.time()

        is_nsfw = bool(post_data.get("over_18", False))

        content_hash = compute_content_hash(media_url, title)
        trending_score = calculate_trending_score(score, num_comments, created_utc)

        return NormalizedMeme(
            id=meme_id,
            raw_id=raw_id,
            title=title,
            media_url=media_url,
            media_type=media_type,
            source_platform=SourcePlatform.REDDIT,
            source_community=f"r/{sub}",
            permalink=permalink,
            author=author,
            score=score,
            num_comments=num_comments,
            created_at=created_utc,
            is_nsfw=is_nsfw,
            domain=domain or "",
            content_hash=content_hash,
            trending_score=trending_score,
        )

    def parse_listing_dict(self, payload: Any, sub_override: Optional[str] = None) -> List[NormalizedMeme]:
        """Parse Reddit Listing dictionary into normalized memes."""
        if not isinstance(payload, dict):
            return []

        data_section = payload.get("data", {})
        if not isinstance(data_section, dict):
            return []

        children = data_section.get("children", [])
        if not isinstance(children, list):
            return []

        results: List[NormalizedMeme] = []
        for child in children:
            if not isinstance(child, dict):
                continue
            post_data = child.get("data")
            if not isinstance(post_data, dict):
                continue
            try:
                meme = self.parse_post_data(post_data, sub_override)
                if meme:
                    results.append(meme)
            except Exception as exc:
                logger.debug(f"Skipping malformed post due to error: {exc}")
                continue

        return results

    def parse_listing_json(self, raw_json: str, sub_override: Optional[str] = None) -> List[NormalizedMeme]:
        """Parse Reddit Listing JSON payload into normalized memes."""
        if not isinstance(raw_json, str) or not raw_json.strip():
            return []
        try:
            payload = json.loads(raw_json)
        except Exception as e:
            logger.warning(f"Failed to parse Reddit JSON listing: {e}")
            return []

        if not isinstance(payload, dict):
            return []

        return self.parse_listing_dict(payload, sub_override)

    def load_offline_fixtures(self, sub_override: Optional[str] = None) -> List[NormalizedMeme]:
        """Load memes from local offline fixture file."""
        sub = sub_override or self.subreddit
        path = self._resolve_default_fixture_path(sub)
        if not path.exists():
            logger.warning(f"Fixture file not found: {path}")
            return []

        try:
            content = path.read_text(encoding="utf-8")
            memes = self.parse_listing_json(content, sub_override=sub)
            self.update_success(len(memes), latency_ms=0.5)
            return memes
        except Exception as e:
            self.update_failure(e)
            logger.error(f"Error loading fixture {path}: {e}")
            return []

    async def fetch_subreddit(self, subreddit: str) -> List[NormalizedMeme]:
        """Fetch memes for a specific subreddit."""
        clean_sub = subreddit.lstrip("r/").strip()
        orig_sub = self.subreddit
        self.subreddit = clean_sub
        try:
            return await self.fetch_memes()
        finally:
            self.subreddit = orig_sub

    def parse_gateway_dict(self, payload: Any, sub_override: Optional[str] = None) -> List[NormalizedMeme]:
        """Parse meme-api.com gateway payload into normalized memes."""
        if not isinstance(payload, dict):
            return []
        items = payload.get("memes", [])
        if not isinstance(items, list):
            return []

        results: List[NormalizedMeme] = []
        now = time.time()
        sub = (sub_override or self.subreddit).lstrip("r/").strip()

        for item in items:
            if not isinstance(item, dict):
                continue
            url = item.get("url", "")
            title = item.get("title", "")
            if not url or not title:
                continue

            post_link = item.get("postLink", "")
            post_id = post_link.rstrip("/").split("/")[-1] if post_link else ""
            meme_id = f"reddit_{sub}_{post_id}" if post_id else f"reddit_{sub}_{str(now)}"

            lower_url = url.lower()
            media_type = MediaType.IMAGE
            if lower_url.endswith(".gif"):
                media_type = MediaType.GIF
            elif lower_url.endswith((".mp4", ".webm")):
                media_type = MediaType.VIDEO

            score = int(item.get("ups", 0))
            comments = max(10, score // 30)
            trending = calculate_trending_score(score, comments, now)
            chash = compute_content_hash(url, title)

            results.append(
                NormalizedMeme(
                    id=meme_id,
                    raw_id=post_id,
                    title=title,
                    media_url=url,
                    media_type=media_type,
                    source_platform=SourcePlatform.REDDIT,
                    source_community=f"r/{item.get('subreddit', sub)}",
                    permalink=post_link or f"https://reddit.com/r/{sub}",
                    author=str(item.get("author", "reddit_user")),
                    score=score,
                    num_comments=comments,
                    created_at=now,
                    is_nsfw=bool(item.get("nsfw", False)),
                    domain="i.redd.it",
                    content_hash=chash,
                    trending_score=trending,
                )
            )
        return results

    async def fetch_memes(self) -> List[NormalizedMeme]:
        """Fetch memes from live Reddit endpoints with retry and fallback to fixtures."""
        settings = get_settings()

        if settings.OFFLINE_MODE:
            return self.load_offline_fixtures()

        start_time = time.monotonic()
        client = self._custom_client or httpx.AsyncClient(
            timeout=settings.REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        should_close = self._custom_client is None

        try:
            # 1. Primary: High-availability gateway to avoid Reddit datacenter 403 blocks
            try:
                gateway_url = f"https://meme-api.com/gimme/{self.subreddit}/30"
                gw_resp = await client.get(gateway_url, timeout=5.0)
                if gw_resp.status_code == 200:
                    gateway_memes = self.parse_gateway_dict(gw_resp.json())
                    if gateway_memes:
                        latency_ms = (time.monotonic() - start_time) * 1000.0
                        self.update_success(len(gateway_memes), latency_ms)
                        return gateway_memes
            except Exception as gw_err:
                logger.debug(f"Gateway fallback check: {gw_err}")

            # 2. Secondary: Direct Reddit JSON
            endpoints = [
                f"https://www.reddit.com/r/{self.subreddit}/hot.json?limit=50&raw_json=1",
                f"https://old.reddit.com/r/{self.subreddit}/hot.json?limit=50&raw_json=1",
            ]
            for endpoint in endpoints:
                for attempt in range(settings.MAX_RETRIES):
                    try:
                        await _rate_limiter.throttle("reddit.com")
                        headers = get_request_headers()
                        resp = await client.get(endpoint, headers=headers)

                        if resp.status_code == 200:
                            memes = self.parse_listing_json(resp.text)
                            latency_ms = (time.monotonic() - start_time) * 1000.0
                            self.update_success(len(memes), latency_ms)
                            return memes

                        if resp.status_code in (429, 403, 500, 502, 503, 504):
                            backoff = calculate_backoff_delay(attempt, resp.headers)
                            logger.warning(
                                f"Reddit [{self.name}] HTTP {resp.status_code}. "
                                f"Attempt {attempt + 1}/{settings.MAX_RETRIES}, backing off {backoff:.2f}s"
                            )
                            await asyncio.sleep(backoff)
                            continue

                        break

                    except (httpx.TimeoutException, httpx.NetworkError) as net_err:
                        backoff = calculate_backoff_delay(attempt)
                        logger.warning(
                            f"Reddit [{self.name}] network error: {net_err}. "
                            f"Retrying in {backoff:.2f}s"
                        )
                        await asyncio.sleep(backoff)

            logger.info(f"Live fetch failed for {self.name}; falling back to offline fixtures.")
            return self.load_offline_fixtures()

        except Exception as exc:
            self.update_failure(exc)
            logger.error(f"Ingestion failed for {self.name}: {exc}")
            return self.load_offline_fixtures()

        finally:
            if should_close:
                await client.aclose()


RedditMemeFetcher = RedditFetcher
