"""Content deduplication and URL canonicalization utilities."""

import hashlib
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from typing import Optional


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
