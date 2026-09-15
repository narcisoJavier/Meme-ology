"""Trending score calculation and engagement ranking algorithm."""

from __future__ import annotations

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


def calculate_global_trending_score(
    score: int,
    comments: int = 0,
    created_at: float = 0.0,
    cross_platform_count: int = 1,
    velocity: float = 0.0,
    acceleration: float = 0.0,
    current_time: Optional[float] = None,
) -> float:
    """Calculate global trending score with cross-platform multiplier and velocity boost."""
    base_score = calculate_trending_score(score, comments, created_at, current_time)

    # Cross-platform spread multiplier (1.5x for 2 platforms, 2.0x for 3+)
    platform_multiplier = 1.0 + (0.5 * max(0, cross_platform_count - 1))

    # Velocity acceleration multiplier
    acceleration_multiplier = 1.0
    if acceleration > 0.0:
        acceleration_multiplier = min(2.0, 1.0 + (acceleration / 500.0))

    return round(base_score * platform_multiplier * acceleration_multiplier, 4)
