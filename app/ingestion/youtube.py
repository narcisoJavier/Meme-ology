"""YouTube RSS feed ingestion engine for meme channels."""

import asyncio
import html
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

try:
    import defusedxml.ElementTree as SafeET
except ImportError:
    SafeET = ET

import httpx

from app.config import get_settings
from app.core.security import (
    PoliteRateLimiter,
    calculate_backoff_delay,
    get_request_headers,
)
from app.core.dedup import compute_content_hash
from app.core.ranking import calculate_trending_score
from app.ingestion.base import BaseSourceFetcher
from app.models.meme import MediaType, NormalizedMeme, SourcePlatform

logger = logging.getLogger(__name__)

# Global per-domain rate limiter
_rate_limiter = PoliteRateLimiter(min_interval_seconds=1.0)


CHANNEL_NAMES = {
    "UCaHT88aobpcvRFEuy4v5Clg": "Lessons in Meme Culture",
    "UCbrPqq29C9Q_TQP7OFFRzcw": "Know Your Meme Video",
    "UCq9UQ0TUfI9GyzSiZ2uNx5Q": "Daily Dose of Memes",
    "UC9sY9S-ddN-1E0jD2fFWLig": "Grandayy",
    "UC2vpvibGYfBcb14l6CLVdiA": "Memer Man",
}


class YouTubeFetcher(BaseSourceFetcher):
    """Fetches and normalizes meme videos and Shorts from YouTube channels."""

    def __init__(
        self,
        channel_id: str = "UCaHT88aobpcvRFEuy4v5Clg",
        http_client: Optional[httpx.AsyncClient] = None,
        fixture_json_path: Optional[Path] = None,
    ) -> None:
        comm_name = CHANNEL_NAMES.get(channel_id, channel_id)
        super().__init__(
            name=f"youtube:{channel_id}",
            platform=SourcePlatform.YOUTUBE,
            community=comm_name,
        )
        self.channel_id = channel_id
        self.channel_name = comm_name
        self.feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        self._custom_client = http_client
        self.fixture_json_path = fixture_json_path or self._resolve_default_fixture_json_path()

    def _resolve_default_fixture_json_path(self) -> Path:
        root = Path(__file__).resolve().parent.parent.parent
        return root / "data" / "fixtures" / "youtube_limc.json"

    def parse_atom_xml(self, xml_content: str) -> List[NormalizedMeme]:
        """Parse YouTube Atom XML string into NormalizedMeme instances."""
        try:
            root = SafeET.fromstring(xml_content)
        except Exception as e:
            logger.warning(f"Failed to parse YouTube Atom XML: {e}")
            return []

        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "yt": "http://www.youtube.com/xml/schemas/2015",
            "media": "http://search.yahoo.com/mrss/"
        }

        results: List[NormalizedMeme] = []

        feed_author_elem = root.find("atom:author/atom:name", ns)
        feed_author = feed_author_elem.text if feed_author_elem is not None and feed_author_elem.text else self.channel_name

        for entry in root.findall("atom:entry", ns):
            try:
                yt_video_id_elem = entry.find("yt:videoId", ns)
                video_id = yt_video_id_elem.text if yt_video_id_elem is not None else ""
                if not video_id:
                    continue

                raw_id = video_id
                meme_id = f"youtube_{raw_id}"

                media_group = entry.find("media:group", ns)
                title = ""
                if media_group is not None:
                    title_elem = media_group.find("media:title", ns)
                    if title_elem is not None and title_elem.text:
                        title = title_elem.text
                if not title:
                    title_elem = entry.find("atom:title", ns)
                    title = title_elem.text if title_elem is not None else ""
                
                title = html.unescape(title).strip()

                author_elem = entry.find("atom:author/atom:name", ns)
                author = author_elem.text if author_elem is not None and author_elem.text else feed_author

                published_elem = entry.find("atom:published", ns)
                created_at = time.time()
                if published_elem is not None and published_elem.text:
                    try:
                        # Parse ISO 8601 string to Unix timestamp
                        dt = datetime.fromisoformat(published_elem.text.replace('Z', '+00:00'))
                        created_at = dt.timestamp()
                    except ValueError:
                        pass

                score = 0
                num_comments = 0
                if media_group is not None:
                    stats_elem = media_group.find("media:community/media:statistics", ns)
                    if stats_elem is not None and stats_elem.get("views"):
                        score = int(stats_elem.get("views"))
                        
                    rating_elem = media_group.find("media:community/media:starRating", ns)
                    if rating_elem is not None and rating_elem.get("count"):
                        num_comments = int(rating_elem.get("count"))

                # Detect if item is a YouTube Short (from alternate link or title)
                link_elem = entry.find("atom:link[@rel='alternate']", ns)
                if link_elem is not None and link_elem.get("href"):
                    permalink = link_elem.get("href")
                else:
                    permalink = f"https://www.youtube.com/watch?v={video_id}"

                is_short = "/shorts/" in permalink or "#shorts" in title.lower()

                media_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                content_hash = compute_content_hash(media_url, title)
                trending_score = calculate_trending_score(score, num_comments, created_at)

                meme = NormalizedMeme(
                    id=meme_id,
                    raw_id=raw_id,
                    title=title,
                    media_url=media_url,
                    media_type=MediaType.VIDEO,
                    source_platform=SourcePlatform.YOUTUBE,
                    source_community=author or self.channel_name,
                    permalink=permalink,
                    author=author or self.channel_name,
                    score=score,
                    num_comments=num_comments,
                    created_at=created_at,
                    is_nsfw=False,
                    domain="youtube.com",
                    content_hash=content_hash,
                    trending_score=trending_score,
                    is_short=is_short,
                    source_category="video_creator",
                )
                results.append(meme)
            except Exception as item_err:
                logger.debug(f"Error parsing single YouTube XML item: {item_err}")
                continue

        return results

    def load_offline_fixtures(self) -> List[NormalizedMeme]:
        """Load memes from local offline JSON fixture."""
        results: List[NormalizedMeme] = []

        if self.fixture_json_path.exists():
            try:
                import json
                json_content = self.fixture_json_path.read_text(encoding="utf-8")
                items = json.loads(json_content)
                for item in items:
                    raw_id = str(item.get("raw_id", ""))
                    title = str(item.get("title", ""))
                    media_url = str(item.get("media_url", ""))
                    if not raw_id or not title or not media_url:
                        continue
                        
                    created_at = float(item.get("created_at", time.time()))
                    score = int(item.get("score", 0))
                    num_comments = int(item.get("num_comments", 0))
                    permalink = item.get("permalink", f"https://www.youtube.com/watch?v={raw_id}")
                    is_short = bool(item.get("is_short", False) or "/shorts/" in permalink or "#shorts" in title.lower())
                    
                    meme = NormalizedMeme(
                        id=f"youtube_{raw_id}",
                        raw_id=raw_id,
                        title=title,
                        media_url=media_url,
                        media_type=MediaType.VIDEO,
                        source_platform=SourcePlatform.YOUTUBE,
                        source_community=item.get("source_community", self.channel_name),
                        permalink=permalink,
                        author=item.get("author", self.channel_name),
                        score=score,
                        num_comments=num_comments,
                        created_at=created_at,
                        is_nsfw=False,
                        domain="youtube.com",
                        content_hash=compute_content_hash(media_url, title),
                        trending_score=calculate_trending_score(score, num_comments, created_at),
                        is_short=is_short,
                        source_category="video_creator",
                    )
                    results.append(meme)
            except Exception as e:
                logger.error(f"Error loading YouTube JSON fixture {self.fixture_json_path}: {e}")

        if results:
            self.update_success(len(results), latency_ms=0.5)
        else:
            self.update_failure(FileNotFoundError("No valid YouTube fixtures found"))

        return results

    async def fetch_memes(self) -> List[NormalizedMeme]:
        """Fetch memes from live YouTube RSS feed with retry and fallback to fixtures."""
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
            for attempt in range(settings.MAX_RETRIES):
                try:
                    await _rate_limiter.throttle("youtube.com")
                    headers = get_request_headers(
                        accept="application/atom+xml, application/xml, text/xml, */*;q=0.9"
                    )
                    resp = await client.get(self.feed_url, headers=headers)

                    if resp.status_code == 200:
                        memes = self.parse_atom_xml(resp.text)
                        
                        latency_ms = (time.monotonic() - start_time) * 1000.0
                        self.update_success(len(memes), latency_ms)
                        return memes

                    if resp.status_code in (429, 403, 500, 502, 503, 504):
                        backoff = calculate_backoff_delay(attempt, resp.headers)
                        logger.warning(
                            f"YouTube [{self.name}] HTTP {resp.status_code}. "
                            f"Attempt {attempt + 1}/{settings.MAX_RETRIES}, backing off {backoff:.2f}s"
                        )
                        await asyncio.sleep(backoff)
                        continue

                    break

                except (httpx.TimeoutException, httpx.NetworkError) as net_err:
                    backoff = calculate_backoff_delay(attempt)
                    logger.warning(
                        f"YouTube [{self.name}] network error: {net_err}. "
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
