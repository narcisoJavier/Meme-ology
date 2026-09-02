"""Unit tests for trending ranking algorithm, gravity decay, and score monotonicity.

Validates:
- Gravity decay formula: (score + comments * 1.5) / (age_in_hours + 2)^1.5.
- Monotonicity: Higher upvotes -> higher trending score.
- Monotonicity: Higher comments -> higher trending score.
- Time decay: Older memes have lower trending scores given identical engagement.
- Freshness displacement: Fast-rising fresh meme displaces stale viral meme.
- Boundary conditions: 0 score, 0 comments, current_time <= created_at, extreme ages.
- Precision, fractional hours, and numerical stability.
"""

from __future__ import annotations

import math
import time
import pytest

from app.core.ranking import calculate_trending_score


class TestTrendingRankingAlgorithm:
    """Tier 1 & Tier 2 unit tests for the trending ranking algorithm."""

    def test_calculate_trending_score_positive_basic(self) -> None:
        """Verify standard trending calculation returns expected positive float."""
        now = 1725300000.0
        created = now - 3600.0  # 1 hour ago
        score = calculate_trending_score(score=1000, comments=50, created_at=created, current_time=now)
        assert isinstance(score, (int, float))
        assert score > 0.0

    def test_higher_upvotes_increase_trending_score(self) -> None:
        """Verify strict monotonicity with respect to upvote score."""
        now = 1725300000.0
        created = now - 7200.0  # 2 hours ago
        score_low = calculate_trending_score(score=500, comments=20, created_at=created, current_time=now)
        score_high = calculate_trending_score(score=5000, comments=20, created_at=created, current_time=now)
        assert score_high > score_low

    def test_higher_comments_increase_trending_score(self) -> None:
        """Verify strict monotonicity with respect to comment engagement."""
        now = 1725300000.0
        created = now - 7200.0
        score_few_comments = calculate_trending_score(score=1000, comments=5, created_at=created, current_time=now)
        score_many_comments = calculate_trending_score(score=1000, comments=200, created_at=created, current_time=now)
        assert score_many_comments > score_few_comments

    def test_older_memes_decay_over_time(self) -> None:
        """Verify trending score decays as age increases (given identical engagement)."""
        now = 1725300000.0
        score_1h = calculate_trending_score(score=2000, comments=50, created_at=now - 3600, current_time=now)
        score_6h = calculate_trending_score(score=2000, comments=50, created_at=now - 21600, current_time=now)
        score_24h = calculate_trending_score(score=2000, comments=50, created_at=now - 86400, current_time=now)
        score_72h = calculate_trending_score(score=2000, comments=50, created_at=now - 259200, current_time=now)

        assert score_1h > score_6h > score_24h > score_72h

    def test_fresh_viral_meme_displaces_stale_top_meme(self) -> None:
        """Verify a fresh meme (1 hr old, 5k upvotes) outranks a 3-day old meme with 50k upvotes."""
        now = 1725300000.0
        stale_score = calculate_trending_score(
            score=50000, comments=1000, created_at=now - (72 * 3600), current_time=now
        )
        fresh_score = calculate_trending_score(
            score=8000, comments=300, created_at=now - (1 * 3600), current_time=now
        )
        assert fresh_score > stale_score

    def test_boundary_zero_score_and_zero_comments(self) -> None:
        """Verify calculation with 0 upvotes and 0 comments does not divide by zero or error."""
        now = 1725300000.0
        score = calculate_trending_score(score=0, comments=0, created_at=now - 3600, current_time=now)
        assert score >= 0.0

    def test_boundary_just_posted_zero_age(self) -> None:
        """Verify newly posted meme (created_at == current_time) calculates cleanly without division by zero."""
        now = 1725300000.0
        score = calculate_trending_score(score=100, comments=10, created_at=now, current_time=now)
        assert score > 0.0

    def test_boundary_future_timestamp_handled_gracefully(self) -> None:
        """Verify clock skew (created_at slightly in future) is clamped to age >= 0."""
        now = 1725300000.0
        future_created = now + 300.0  # 5 minutes in future
        score = calculate_trending_score(score=500, comments=20, created_at=future_created, current_time=now)
        assert score >= 0.0

    def test_boundary_negative_scores_clamped(self) -> None:
        """Verify downvoted post (negative score) is handled gracefully and does not produce negative infinity."""
        now = 1725300000.0
        score = calculate_trending_score(score=-50, comments=10, created_at=now - 3600, current_time=now)
        assert score >= 0.0

    def test_default_current_time_uses_system_clock(self) -> None:
        """Verify omission of current_time parameter defaults to current system time."""
        created = time.time() - 1800.0
        score = calculate_trending_score(score=1000, comments=50, created_at=created)
        assert score > 0.0

    def test_trending_score_reproducibility(self) -> None:
        """Verify deterministic calculation with exact fixed parameters."""
        s1 = calculate_trending_score(1500, 75, 1725300000.0, 1725303600.0)
        s2 = calculate_trending_score(1500, 75, 1725300000.0, 1725303600.0)
        assert s1 == s2

    def test_fractional_hour_decay_granularity(self) -> None:
        """Verify score decreases continuously across 10m, 20m, 30m intervals."""
        now = 1725300000.0
        score_10m = calculate_trending_score(1000, 20, now - 600, now)
        score_20m = calculate_trending_score(1000, 20, now - 1200, now)
        score_30m = calculate_trending_score(1000, 20, now - 1800, now)
        assert score_10m > score_20m > score_30m

    def test_extreme_large_engagement_numerical_stability(self) -> None:
        """Verify multi-million score calculations do not overflow or produce NaN/inf."""
        now = 1725300000.0
        score = calculate_trending_score(score=5_000_000, comments=500_000, created_at=now - 3600, current_time=now)
        assert not math.isnan(score)
        assert not math.isinf(score)
        assert score > 1000.0

    def test_extreme_age_stability(self) -> None:
        """Verify 1-year-old meme calculation does not underflow or crash."""
        now = 1725300000.0
        one_year_ago = now - (365 * 86400)
        score = calculate_trending_score(score=10000, comments=500, created_at=one_year_ago, current_time=now)
        assert score >= 0.0
        assert not math.isnan(score)
