"""Trending score calculation and engagement ranking algorithm."""

import time
from typing import Optional


def calculate_trending_score(
    score: int,
    comments: int = 0,
    created_at: float = 0.0,
    current_time: Optional[float] = None,
    num_comments: Optional[int] = None,
) -> float:
    """Calculate trending score with engagement weighting and gravity time decay.

    Formula: (max(0, score) + max(0, comments) * 1.5) / (age_in_hours + 2.0) ^ 1.5
    """
    now = current_time if current_time is not None else time.time()
    age_seconds = max(0.0, now - created_at)
    age_hours = age_seconds / 3600.0

    effective_score = max(0, score)
    comment_count = num_comments if num_comments is not None else comments
    effective_comments = max(0, comment_count)

    engagement = effective_score + (effective_comments * 1.5)
    gravity_decay = (age_hours + 2.0) ** 1.5
    return round(float(engagement / gravity_decay), 4)
