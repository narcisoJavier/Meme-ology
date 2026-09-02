"""Abstract base class for meme source fetchers."""

import abc
import hashlib
import re
import time
from typing import List, Optional
from app.models.meme import NormalizedMeme, SourcePlatform
from app.models.source import SourceStatus


def compute_content_hash(media_url: str, title: str) -> str:
    """Compute deterministic SHA-256 hash from canonical media URL and normalized title."""
    clean_url = re.sub(r"\?.*$", "", (media_url or "").lower().strip())
    clean_title = (title or "").lower().strip()
    payload = f"{clean_url}|{clean_title}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def calculate_trending_score(
    score: int,
    num_comments: int,
    created_at: float,
    current_time: Optional[float] = None,
) -> float:
    """Calculate trending score with engagement weights and gravity decay over time.

    Formula: (score + num_comments * 1.5) / (age_in_hours + 2.0) ^ 1.5
    """
    now = current_time if current_time is not None else time.time()
    age_seconds = max(0.0, now - created_at)
    age_hours = age_seconds / 3600.0
    engagement = max(0, score) + (max(0, num_comments) * 1.5)
    gravity_decay = (age_hours + 2.0) ** 1.5
    return round(float(engagement / gravity_decay), 4)


class BaseSourceFetcher(abc.ABC):
    """Abstract interface for all multi-source meme fetchers."""

    def __init__(
        self,
        name: str,
        platform: SourcePlatform,
        community: str,
    ) -> None:
        self.name = name
        self.platform = platform
        self.community = community
        self.status = SourceStatus(
            name=name,
            platform=platform,
            community=community,
            status="ok",
            item_count=0,
        )

    @abc.abstractmethod
    async def fetch_memes(self) -> List[NormalizedMeme]:
        """Fetch and normalize memes from upstream source."""
        raise NotImplementedError

    @abc.abstractmethod
    def load_offline_fixtures(self) -> List[NormalizedMeme]:
        """Load and normalize memes from local static fixtures."""
        raise NotImplementedError

    def update_success(self, count: int, latency_ms: float) -> None:
        """Update health metrics on successful fetch."""
        self.status.status = "ok"
        self.status.item_count = count
        self.status.last_synced_at = time.time()
        self.status.last_error = None
        self.status.latency_ms = round(latency_ms, 2)

    def update_failure(self, error: Exception) -> None:
        """Update health metrics on failed fetch."""
        self.status.status = "degraded"
        self.status.last_error = str(error)
