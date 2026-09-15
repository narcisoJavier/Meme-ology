"""Virality and Trend Lifecycle calculation engine."""

from __future__ import annotations

import time
from enum import Enum
from typing import Dict, List, Optional, Tuple


class LifecycleStage(str, Enum):
    """Discrete lifecycle stage of a meme."""
    EMERGING = "emerging"
    VIRAL = "viral"
    PEAK = "peak"
    COOLING = "cooling"


# Adaptive viral velocity thresholds (score or views per hour)
DEFAULT_VIRAL_THRESHOLDS: Dict[str, float] = {
    "youtube": 2500.0,
    "reddit": 1000.0,
    "knowyourmeme": 500.0,
    "mastodon": 250.0,
    "bluesky": 250.0,
}


def calculate_velocity_and_acceleration(
    snapshots: List[Tuple[float, int]],
    current_time: Optional[float] = None,
    current_score: Optional[int] = None,
) -> Tuple[float, float]:
    """Calculate velocity (growth/hr) and acceleration from time-series score snapshots.
    
    snapshots: list of (timestamp_seconds, score) tuples in ascending chronological order.
    Returns: (velocity_per_hour, acceleration)
    """
    now = current_time or time.time()
    points = list(snapshots)
    if current_score is not None:
        points.append((now, current_score))

    if len(points) < 2:
        # Fallback: if only 1 point, estimate velocity from created_at or return 0.0
        return 0.0, 0.0

    # Last segment velocity
    t_last, s_last = points[-1]
    t_prev, s_prev = points[-2]
    dt_hours = max(0.001, (t_last - t_prev) / 3600.0)
    current_velocity = max(0.0, (s_last - s_prev) / dt_hours)

    if len(points) < 3:
        return round(current_velocity, 2), 0.0

    # Prior segment velocity to calculate acceleration
    t_prior, s_prior = points[-3]
    dt_prior_hours = max(0.001, (t_prev - t_prior) / 3600.0)
    prior_velocity = max(0.0, (s_prev - s_prior) / dt_prior_hours)

    acceleration = (current_velocity - prior_velocity) / dt_hours
    return round(current_velocity, 2), round(acceleration, 2)


def classify_lifecycle_stage(
    velocity: float,
    acceleration: float,
    created_at: float,
    platform: str,
    total_score: int,
    custom_thresholds: Optional[Dict[str, float]] = None,
) -> LifecycleStage:
    """Classify a meme into its lifecycle stage using adaptive velocity & acceleration."""
    thresholds = custom_thresholds or DEFAULT_VIRAL_THRESHOLDS
    plat_key = str(platform).lower().strip()
    viral_threshold = thresholds.get(plat_key, 1000.0)
    cooling_threshold = viral_threshold * 0.25

    now = time.time()
    age_hours = max(0.0, (now - created_at) / 3600.0)

    # VIRAL: High velocity exceeding platform threshold with sustained forward momentum
    if velocity >= viral_threshold:
        return LifecycleStage.VIRAL

    # PEAK: High cumulative score, but acceleration is negative and velocity is tapering off
    if total_score >= viral_threshold and acceleration < -10.0 and velocity < (viral_threshold * 0.7):
        return LifecycleStage.PEAK

    # COOLING: Older post with velocity dropping below cooling cutoff
    if age_hours > 24.0 and velocity <= cooling_threshold:
        return LifecycleStage.COOLING

    # EMERGING: Fresh post (< 24 hours) with positive velocity or acceleration
    if age_hours <= 24.0 and (velocity > 0 or acceleration >= 0):
        return LifecycleStage.EMERGING

    # Default fallback based on velocity
    if velocity > cooling_threshold:
        return LifecycleStage.EMERGING
    return LifecycleStage.COOLING
