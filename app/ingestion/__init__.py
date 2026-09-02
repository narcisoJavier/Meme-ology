"""Meme ingestion package exporting base and platform-specific fetchers."""

from app.ingestion.base import (
    BaseSourceFetcher,
    compute_content_hash,
    calculate_trending_score,
)
from app.ingestion.reddit import RedditFetcher, RedditMemeFetcher
from app.ingestion.knowyourmeme import KnowYourMemeFetcher

__all__ = [
    "BaseSourceFetcher",
    "compute_content_hash",
    "calculate_trending_score",
    "RedditFetcher",
    "RedditMemeFetcher",
    "KnowYourMemeFetcher",
]
