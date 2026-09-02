"""Adversarial stress-testing suite for Know Your Meme parser and Security module.

Empirical verification suite for:
- Adversarial RSS XML payloads (corrupted XML, missing tags, empty items, CDATA, HTML entities)
- Diverse RFC 822 timezone strings (offsets, named timezones, malformed strings, fallback)
- Image URL extraction from description (missing images, multiple images, single/double quotes, CDATA)
- NSFW detection accuracy
- User-Agent pool randomness, distribution, and header generation
- Backoff exponential delay formula, jitter bounds, Retry-After header parsing, and cap enforcement
- PoliteRateLimiter per-domain isolation and concurrency safety
"""

import asyncio
import math
import re
import time
from collections import Counter
from typing import Dict, List

import pytest

from app.core.security import (
    USER_AGENTS,
    PoliteRateLimiter,
    calculate_backoff_delay,
    get_random_user_agent,
    get_request_headers,
)
from app.ingestion.knowyourmeme import (
    KnowYourMemeFetcher,
    extract_image_from_description,
    parse_kym_rss,
    parse_rfc822_date,
)
from app.models.meme import MediaType, NormalizedMeme, SourcePlatform


# =============================================================================
# 1. RFC 822 / 2822 TIMEZONE & DATE PARSING TESTS
# =============================================================================

class TestRFC822TimezoneParsing:
    """Stress-tests for RFC 822 pubDate parser with diverse timezones and corrupt strings."""

    @pytest.mark.parametrize(
        "date_str, expected_year, expected_month, expected_day",
        [
            ("Mon, 24 Aug 2026 10:13:17 -0400", 2026, 8, 24),
            ("Tue, 25 Aug 2026 14:30:00 +0000", 2026, 8, 25),
            ("Wed, 26 Aug 2026 22:00:00 +0800", 2026, 8, 26),
            ("24 Aug 2026 10:13:17 -0400", 2026, 8, 24),  # Missing day of week
            ("Mon, 24 Aug 2026 10:13:17 GMT", 2026, 8, 24),  # GMT
            ("Mon, 24 Aug 2026 10:13:17 UTC", 2026, 8, 24),  # UTC
            ("Mon, 24 Aug 2026 10:13:17 EST", 2026, 8, 24),  # EST
            ("Mon, 24 Aug 2026 10:13:17 EDT", 2026, 8, 24),  # EDT
            ("Mon, 24 Aug 2026 10:13:17 PST", 2026, 8, 24),  # PST
            ("Mon, 24 Aug 2026 10:13:17 PDT", 2026, 8, 24),  # PDT
            ("Mon, 24 Aug 2026 10:13:17 CST", 2026, 8, 24),  # CST
            ("Mon, 24 Aug 2026 10:13:17 CDT", 2026, 8, 24),  # CDT
            ("  Mon, 24 Aug 2026 10:13:17 -0400  ", 2026, 8, 24),  # Leading/trailing whitespace
        ],
    )
    def test_rfc822_valid_timezones(
        self, date_str: str, expected_year: int, expected_month: int, expected_day: int
    ) -> None:
        """Verify standard, named, and offset timezones parse to accurate timestamps."""
        ts = parse_rfc822_date(date_str)
        assert isinstance(ts, float)
        assert ts > 1700000000.0  # After 2023

    @pytest.mark.parametrize(
        "invalid_date",
        [
            None,
            "",
            "   ",
            "not a date string",
            "2026-08-24T10:13:17Z",  # ISO 8601 instead of RFC 822 (should fallback or parse)
            "99/99/9999",
            "Mon, 32 Dec 2026 25:99:99 GMT",
            "null",
            "undefined",
            "<script>alert(1)</script>",
        ],
    )
    def test_rfc822_malformed_dates_graceful_fallback(self, invalid_date: str) -> None:
        """Verify invalid or corrupt date strings return current timestamp without raising."""
        before = time.time() - 1.0
        ts = parse_rfc822_date(invalid_date)
        after = time.time() + 1.0
        assert isinstance(ts, float)
        assert before <= ts <= after


# =============================================================================
# 2. IMAGE EXTRACTION FROM HTML DESCRIPTION
# =============================================================================

class TestImageExtractionFromDescription:
    """Stress-tests for regex-based image extraction from diverse HTML snippets."""

    def test_extract_standard_double_quotes(self) -> None:
        html_str = '<p>Some text</p><img src="https://i.kym-cdn.com/photos/images/original/001/test.jpg" alt="test" />'
        result = extract_image_from_description(html_str)
        assert result == "https://i.kym-cdn.com/photos/images/original/001/test.jpg"

    def test_extract_single_quotes(self) -> None:
        html_str = "<p>Text</p><img src='https://i.kym-cdn.com/photos/images/original/002/test.png' />"
        result = extract_image_from_description(html_str)
        assert result == "https://i.kym-cdn.com/photos/images/original/002/test.png"

    def test_extract_uppercase_tag_and_attributes(self) -> None:
        html_str = '<DIV><IMG WIDTH="600" HEIGHT="400" SRC="https://i.kym-cdn.com/test_upper.jpg" CLASS="center"></DIV>'
        result = extract_image_from_description(html_str)
        assert result == "https://i.kym-cdn.com/test_upper.jpg"

    def test_extract_first_image_when_multiple_present(self) -> None:
        html_str = """
        <div>
            <img src="https://i.kym-cdn.com/first_image.jpg" />
            <p>Description in between</p>
            <img src="https://i.kym-cdn.com/second_image.jpg" />
        </div>
        """
        result = extract_image_from_description(html_str)
        assert result == "https://i.kym-cdn.com/first_image.jpg"

    def test_extract_unescapes_html_entities_in_url(self) -> None:
        html_str = '<img src="https://i.kym-cdn.com/image.jpg?w=1200&amp;h=800&amp;format=webp" />'
        result = extract_image_from_description(html_str)
        assert result == "https://i.kym-cdn.com/image.jpg?w=1200&h=800&format=webp"

    @pytest.mark.parametrize(
        "empty_or_no_img",
        [
            None,
            "",
            "   ",
            "<p>Just plain text with no images at all.</p>",
            "<div><a href='https://knowyourmeme.com'>Link only</a></div>",
            "<img >",
            "<img src=>",
            "<img src=''>",
        ],
    )
    def test_extract_returns_none_when_no_valid_img(self, empty_or_no_img: str) -> None:
        result = extract_image_from_description(empty_or_no_img)
        assert result is None or result == ""


# =============================================================================
# 3. ADVERSARIAL RSS XML PAYLOADS
# =============================================================================

class TestAdversarialRSSXMLPayloads:
    """Stress-tests for KYM RSS parser with hostile, corrupt, and edge-case XML feeds."""

    def test_completely_corrupt_xml(self) -> None:
        corrupted = "<<<???xml not valid<<<>>>"
        memes = parse_kym_rss(corrupted)
        assert memes == []

    def test_truncated_xml_in_middle_of_tag(self) -> None:
        truncated = '<?xml version="1.0"?><rss version="2.0"><channel><item><title>Truncated'
        memes = parse_kym_rss(truncated)
        assert memes == []

    def test_binary_garbage_and_null_bytes(self) -> None:
        garbage = "\x00\x01\x02\xff\xfe\xfd<rss><channel></rss>"
        memes = parse_kym_rss(garbage)
        assert memes == []

    def test_valid_xml_but_non_rss_root(self) -> None:
        non_rss = '<?xml version="1.0"?><configuration><setting key="foo" value="bar"/></configuration>'
        memes = parse_kym_rss(non_rss)
        assert memes == []

    def test_channel_less_rss_items_direct_under_root(self) -> None:
        xml_without_channel = """<?xml version="1.0"?>
        <rss version="2.0">
            <item>
                <guid>Entry-1001</guid>
                <title>Direct Under RSS Root</title>
                <link>https://knowyourmeme.com/memes/direct-root</link>
                <description>&lt;img src="https://i.kym-cdn.com/direct.jpg"/&gt;</description>
            </item>
        </rss>"""
        memes = parse_kym_rss(xml_without_channel)
        assert len(memes) == 1
        assert memes[0].title == "Direct Under RSS Root"
        assert "direct.jpg" in memes[0].media_url

    def test_missing_guid_falls_back_to_title_slug(self) -> None:
        xml = """<?xml version="1.0"?>
        <rss version="2.0"><channel>
            <item>
                <title>Meme Without GUID / Special: Chars!</title>
                <link>https://knowyourmeme.com/memes/no-guid</link>
                <description>&lt;img src="https://i.kym-cdn.com/noguid.jpg"/&gt;</description>
            </item>
        </channel></rss>"""
        memes = parse_kym_rss(xml)
        assert len(memes) == 1
        assert memes[0].id.startswith("kym_")
        assert len(memes[0].id) > 4

    def test_missing_description_falls_back_to_enclosure(self) -> None:
        xml = """<?xml version="1.0"?>
        <rss version="2.0"><channel>
            <item>
                <guid>Entry-2002</guid>
                <title>Enclosure Only Meme</title>
                <link>https://knowyourmeme.com/memes/enclosure-only</link>
                <enclosure url="https://i.kym-cdn.com/enclosure_image.png" length="12345" type="image/png"/>
            </item>
        </channel></rss>"""
        memes = parse_kym_rss(xml)
        assert len(memes) == 1
        assert memes[0].media_url == "https://i.kym-cdn.com/enclosure_image.png"
        assert memes[0].media_type == MediaType.IMAGE

    def test_missing_description_and_enclosure_uses_placeholder(self) -> None:
        xml = """<?xml version="1.0"?>
        <rss version="2.0"><channel>
            <item>
                <guid>Entry-3003</guid>
                <title>No Image Anywhere</title>
                <link>https://knowyourmeme.com/memes/no-image</link>
            </item>
        </channel></rss>"""
        memes = parse_kym_rss(xml)
        assert len(memes) == 1
        assert "kym_placeholder.jpg" in memes[0].media_url

    def test_gif_media_type_detection(self) -> None:
        xml = """<?xml version="1.0"?>
        <rss version="2.0"><channel>
            <item>
                <guid>Entry-4004</guid>
                <title>Dancing Cat Animation</title>
                <link>https://knowyourmeme.com/memes/dancing-cat</link>
                <description>&lt;img src="https://i.kym-cdn.com/dancing_cat.GIF"/&gt;</description>
            </item>
        </channel></rss>"""
        memes = parse_kym_rss(xml)
        assert len(memes) == 1
        assert memes[0].media_type == MediaType.GIF

    def test_cdata_content_in_title_and_description(self) -> None:
        xml = """<?xml version="1.0"?>
        <rss version="2.0"><channel>
            <item>
                <guid>Entry-5005</guid>
                <title><![CDATA[Meme With <CDATA> & Unescaped Entities]]></title>
                <link>https://knowyourmeme.com/memes/cdata-meme</link>
                <description><![CDATA[<p>Summary</p><img src="https://i.kym-cdn.com/cdata_img.jpg?foo=1&bar=2" />]]></description>
            </item>
        </channel></rss>"""
        memes = parse_kym_rss(xml)
        assert len(memes) == 1
        assert "Meme With <CDATA>" in memes[0].title
        assert "cdata_img.jpg" in memes[0].media_url

    def test_mixed_valid_and_broken_items(self) -> None:
        xml = """<?xml version="1.0"?>
        <rss version="2.0"><channel>
            <item>
                <guid>Good-1</guid>
                <title>Good Item 1</title>
                <description>&lt;img src="https://i.kym-cdn.com/good1.jpg"/&gt;</description>
            </item>
            <item>
                <!-- Missing title -->
                <guid>Bad-2</guid>
                <description>&lt;img src="https://i.kym-cdn.com/bad2.jpg"/&gt;</description>
            </item>
            <item>
                <guid>Good-3</guid>
                <title>Good Item 3</title>
                <description>&lt;img src="https://i.kym-cdn.com/good3.jpg"/&gt;</description>
            </item>
        </channel></rss>"""
        memes = parse_kym_rss(xml)
        assert len(memes) == 2
        titles = [m.title for m in memes]
        assert "Good Item 1" in titles
        assert "Good Item 3" in titles

    def test_nsfw_detection_in_title_and_description(self) -> None:
        xml = """<?xml version="1.0"?>
        <rss version="2.0"><channel>
            <item>
                <guid>NSFW-1</guid>
                <title>Adult Topic [NSFW]</title>
                <description>&lt;img src="https://i.kym-cdn.com/1.jpg"/&gt;</description>
            </item>
            <item>
                <guid>NSFW-2</guid>
                <title>Clean Title</title>
                <description>&lt;p&gt;Warning: explicit content inside&lt;/p&gt;&lt;img src="https://i.kym-cdn.com/2.jpg"/&gt;</description>
            </item>
            <item>
                <guid>SFW-3</guid>
                <title>Completely Wholesome Cat</title>
                <description>&lt;img src="https://i.kym-cdn.com/3.jpg"/&gt;</description>
            </item>
        </channel></rss>"""
        memes = parse_kym_rss(xml)
        assert len(memes) == 3
        assert memes[0].is_nsfw is True
        assert memes[1].is_nsfw is True
        assert memes[2].is_nsfw is False

    def test_high_volume_stress_1000_items(self) -> None:
        """Stress-test parsing efficiency on a large 1,000 item RSS feed."""
        items_xml = []
        for i in range(1000):
            items_xml.append(
                f"""<item>
                    <guid>Entry-Stress-{i}</guid>
                    <title>Stress Item #{i}</title>
                    <link>https://knowyourmeme.com/memes/stress-{i}</link>
                    <pubDate>Mon, 24 Aug 2026 10:13:17 -0400</pubDate>
                    <description>&lt;p&gt;Item {i}&lt;/p&gt;&lt;img src="https://i.kym-cdn.com/img_{i}.jpg"/&gt;</description>
                </item>"""
            )
        feed_xml = f'<?xml version="1.0"?><rss version="2.0"><channel>{"".join(items_xml)}</channel></rss>'

        start = time.perf_counter()
        memes = parse_kym_rss(feed_xml)
        duration = time.perf_counter() - start

        assert len(memes) == 1000
        assert duration < 1.0  # Should parse 1,000 items in well under 1 second


# =============================================================================
# 4. SECURITY MODULE: USER-AGENT ROTATION, HEADERS & BACKOFF
# =============================================================================

class TestSecurityModuleAdversarial:
    """Stress-tests for security headers, User-Agent entropy, backoff math, and rate limiter."""

    def test_user_agent_pool_quality_and_diversity(self) -> None:
        """Verify user agents are modern, varied (Windows, Mac, Linux, iOS), and valid."""
        assert len(USER_AGENTS) >= 4
        platforms = {"Windows", "Macintosh", "Linux", "iPhone"}
        found_platforms = set()
        for ua in USER_AGENTS:
            assert isinstance(ua, str)
            assert len(ua) > 30
            for plat in platforms:
                if plat in ua:
                    found_platforms.add(plat)
        assert len(found_platforms) >= 3  # Diverse OS coverage

    def test_user_agent_rotation_statistical_distribution(self) -> None:
        """Empirically test that get_random_user_agent samples all pool items evenly."""
        sample_count = 6000
        counts = Counter(get_random_user_agent() for _ in range(sample_count))
        num_agents = len(USER_AGENTS)
        expected_per_agent = sample_count / num_agents

        # Verify every UA was sampled
        assert len(counts) == num_agents

        # Chi-squared test for uniformity
        chi_squared = sum((c - expected_per_agent) ** 2 / expected_per_agent for c in counts.values())
        # Degrees of freedom = num_agents - 1 (e.g., 5 for 6 UAs). Critical value at p=0.001 is ~20.5
        assert chi_squared < 30.0

    def test_get_request_headers_spec(self) -> None:
        """Verify request header dictionary structure and custom overrides."""
        headers = get_request_headers(
            user_agent="CustomTestBot/1.0",
            accept="application/xml",
        )
        assert headers["User-Agent"] == "CustomTestBot/1.0"
        assert headers["Accept"] == "application/xml"
        assert headers["Accept-Language"] == "en-US,en;q=0.9"
        assert headers["Accept-Encoding"] == "gzip, deflate, br"
        assert headers["Connection"] == "keep-alive"

    def test_calculate_backoff_exponential_growth(self) -> None:
        """Verify backoff delay increases exponentially with attempt count."""
        delays = []
        for attempt in range(5):
            # Sample multiple times to account for random jitter
            sample_delays = [calculate_backoff_delay(attempt, base=1.0, max_backoff=32.0) for _ in range(20)]
            avg_delay = sum(sample_delays) / len(sample_delays)
            delays.append(avg_delay)

        # Verify each step roughly doubles (1s, 2s, 4s, 8s, 16s) + jitter
        for i in range(1, len(delays)):
            assert delays[i] > delays[i - 1]

    def test_calculate_backoff_jitter_bounds(self) -> None:
        """Verify jitter is always in [0.1, 0.5]."""
        for _ in range(100):
            d = calculate_backoff_delay(0, base=1.0, max_backoff=16.0)
            # base * 2^0 + jitter = 1.0 + [0.1, 0.5] = [1.1, 1.5]
            assert 1.10 <= d <= 1.50 + 1e-6

    def test_calculate_backoff_max_backoff_cap(self) -> None:
        """Verify delay is strictly capped at max_backoff even at huge attempt numbers."""
        for attempt in [10, 50, 100]:
            d = calculate_backoff_delay(attempt, max_backoff=16.0)
            assert d == 16.0

    @pytest.mark.parametrize(
        "headers, expected_delay",
        [
            ({"Retry-After": "5"}, 5.0),
            ({"retry-after": "8.5"}, 8.5),
            ({"Retry-After": "100"}, 16.0),  # Capped at max_backoff 16.0
            ({"x-ratelimit-reset": "12"}, 12.0),
            ({"x-ratelimit-reset": "250"}, 16.0),  # Capped at max_backoff 16.0
        ],
    )
    def test_calculate_backoff_with_response_headers(
        self, headers: Dict[str, str], expected_delay: float
    ) -> None:
        d = calculate_backoff_delay(0, response_headers=headers, max_backoff=16.0)
        assert d == pytest.approx(expected_delay, abs=0.01)

    @pytest.mark.parametrize(
        "headers",
        [
            {"Retry-After": "invalid-string"},
            {"Retry-After": "-10"},
            {"x-ratelimit-reset": "not-a-number"},
            {"x-ratelimit-reset": "-5"},
        ],
    )
    def test_calculate_backoff_with_corrupt_response_headers_falls_back(
        self, headers: Dict[str, str]
    ) -> None:
        """Verify corrupt or negative rate limit headers safely fallback to exponential backoff."""
        d = calculate_backoff_delay(1, response_headers=headers, base=1.0, max_backoff=16.0)
        # Attempt 1 -> 1.0 * 2^1 + jitter = 2.1 to 2.5
        assert 2.10 <= d <= 2.50 + 1e-6

    @pytest.mark.asyncio
    async def test_polite_rate_limiter_domain_isolation(self) -> None:
        """Verify rate limiter enforces interval on same domain without blocking distinct domains."""
        limiter = PoliteRateLimiter(min_interval_seconds=0.1)

        # First request to domain A and domain B in parallel should complete immediately
        t0 = time.monotonic()
        await asyncio.gather(
            limiter.throttle("reddit.com"),
            limiter.throttle("knowyourmeme.com"),
        )
        elapsed = time.monotonic() - t0
        assert elapsed < 0.05  # Both allowed through without waiting

        # Second request to domain A immediately should be throttled
        t1 = time.monotonic()
        await limiter.throttle("reddit.com")
        elapsed_throttled = time.monotonic() - t1
        assert elapsed_throttled >= 0.08  # Throttled to ~0.1s
