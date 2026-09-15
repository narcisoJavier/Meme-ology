"""Content deduplication, URL canonicalization, and identity resolution utilities."""

from __future__ import annotations

import hashlib
import re
from typing import Optional, Set
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Tracking & image manipulation query parameter patterns to strip
STRIP_QUERY_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "s",
    "width",
    "height",
    "crop",
    "auto",
    "format",
    "context",
    "preview",
}


def normalize_url(raw_url: Optional[str]) -> str:
    """Normalize and canonicalize media URL for deterministic deduplication."""
    if not raw_url:
        return ""

    url_str = raw_url.strip()
    if not url_str:
        return ""

    lower_prefix = url_str.lower()
    if lower_prefix.startswith("//"):
        url_str = "https:" + url_str
    elif not lower_prefix.startswith("http://") and not lower_prefix.startswith("https://"):
        url_str = "https://" + url_str

    try:
        parsed = urlparse(url_str)
    except Exception:
        return url_str

    # Normalize scheme to https and domain to lowercase
    scheme = "https"
    netloc = parsed.netloc.lower()
    path = parsed.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    # Clean query parameters
    query_params = parse_qsl(parsed.query, keep_blank_values=False)
    filtered_params = [
        (k, v)
        for k, v in query_params
        if k.lower() not in STRIP_QUERY_PARAMS and not k.lower().startswith("utm_")
    ]

    # Reconstruct clean URL (drop fragment)
    new_query = urlencode(filtered_params) if filtered_params else ""
    canonical = urlunparse((scheme, netloc, path, "", new_query, ""))
    return canonical


def compute_content_hash(media_url: str, title: str) -> str:
    """Compute deterministic SHA-256 hash from canonical media URL and normalized title."""
    clean_url = normalize_url(media_url).lower().strip()
    clean_title = (title or "").lower().strip()
    payload = f"{clean_url}|{clean_title}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def normalize_title(title: Optional[str]) -> str:
    """Normalize meme title by stripping hashtag spam, links, and redundant whitespace."""
    if not title:
        return ""
    # Strip URLs
    text = re.sub(r"https?://\S+", "", title)
    # Strip hashtags (#meme, #shitpost, #humour, etc.) - must start with a letter/underscore
    text = re.sub(r"#[a-zA-Z_]\w*", "", text)
    # Extract alphanumeric tokens
    tokens = re.findall(r"\w+", text.lower())
    return " ".join(tokens).strip()


def normalize_author_handle(author: Optional[str]) -> str:
    """Canonicalize author handles across platforms, resolving Bridgy Fed mirrors."""
    if not author:
        return ""
    clean = author.strip().lower()
    if clean.startswith("@"):
        clean = clean[1:]

    # Bridgy Fed ActivityPub -> Bluesky: {user}.{instance}.ap.brid.gy
    if clean.endswith(".ap.brid.gy"):
        prefix = clean.removesuffix(".ap.brid.gy")
        parts = prefix.split(".", 1)
        if len(parts) == 2:
            return f"{parts[0]}@{parts[1]}"
        return prefix

    # Bridgy Fed Bluesky -> Mastodon: {user}@bsky.brid.gy or {user}.bsky.brid.gy
    if clean.endswith("@bsky.brid.gy"):
        return clean.removesuffix("@bsky.brid.gy")
    if clean.endswith(".bsky.brid.gy"):
        return clean.removesuffix(".bsky.brid.gy")

    return clean


def compute_semantic_title_hash(title: str) -> str:
    """Compute deterministic hash of the normalized title."""
    normalized = normalize_title(title)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def are_memes_duplicate(
    media_url_1: str,
    title_1: str,
    author_1: str,
    media_url_2: str,
    title_2: str,
    author_2: str,
) -> bool:
    """Determine if two memes represent the same content based on multiple heuristics."""
    # Exact media URL canonical match
    clean_u1 = normalize_url(media_url_1).lower()
    clean_u2 = normalize_url(media_url_2).lower()
    if clean_u1 and clean_u2 and clean_u1 == clean_u2:
        return True

    # Normalized title match
    norm_t1 = normalize_title(title_1)
    norm_t2 = normalize_title(title_2)

    if norm_t1 and norm_t2 and norm_t1 == norm_t2:
        # If title is distinctive (len >= 12 chars), it is almost certainly the same meme
        if len(norm_t1) >= 12:
            return True

        # For shorter titles, check if author matches (including bridged mirrors)
        norm_a1 = normalize_author_handle(author_1)
        norm_a2 = normalize_author_handle(author_2)
        if norm_a1 and norm_a2 and norm_a1 == norm_a2:
            return True

    return False
