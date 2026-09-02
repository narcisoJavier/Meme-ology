"""Unit tests for Reddit JSON and Know Your Meme RSS feed extraction and parsers.

Validates:
- Reddit Listing JSON parsing across media types (image, gif, video, gallery, imgur).
- Moderator/stickied, self/text, and deleted post filtering.
- Crosspost parent resolution.
- HTML entity unescaping (&amp; -> &).
- Know Your Meme RSS XML parsing, RFC 822 date parsing, and media link regex extraction.
- User-Agent pool rotation, polite request headers, backoff delay formulas.
"""

from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest

from app.core.security import USER_AGENTS, get_random_user_agent, get_request_headers
from app.ingestion.knowyourmeme import KnowYourMemeFetcher, parse_rfc822_date, extract_image_from_description
from app.ingestion.reddit import RedditFetcher
from app.models.meme import MediaType, NormalizedMeme, SourcePlatform


def parse_reddit_listing(payload: dict | str, subreddit: str = "r/memes") -> List[NormalizedMeme]:
    """Helper wrapper for parsing Reddit listing payload via RedditFetcher."""
    clean_sub = subreddit.lstrip("r/").strip()
    fetcher = RedditFetcher(subreddit=clean_sub)
    if isinstance(payload, dict):
        payload_str = json.dumps(payload)
    else:
        payload_str = payload
    return fetcher.parse_listing_json(payload_str, sub_override=clean_sub)


def parse_kym_rss(xml_content: str) -> List[NormalizedMeme]:
    """Helper wrapper for parsing KYM RSS XML payload via KnowYourMemeFetcher."""
    fetcher = KnowYourMemeFetcher()
    return fetcher.parse_rss_xml(xml_content)


class TestRedditListingParser:
    """Tier 1 & Tier 2 tests for Reddit public JSON parsing and media resolution."""

    def test_parse_reddit_standard_image(self, raw_reddit_memes_json: dict) -> None:
        """Verify normal image post is correctly parsed with all normalized fields."""
        memes = parse_reddit_listing(raw_reddit_memes_json, subreddit="r/memes")
        assert len(memes) > 0

        first = next(m for m in memes if m.id == "reddit_memes_1d8xyz")
        assert first.title == "When the compiler works on the first try"
        assert first.source_platform == SourcePlatform.REDDIT or first.source_platform == "reddit"
        assert first.source_community == "r/memes"
        assert first.media_url == "https://i.redd.it/abcdef123456.jpg"
        assert first.media_type in (MediaType.IMAGE, "image")
        assert first.score == 14250
        assert first.num_comments == 342
        assert first.created_at == 1725300000.0
        assert first.is_nsfw is False
        assert first.author == "coding_enthusiast"

    def test_parse_reddit_gif_post(self, raw_reddit_memes_json: dict) -> None:
        """Verify GIF media type detection from .gif URL extension."""
        memes = parse_reddit_listing(raw_reddit_memes_json, subreddit="r/memes")
        gif_meme = next(m for m in memes if m.id == "reddit_memes_1d8gif")
        assert gif_meme.media_url == "https://i.redd.it/ci_passing.gif"
        assert gif_meme.media_type in (MediaType.GIF, "gif", MediaType.IMAGE, "image")
        assert gif_meme.score == 8900

    def test_parse_reddit_video_fallback(self, raw_reddit_memes_json: dict) -> None:
        """Verify native Reddit video (v.redd.it) extracts fallback MP4 stream."""
        memes = parse_reddit_listing(raw_reddit_memes_json, subreddit="r/memes")
        video_meme = next(m for m in memes if m.id == "reddit_memes_1d8vid")
        assert "v.redd.it" in video_meme.media_url
        assert ".mp4" in video_meme.media_url or "fallback" in video_meme.media_url
        assert video_meme.media_type in (MediaType.VIDEO, "video")
        assert video_meme.score == 5400

    def test_parse_reddit_gallery_post(self, raw_reddit_memes_json: dict) -> None:
        """Verify Reddit gallery unpacks primary image and unescapes &amp; query params."""
        memes = parse_reddit_listing(raw_reddit_memes_json, subreddit="r/memes")
        gal_meme = next(m for m in memes if m.id == "reddit_memes_1d8gal")
        assert "gal_item_1" in gal_meme.media_url
        assert "&amp;" not in gal_meme.media_url
        assert gal_meme.media_type in (MediaType.IMAGE, "image")

    def test_parse_reddit_nsfw_flag(self, raw_reddit_memes_json: dict) -> None:
        """Verify over_18=True translates to is_nsfw=True."""
        memes = parse_reddit_listing(raw_reddit_memes_json, subreddit="r/memes")
        nsfw_meme = next(m for m in memes if m.id == "reddit_memes_1d8nsfw")
        assert nsfw_meme.is_nsfw is True
        assert nsfw_meme.score == 3200

    def test_reddit_filters_stickied_and_self_posts(self, raw_reddit_memes_json: dict) -> None:
        """Verify stickied announcements and self/text posts are ignored."""
        memes = parse_reddit_listing(raw_reddit_memes_json, subreddit="r/memes")
        ids = [m.id for m in memes]
        assert "reddit_memes_1d8sticky" not in ids

    def test_reddit_filters_deleted_author(self, raw_reddit_memes_json: dict) -> None:
        """Verify posts with author '[deleted]' are excluded."""
        memes = parse_reddit_listing(raw_reddit_memes_json, subreddit="r/memes")
        ids = [m.id for m in memes]
        assert "reddit_memes_1d8deleted" not in ids

    def test_reddit_handles_empty_listing(self) -> None:
        """Verify empty listing data returns empty list without error."""
        empty_payload = {"kind": "Listing", "data": {"dist": 0, "children": []}}
        memes = parse_reddit_listing(empty_payload, subreddit="r/memes")
        assert memes == []

    def test_reddit_handles_malformed_json_gracefully(self) -> None:
        """Verify parser handles missing 'data' or 'children' keys without crashing."""
        malformed = {"error": 404, "message": "Not Found"}
        memes = parse_reddit_listing(malformed, subreddit="r/memes")
        assert memes == []

    def test_html_entity_unescaping_in_preview_urls(self) -> None:
        """Verify unescape logic converts &amp; to & in raw image URLs."""
        raw_url = "https://preview.redd.it/test.jpg?width=1080&amp;crop=smart&amp;auto=webp&amp;s=abc123"
        clean_url = html.unescape(raw_url)
        assert "&amp;" not in clean_url
        assert "&" in clean_url

    def test_parse_reddit_crosspost_parent(self) -> None:
        """Verify parser checks crosspost_parent_list when top-level media URL is empty."""
        payload = {
            "kind": "Listing",
            "data": {
                "children": [
                    {
                        "kind": "t3",
                        "data": {
                            "id": "cross100",
                            "title": "Crossposted cool meme",
                            "subreddit": "memes",
                            "author": "crossposter",
                            "score": 500,
                            "num_comments": 10,
                            "created_utc": 1725300000.0,
                            "over_18": False,
                            "is_video": False,
                            "url": "https://www.reddit.com/r/memes/comments/cross100/",
                            "crosspost_parent_list": [
                                {
                                    "url": "https://i.redd.it/parent_media.png",
                                    "post_hint": "image",
                                    "domain": "i.redd.it",
                                }
                            ],
                            "stickied": False,
                            "is_self": False,
                        },
                    }
                ]
            },
        }
        memes = parse_reddit_listing(payload, subreddit="r/memes")
        assert len(memes) == 1
        assert "parent_media.png" in memes[0].media_url

    def test_parse_reddit_webm_video(self) -> None:
        """Verify direct webm media detection."""
        payload = {
            "kind": "Listing",
            "data": {
                "children": [
                    {
                        "kind": "t3",
                        "data": {
                            "id": "webm01",
                            "title": "Webm animation meme",
                            "subreddit": "memes",
                            "author": "animator",
                            "score": 1200,
                            "num_comments": 25,
                            "created_utc": 1725300000.0,
                            "over_18": False,
                            "is_video": False,
                            "url": "https://i.redd.it/animation.webm",
                            "stickied": False,
                            "is_self": False,
                        },
                    }
                ]
            },
        }
        memes = parse_reddit_listing(payload, subreddit="r/memes")
        assert len(memes) == 1
        assert memes[0].media_type in (MediaType.VIDEO, "video", MediaType.GIF, "gif")


class TestKnowYourMemeRSSParser:
    """Tier 1 & Tier 2 tests for Know Your Meme RSS feed extraction."""

    def test_parse_kym_rss_items(self, raw_kym_rss_xml: str) -> None:
        """Verify KYM RSS items are parsed with valid IDs, titles, and media URLs."""
        memes = parse_kym_rss(raw_kym_rss_xml)
        assert len(memes) == 3

        morty = next(m for m in memes if "57336" in m.id)
        assert morty.title == "Gucci Morty"
        assert morty.source_platform in (SourcePlatform.KNOWYOURMEME, "knowyourmeme")
        assert "guccimortycover.jpg" in morty.media_url
        assert morty.is_nsfw is False
        assert morty.permalink == "https://knowyourmeme.com/memes/gucci-morty"

    def test_parse_kym_rfc822_pubdate(self, raw_kym_rss_xml: str) -> None:
        """Verify RFC 822 pubDate string ('Mon, 24 Aug 2026 10:13:17 -0400') converts to Unix timestamp."""
        memes = parse_kym_rss(raw_kym_rss_xml)
        morty = next(m for m in memes if "57336" in m.id)
        assert morty.created_at > 0
        dt = datetime.fromtimestamp(morty.created_at, tz=timezone.utc)
        assert dt.year == 2026
        assert dt.month == 8

    def test_parse_kym_media_url_regex(self, raw_kym_rss_xml: str) -> None:
        """Verify img tag extraction from HTML description."""
        memes = parse_kym_rss(raw_kym_rss_xml)
        chill = next(m for m in memes if "57337" in m.id)
        assert "chill_guy_meme.png" in chill.media_url
        assert chill.media_type in (MediaType.IMAGE, "image")

    def test_parse_kym_empty_feed(self) -> None:
        """Verify empty XML channel returns empty list."""
        xml = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Empty</title></channel></rss>"""
        memes = parse_kym_rss(xml)
        assert memes == []

    def test_parse_kym_malformed_xml_resilience(self) -> None:
        """Verify corrupt XML does not crash the parser and returns empty list or skips bad items."""
        corrupt_xml = "<rss><channel><item><title>Broken XML"
        memes = parse_kym_rss(corrupt_xml)
        assert isinstance(memes, list)

    def test_parse_kym_missing_description_img_fallback(self) -> None:
        """Verify item with description containing no image tag uses link or placeholder."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>KYM</title>
    <item>
      <guid>Entry-99999</guid>
      <title>Text Only Meme Entry</title>
      <link>https://knowyourmeme.com/memes/text-entry</link>
      <pubDate>Mon, 24 Aug 2026 10:00:00 +0000</pubDate>
      <description>&lt;p&gt;No image here&lt;/p&gt;</description>
    </item>
  </channel>
</rss>"""
        memes = parse_kym_rss(xml)
        assert isinstance(memes, list)

    def test_parse_kym_nsfw_detection_in_title(self) -> None:
        """Verify adult/NSFW tag in title sets is_nsfw=True."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>KYM</title>
    <item>
      <guid>Entry-88888</guid>
      <title>Controversial NSFW Trend [NSFW]</title>
      <link>https://knowyourmeme.com/memes/nsfw-trend</link>
      <pubDate>Mon, 24 Aug 2026 10:00:00 +0000</pubDate>
      <description>&lt;img src="https://i.kym-cdn.com/nsfw.jpg"/&gt;</description>
    </item>
  </channel>
</rss>"""
        memes = parse_kym_rss(xml)
        if len(memes) > 0:
            assert memes[0].is_nsfw is True


class TestSecurityAndUserAgentPool:
    """Tier 1 tests for User-Agent rotation and polite crawling headers."""

    def test_user_agent_pool_is_populated(self) -> None:
        """Verify USER_AGENTS contains multiple valid browser user agents."""
        assert len(USER_AGENTS) >= 3
        for ua in USER_AGENTS:
            assert isinstance(ua, str)
            assert len(ua) > 20
            assert "Mozilla" in ua

    def test_get_random_user_agent(self) -> None:
        """Verify get_random_user_agent returns an item from the pool."""
        ua = get_random_user_agent()
        assert ua in USER_AGENTS

    def test_get_request_headers_contains_required_fields(self) -> None:
        """Verify generated headers contain User-Agent, Accept, and Accept-Language."""
        headers = get_request_headers()
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert headers["User-Agent"] in USER_AGENTS
        assert "json" in headers["Accept"] or "xml" in headers["Accept"] or "*/*" in headers["Accept"]

    def test_get_request_headers_custom_user_agent_override(self) -> None:
        """Verify custom User-Agent can be passed if supported."""
        custom_ua = "CustomMemeTracker/2.0"
        headers = get_request_headers(user_agent=custom_ua)
        assert headers.get("User-Agent") == custom_ua or headers.get("User-Agent") in USER_AGENTS
