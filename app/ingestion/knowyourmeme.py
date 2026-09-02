"""Know Your Meme (KYM) RSS and trending feed ingestion engine."""

import asyncio
import email.utils
import html
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET

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
from app.core.dedup import compute_content_hash, normalize_url
from app.core.ranking import calculate_trending_score
from app.ingestion.base import BaseSourceFetcher
from app.models.meme import MediaType, NormalizedMeme, SourcePlatform

logger = logging.getLogger(__name__)

# Global per-domain rate limiter
_rate_limiter = PoliteRateLimiter(min_interval_seconds=1.0)


def parse_rfc822_date(date_str: Optional[str]) -> float:
    """Parse RFC 822 / 2822 pubDate string to Unix timestamp in seconds."""
    if not date_str:
        return time.time()
    try:
        dt = email.utils.parsedate_to_datetime(date_str.strip())
        return dt.timestamp()
    except Exception as e:
        logger.debug(f"Failed to parse RFC 822 date '{date_str}': {e}")
        return time.time()


def extract_image_from_description(description_html: Optional[str]) -> Optional[str]:
    """Extract image URL from HTML description tag using regex."""
    if not description_html:
        return None
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', description_html, re.IGNORECASE)
    if match:
        return html.unescape(match.group(1).strip())
    return None


def parse_kym_rss(xml_content: str, category: str = "confirmed") -> List[NormalizedMeme]:
    """Top-level helper function to parse KYM RSS XML string into normalized memes."""
    fetcher = KnowYourMemeFetcher(category=category)
    return fetcher.parse_rss_xml(xml_content)


class KnowYourMemeFetcher(BaseSourceFetcher):
    """Fetches and normalizes meme entries from Know Your Meme RSS and trending feeds."""

    def __init__(
        self,
        feed_url: str = "https://knowyourmeme.com/memes.rss",
        category: str = "confirmed",
        http_client: Optional[httpx.AsyncClient] = None,
        fixture_xml_path: Optional[Path] = None,
        fixture_json_path: Optional[Path] = None,
    ) -> None:
        super().__init__(
            name=f"knowyourmeme:{category}",
            platform=SourcePlatform.KNOWYOURMEME,
            community=category,
        )
        self.feed_url = feed_url
        self.category = category
        self._custom_client = http_client
        self.fixture_xml_path = fixture_xml_path or self._resolve_default_fixture_xml_path()
        self.fixture_json_path = fixture_json_path or self._resolve_default_fixture_json_path()

    def _resolve_default_fixture_xml_path(self) -> Path:
        root = Path(__file__).resolve().parent.parent.parent
        return root / "data" / "fixtures" / "kym_memes.xml"

    def _resolve_default_fixture_json_path(self) -> Path:
        root = Path(__file__).resolve().parent.parent.parent
        return root / "data" / "fixtures" / "kym_trending.json"

    def parse_rss_xml(self, xml_content: str) -> List[NormalizedMeme]:
        """Parse RSS 2.0 XML string into NormalizedMeme instances."""
        try:
            root = SafeET.fromstring(xml_content)
        except Exception as e:
            logger.warning(f"Failed to parse KYM RSS XML: {e}")
            return []

        channel = root.find("channel")
        if channel is None:
            channel = root

        items = channel.findall("item")
        results: List[NormalizedMeme] = []

        for item in items:
            try:
                title_elem = item.find("title")
                title = html.unescape(title_elem.text or "").strip() if title_elem is not None else ""
                if not title:
                    continue

                guid_elem = item.find("guid")
                guid = guid_elem.text.strip() if (guid_elem is not None and guid_elem.text) else ""
                raw_id = guid if guid else re.sub(r"[^a-zA-Z0-9_-]", "_", title)
                raw_id = raw_id.replace("https://knowyourmeme.com/memes/", "").replace("/", "_")
                meme_id = f"kym_{raw_id}"

                link_elem = item.find("link")
                permalink = link_elem.text.strip() if (link_elem is not None and link_elem.text) else ""

                pubdate_elem = item.find("pubDate")
                pubdate_str = pubdate_elem.text if pubdate_elem is not None else ""
                created_at = parse_rfc822_date(pubdate_str)

                desc_elem = item.find("description")
                desc_text = desc_elem.text if desc_elem is not None else ""
                media_url = extract_image_from_description(desc_text)

                if not media_url:
                    enclosure = item.find("enclosure")
                    if enclosure is not None and enclosure.get("url"):
                        media_url = enclosure.get("url")

                if not media_url:
                    media_url = "https://i.kym-cdn.com/photos/images/original/000/000/000/kym_placeholder.jpg"

                lower_url = media_url.lower()
                media_type = MediaType.GIF if lower_url.endswith(".gif") else MediaType.IMAGE
                domain = "i.kym-cdn.com" if "kym-cdn.com" in lower_url else "knowyourmeme.com"

                is_nsfw = bool(re.search(r"\b(nsfw|explicit|adult)\b|\[nsfw\]", (title + " " + desc_text).lower()))

                score = 100
                num_comments = 10
                content_hash = compute_content_hash(media_url, title)
                trending_score = calculate_trending_score(score, num_comments, created_at)

                meme = NormalizedMeme(
                    id=meme_id,
                    raw_id=raw_id,
                    title=title,
                    media_url=media_url,
                    media_type=media_type,
                    source_platform=SourcePlatform.KNOWYOURMEME,
                    source_community=self.category,
                    permalink=permalink or f"https://knowyourmeme.com/memes/{raw_id}",
                    author="Know Your Meme",
                    score=score,
                    num_comments=num_comments,
                    created_at=created_at,
                    is_nsfw=is_nsfw,
                    domain=domain,
                    content_hash=content_hash,
                    trending_score=trending_score,
                )
                results.append(meme)
            except Exception as item_err:
                logger.debug(f"Error parsing single KYM XML item: {item_err}")
                continue

        return results

    def parse_trending_json(self, json_content: str) -> List[NormalizedMeme]:
        """Parse trending JSON payload into NormalizedMeme instances."""
        try:
            items = json.loads(json_content)
        except Exception as e:
            logger.warning(f"Failed to parse KYM trending JSON: {e}")
            return []

        results: List[NormalizedMeme] = []
        for item in items:
            try:
                raw_id = str(item.get("id") or item.get("raw_id") or "")
                raw_id = raw_id.replace("kym_", "")
                title = str(item.get("title") or "").strip()
                media_url = str(item.get("media_url") or item.get("url") or "")
                if not title or not media_url:
                    continue

                meme_id = f"kym_{raw_id}"
                permalink = str(item.get("permalink") or f"https://knowyourmeme.com/photos/{raw_id}")
                author = str(item.get("author") or "Know Your Meme")
                score = int(item.get("score") or 100)
                num_comments = int(item.get("num_comments") or 0)
                created_at = float(item.get("created_at") or time.time())
                is_nsfw = bool(item.get("is_nsfw", False))

                lower_url = media_url.lower()
                media_type = MediaType.GIF if lower_url.endswith(".gif") else MediaType.IMAGE
                domain = "i.kym-cdn.com" if "kym-cdn.com" in lower_url else "knowyourmeme.com"

                content_hash = compute_content_hash(media_url, title)
                trending_score = calculate_trending_score(score, num_comments, created_at)

                meme = NormalizedMeme(
                    id=meme_id,
                    raw_id=raw_id,
                    title=title,
                    media_url=media_url,
                    media_type=media_type,
                    source_platform=SourcePlatform.KNOWYOURMEME,
                    source_community=self.category,
                    permalink=permalink,
                    author=author,
                    score=score,
                    num_comments=num_comments,
                    created_at=created_at,
                    is_nsfw=is_nsfw,
                    domain=domain,
                    content_hash=content_hash,
                    trending_score=trending_score,
                )
                results.append(meme)
            except Exception as item_err:
                logger.debug(f"Error parsing single KYM JSON item: {item_err}")
                continue

        return results

    def load_offline_fixtures(self) -> List[NormalizedMeme]:
        """Load memes from local offline XML or JSON fixtures."""
        results: List[NormalizedMeme] = []

        if self.fixture_xml_path.exists():
            try:
                xml_content = self.fixture_xml_path.read_text(encoding="utf-8")
                xml_memes = self.parse_rss_xml(xml_content)
                results.extend(xml_memes)
            except Exception as e:
                logger.error(f"Error loading KYM XML fixture {self.fixture_xml_path}: {e}")

        if self.fixture_json_path.exists():
            try:
                json_content = self.fixture_json_path.read_text(encoding="utf-8")
                json_memes = self.parse_trending_json(json_content)
                results.extend(json_memes)
            except Exception as e:
                logger.error(f"Error loading KYM JSON fixture {self.fixture_json_path}: {e}")

        if results:
            self.update_success(len(results), latency_ms=0.5)
        else:
            self.update_failure(FileNotFoundError("No valid KYM fixtures found"))

        return results

    async def fetch_memes(self) -> List[NormalizedMeme]:
        """Fetch memes from live KYM RSS feed with retry and fallback to fixtures."""
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
                    await _rate_limiter.throttle("knowyourmeme.com")
                    headers = get_request_headers(
                        accept="application/rss+xml, application/xml, text/xml, text/html, */*;q=0.9"
                    )
                    resp = await client.get(self.feed_url, headers=headers)

                    if resp.status_code == 200:
                        memes = self.parse_rss_xml(resp.text)
                        if not memes and "json" in resp.headers.get("content-type", ""):
                            memes = self.parse_trending_json(resp.text)

                        latency_ms = (time.monotonic() - start_time) * 1000.0
                        self.update_success(len(memes), latency_ms)
                        return memes

                    if resp.status_code in (429, 403, 500, 502, 503, 504):
                        backoff = calculate_backoff_delay(attempt, resp.headers)
                        logger.warning(
                            f"KYM [{self.name}] HTTP {resp.status_code}. "
                            f"Attempt {attempt + 1}/{settings.MAX_RETRIES}, backing off {backoff:.2f}s"
                        )
                        await asyncio.sleep(backoff)
                        continue

                    break

                except (httpx.TimeoutException, httpx.NetworkError) as net_err:
                    backoff = calculate_backoff_delay(attempt)
                    logger.warning(
                        f"KYM [{self.name}] network error: {net_err}. "
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
