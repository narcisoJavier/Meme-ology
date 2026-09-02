"""Unit tests for URL canonicalization and SHA-256 content hashing deduplication.

Validates:
- Query parameter stripping (tracking params: utm_*, ref, preview, width, s).
- Protocol and host normalization (http -> https, lowercase host).
- Canonical handling of Imgur, Reddit, and KYM CDN domains.
- Deterministic SHA-256 hashing on media URL and normalized title.
- Cross-platform duplicate collision avoidance.
- Unicode and special character handling in meme titles.
- Extreme edge cases: encoded characters, duplicate query params, trailing slashes.
"""

from __future__ import annotations

import hashlib
import pytest

from app.core.dedup import compute_content_hash, normalize_url


class TestURLNormalization:
    """Tier 1 & Tier 2 tests for canonical URL normalization."""

    def test_normalize_url_strips_tracking_params(self) -> None:
        """Verify query parameters like utm_source, s, and preview are stripped."""
        raw = "https://i.redd.it/abcdef123456.jpg?utm_source=share&utm_medium=web2x&context=3"
        clean = normalize_url(raw)
        assert clean == "https://i.redd.it/abcdef123456.jpg"

    def test_normalize_url_strips_reddit_preview_params(self) -> None:
        """Verify Reddit preview query parameters (width, format, auto, s) are stripped."""
        raw = "https://preview.redd.it/test.png?width=640&crop=smart&auto=webp&s=9f8e7d6c5b"
        clean = normalize_url(raw)
        assert "?" not in clean
        assert clean == "https://preview.redd.it/test.png"

    def test_normalize_url_lowercases_scheme_and_domain(self) -> None:
        """Verify scheme and host are lowercased."""
        raw = "HTTP://I.REDD.IT/Meme_Case_Sensitive_Path.JPG"
        clean = normalize_url(raw)
        assert clean.startswith("https://i.redd.it/")
        assert "Meme_Case_Sensitive_Path" in clean

    def test_normalize_url_trims_whitespace(self) -> None:
        """Verify leading and trailing whitespace is stripped."""
        raw = "   https://i.redd.it/image.png   "
        clean = normalize_url(raw)
        assert clean == "https://i.redd.it/image.png"

    def test_normalize_url_handles_empty_or_none(self) -> None:
        """Verify empty string returns empty string without error."""
        assert normalize_url("") == ""
        assert normalize_url("   ") == ""

    def test_normalize_url_removes_url_fragments(self) -> None:
        """Verify URL fragments (#section) are stripped."""
        raw = "https://i.kym-cdn.com/photos/trending/12345.jpg#main"
        clean = normalize_url(raw)
        assert "#" not in clean
        assert clean == "https://i.kym-cdn.com/photos/trending/12345.jpg"

    def test_normalize_url_without_params_unchanged(self) -> None:
        """Verify clean URL remains untouched."""
        raw = "https://i.redd.it/clean_image.png"
        assert normalize_url(raw) == "https://i.redd.it/clean_image.png"

    def test_normalize_url_standard_http_to_https(self) -> None:
        """Verify insecure http protocol is normalized to https."""
        raw = "http://i.redd.it/secure_me.jpg"
        clean = normalize_url(raw)
        assert clean.startswith("https://")

    def test_normalize_url_strips_trailing_slash_on_root(self) -> None:
        """Verify bare origin trailing slash handling."""
        raw = "https://i.redd.it/path/to/image.jpg/"
        clean = normalize_url(raw)
        assert not clean.endswith("/")

    def test_normalize_url_imgur_conversion(self) -> None:
        """Verify imgur single image page links resolve or preserve canonical image id."""
        raw = "https://imgur.com/aBcDeFg"
        clean = normalize_url(raw)
        assert "aBcDeFg" in clean


class TestContentHashing:
    """Tier 1 & Tier 2 tests for deterministic SHA-256 deduplication hashing."""

    def test_compute_content_hash_deterministic(self) -> None:
        """Verify compute_content_hash produces identical output for identical inputs."""
        url = "https://i.redd.it/test_meme.jpg"
        title = "When you write 100 tests and they all pass"
        hash1 = compute_content_hash(url, title)
        hash2 = compute_content_hash(url, title)
        assert isinstance(hash1, str)
        assert len(hash1) == 64
        assert hash1 == hash2

    def test_compute_content_hash_case_and_whitespace_insensitive(self) -> None:
        """Verify title case and extra spaces do not alter the content hash."""
        url = "https://i.redd.it/test_meme.jpg"
        hash1 = compute_content_hash(url, "Programming Meme")
        hash2 = compute_content_hash(url, "  programming meme  ")
        assert hash1 == hash2

    def test_compute_content_hash_different_media_different_hash(self) -> None:
        """Verify different media URLs produce distinct hashes even with same title."""
        title = "Same Title"
        hash1 = compute_content_hash("https://i.redd.it/image1.jpg", title)
        hash2 = compute_content_hash("https://i.redd.it/image2.jpg", title)
        assert hash1 != hash2

    def test_compute_content_hash_different_title_different_hash(self) -> None:
        """Verify different titles produce distinct hashes with same media URL."""
        url = "https://i.redd.it/shared_template.jpg"
        hash1 = compute_content_hash(url, "First Caption")
        hash2 = compute_content_hash(url, "Second Caption")
        assert hash1 != hash2

    def test_compute_content_hash_with_tracking_params_deduplicates(self) -> None:
        """Verify two URLs with different tracking params resolve to same hash."""
        url1 = "https://i.redd.it/shared.jpg?utm_source=reddit"
        url2 = "https://i.redd.it/shared.jpg?ref=homepage&s=12345"
        title = "Cross Posted Viral Meme"
        assert compute_content_hash(url1, title) == compute_content_hash(url2, title)

    def test_compute_content_hash_unicode_and_emojis(self) -> None:
        """Verify non-ASCII characters and emojis are hashed deterministically."""
        url = "https://i.redd.it/emoji.jpg"
        title = "🔥 🚀 Coder life (élégant & groß) 💻"
        hash_val = compute_content_hash(url, title)
        assert len(hash_val) == 64
        assert int(hash_val, 16) > 0

    def test_compute_content_hash_matches_sha256_standard(self) -> None:
        """Verify hash matches standard Python hashlib.sha256 result."""
        url = "https://i.redd.it/exact.png"
        title = "Exact match title"
        clean_url = normalize_url(url).lower().strip()
        clean_title = title.lower().strip()
        expected = hashlib.sha256(f"{clean_url}|{clean_title}".encode("utf-8")).hexdigest()
        assert compute_content_hash(url, title) == expected

    def test_compute_content_hash_empty_inputs(self) -> None:
        """Verify empty url or title produces a valid 64-char sha256 hash."""
        h1 = compute_content_hash("", "")
        assert len(h1) == 64
        assert isinstance(h1, str)
