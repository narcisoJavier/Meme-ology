"""In-memory fast cache with atomic indices for sub-millisecond query latencies."""

from __future__ import annotations

import asyncio
import logging
import random
import threading
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from app.config import get_settings
from app.core.dedup import compute_content_hash
from app.core.lifecycle import (
    calculate_velocity_and_acceleration,
    classify_lifecycle_stage,
    LifecycleStage,
)
from app.core.ranking import calculate_trending_score
from app.core.webhooks import dispatch_viral_webhook
from app.models.meme import MediaType, Meme, NormalizedMeme, SourcePlatform
from app.models.source import HealthResponse, SourceStatus

logger = logging.getLogger(__name__)


def _extract_source_tokens(platform_val: str, comm_val: str) -> Set[str]:
    """Pre-extract all matching query tokens for a given platform and community."""
    tokens: Set[str] = set()
    plat = platform_val.lower().strip()
    comm = comm_val.lower().strip()
    clean_comm = comm[2:].strip() if comm.startswith("r/") else (comm[1:].strip() if comm.startswith("#") else comm)

    # Direct platform tokens
    tokens.add(plat)
    if plat == "reddit":
        tokens.add("reddit")
    elif plat in ("knowyourmeme", "kym"):
        tokens.add("knowyourmeme")
        tokens.add("kym")
        tokens.add("know your meme")
    elif plat in ("bluesky", "bsky"):
        tokens.add("bluesky")
        tokens.add("bsky")
    elif plat in ("mastodon", "masto", "fediverse"):
        tokens.add("mastodon")
        tokens.add("masto")
        tokens.add("fediverse")
    elif plat in ("youtube", "yt"):
        tokens.add("youtube")
        tokens.add("yt")

    # Community tokens
    if comm:
        tokens.add(comm)
    if clean_comm:
        tokens.add(clean_comm)
        if plat == "reddit":
            tokens.add(f"r/{clean_comm}")
        elif plat == "mastodon":
            tokens.add(f"#{clean_comm}")

    # Composite tokens
    plats = [plat]
    if plat in ("knowyourmeme", "kym"):
        plats.extend(["knowyourmeme", "kym"])
    elif plat == "reddit":
        plats.append("reddit")
    elif plat in ("bluesky", "bsky"):
        plats.extend(["bluesky", "bsky"])
    elif plat in ("mastodon", "masto", "fediverse"):
        plats.extend(["mastodon", "masto", "fediverse"])
    elif plat in ("youtube", "yt"):
        plats.extend(["youtube", "yt"])

    comms = [c for c in (comm, clean_comm, f"r/{clean_comm}" if clean_comm and plat == "reddit" else None, f"#{clean_comm}" if clean_comm and plat == "mastodon" else None) if c]
    for p in set(plats):
        for c in set(comms):
            tokens.add(f"{p}:{c}")
            tokens.add(f"{p}/{c}")

    return tokens


class MemoryStore:
    """High-performance in-memory cache store with pre-sorted latest and trending indices."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._by_id: Dict[str, NormalizedMeme] = {}
        self._by_content_hash: Dict[str, str] = {}
        self._by_author_title: Dict[str, str] = {}
        self._source_tokens_by_id: Dict[str, Set[str]] = {}
        self._snapshots: Dict[str, List[Tuple[float, int]]] = {}

        # Primary pre-sorted lists
        self._latest_index: List[NormalizedMeme] = []
        self._latest_index_sfw: List[NormalizedMeme] = []
        self._trending_index: List[NormalizedMeme] = []
        self._trending_index_sfw: List[NormalizedMeme] = []

        # Secondary source pre-indexed lists (all presorted)
        self._by_source_latest: Dict[str, List[NormalizedMeme]] = {}
        self._by_source_latest_sfw: Dict[str, List[NormalizedMeme]] = {}
        self._by_source_trending: Dict[str, List[NormalizedMeme]] = {}
        self._by_source_trending_sfw: Dict[str, List[NormalizedMeme]] = {}

        self._source_status: Dict[str, SourceStatus] = {}
        self._start_time = time.time()
        self._init_default_source_statuses()

    def _init_default_source_statuses(self) -> None:
        """Initialize default status tracking for configured sources."""
        settings = get_settings()
        for sub in settings.REDDIT_SUBREDDITS:
            clean_sub = sub.lstrip("r/").strip()
            name = f"reddit:r/{clean_sub}"
            self._source_status[name] = SourceStatus(
                id=f"reddit_{clean_sub}",
                name=name,
                platform=SourcePlatform.REDDIT,
                community=f"r/{clean_sub}",
                category="community_forum",
                status="ok",
                item_count=0,
            )

        for cat in ["confirmed", "trending", "news"]:
            name = f"knowyourmeme:{cat}"
            self._source_status[name] = SourceStatus(
                id=f"kym_{cat}",
                name=name,
                platform=SourcePlatform.KNOWYOURMEME,
                community=cat,
                category="encyclopedia",
                status="ok",
                item_count=0,
            )

        for feed in getattr(settings, "BLUESKY_FEEDS", ["meme"]):
            clean_feed = feed.strip()
            name = f"bluesky:{clean_feed}"
            self._source_status[name] = SourceStatus(
                id=f"bluesky_{clean_feed}",
                name=name,
                platform=SourcePlatform.BLUESKY,
                community=clean_feed,
                category="federated_social",
                status="ok",
                item_count=0,
            )

        for server in getattr(settings, "MASTODON_SERVERS", ["mastodon.social"]):
            clean_server = server.replace("https://", "").replace("http://", "").strip().rstrip("/")
            name = f"mastodon:{clean_server}:#meme"
            self._source_status[name] = SourceStatus(
                id=f"mastodon_{clean_server}_meme",
                name=name,
                platform=SourcePlatform.MASTODON,
                community="#meme",
                category="federated_social",
                status="ok",
                item_count=0,
            )

        channel_names = {
            "UCaHT88aobpcvRFEuy4v5Clg": "Lessons in Meme Culture",
            "UCbrPqq29C9Q_TQP7OFFRzcw": "Know Your Meme Video",
            "UCq9UQ0TUfI9GyzSiZ2uNx5Q": "Daily Dose of Memes",
            "UC9sY9S-ddN-1E0jD2fFWLig": "Grandayy",
            "UC2vpvibGYfBcb14l6CLVdiA": "Memer Man",
        }
        for channel_id in getattr(settings, "YOUTUBE_CHANNELS", []):
            name = f"youtube:{channel_id}"
            comm = channel_names.get(channel_id, channel_id)
            self._source_status[name] = SourceStatus(
                id=f"youtube_{channel_id.lower()}",
                name=name,
                platform=SourcePlatform.YOUTUBE,
                community=comm,
                category="video_creator",
                status="ok",
                item_count=0,
            )

    def count(self) -> int:
        """Return total number of cached memes."""
        with self._lock:
            return len(self._by_id)

    def clear(self) -> None:
        """Reset all in-memory indices and cache maps."""
        with self._lock:
            self._by_id.clear()
            self._by_content_hash.clear()
            self._by_author_title.clear()
            self._source_tokens_by_id.clear()
            self._latest_index.clear()
            self._latest_index_sfw.clear()
            self._trending_index.clear()
            self._trending_index_sfw.clear()
            self._by_source_latest.clear()
            self._by_source_latest_sfw.clear()
            self._by_source_trending.clear()
            self._by_source_trending_sfw.clear()
            for status in self._source_status.values():
                status.item_count = 0

    def upsert_memes(self, memes: Sequence[Union[NormalizedMeme, Meme, dict]]) -> int:
        """Upsert memes into memory store with deduplication and engagement merging."""
        if not memes:
            return len(self._by_id)

        with self._lock:
            for item in memes:
                if isinstance(item, dict):
                    m = NormalizedMeme(**item)
                elif isinstance(item, Meme):
                    source_plat = (
                        item.source_platform
                        if isinstance(item.source_platform, SourcePlatform)
                        else (
                            SourcePlatform.REDDIT
                            if "reddit" in str(item.source).lower()
                            else SourcePlatform.KNOWYOURMEME
                        )
                    )
                    m = NormalizedMeme(
                        id=item.id,
                        title=item.title,
                        media_url=item.url or item.media_url,
                        media_type=item.media_type,
                        source_platform=source_plat,
                        source_community=item.source_community,
                        permalink=item.permalink,
                        author=item.author,
                        score=item.score,
                        num_comments=item.num_comments,
                        created_at=item.created_at,
                        is_nsfw=item.is_nsfw,
                        domain=item.domain,
                        content_hash=item.content_hash,
                        trending_score=item.trending_score,
                    )
                else:
                    m = item

                from app.core.dedup import normalize_title, normalize_author_handle, compute_semantic_title_hash

                content_hash = m.content_hash or compute_content_hash(m.media_url, m.title)
                existing_id = self._by_content_hash.get(content_hash)

                norm_auth = normalize_author_handle(m.author)
                clean_t = normalize_title(m.title)
                title_hash = compute_semantic_title_hash(m.title) if clean_t else ""
                author_title_key = f"{norm_auth}|{title_hash}" if (norm_auth and norm_auth not in ("unknown", "anonymous", "test_author") and len(clean_t) >= 5) else ""

                if not existing_id and author_title_key:
                    existing_id = self._by_author_title.get(author_title_key)

                target_id = existing_id if existing_id else m.id

                plat_str = (
                    m.source_platform.value
                    if isinstance(m.source_platform, SourcePlatform)
                    else str(m.source_platform)
                )
                comm_str = m.source_community or ""
                new_tokens = _extract_source_tokens(plat_str, comm_str)

                now = time.time()

                if target_id in self._by_id:
                    existing = self._by_id[target_id]
                    # Engagement maximization & temporal anchor preservation
                    merged_score = max(existing.score, m.score)
                    merged_comments = max(existing.num_comments, m.num_comments)
                    merged_created_at = min(existing.created_at, m.created_at)
                    merged_nsfw = existing.is_nsfw or m.is_nsfw

                    recalculated_trending = calculate_trending_score(
                        merged_score,
                        merged_comments,
                        merged_created_at,
                    )

                    # Snapshot tracking for velocity & acceleration
                    snaps = self._snapshots.setdefault(target_id, [])
                    if not snaps or (now - snaps[-1][0]) >= 30.0:
                        snaps.append((now, merged_score))
                        if len(snaps) > 20:
                            self._snapshots[target_id] = snaps[-20:]

                    velocity, acceleration = calculate_velocity_and_acceleration(snaps)
                    stage = classify_lifecycle_stage(
                        velocity=velocity,
                        acceleration=acceleration,
                        created_at=merged_created_at,
                        platform=plat_str,
                        total_score=merged_score,
                    )

                    updated_meme = existing.model_copy(
                        update={
                            "title": m.title or existing.title,
                            "score": merged_score,
                            "num_comments": merged_comments,
                            "created_at": merged_created_at,
                            "is_nsfw": merged_nsfw,
                            "content_hash": content_hash,
                            "trending_score": recalculated_trending,
                            "velocity": velocity,
                            "acceleration": acceleration,
                            "lifecycle_stage": stage.value,
                            "first_seen_at": getattr(existing, "first_seen_at", None) or now,
                            "last_seen_at": now,
                        }
                    )
                    self._by_id[target_id] = updated_meme
                    self._by_content_hash[content_hash] = target_id
                    if author_title_key:
                        self._by_author_title[author_title_key] = target_id
                    existing_tokens = self._source_tokens_by_id.get(target_id, set())
                    self._source_tokens_by_id[target_id] = existing_tokens | new_tokens

                    # Trigger breakout webhook alert if entering viral stage
                    if stage == LifecycleStage.VIRAL:
                        try:
                            loop = asyncio.get_running_loop()
                            loop.create_task(dispatch_viral_webhook(updated_meme))
                        except RuntimeError:
                            pass
                else:
                    trending = m.trending_score or calculate_trending_score(
                        m.score,
                        m.num_comments,
                        m.created_at,
                    )

                    # Initial snapshot for new meme
                    snaps = self._snapshots.setdefault(m.id, [])
                    snaps.append((now, m.score))
                    age_hours = max(0.01, (now - m.created_at) / 3600.0)
                    initial_velocity = round(m.score / age_hours, 2) if age_hours <= 48.0 else 0.0

                    stage = classify_lifecycle_stage(
                        velocity=initial_velocity,
                        acceleration=0.0,
                        created_at=m.created_at,
                        platform=plat_str,
                        total_score=m.score,
                    )

                    new_meme = m.model_copy(
                        update={
                            "content_hash": content_hash,
                            "trending_score": trending,
                            "velocity": initial_velocity,
                            "acceleration": 0.0,
                            "lifecycle_stage": stage.value,
                            "first_seen_at": now,
                            "last_seen_at": now,
                        }
                    )
                    self._by_id[new_meme.id] = new_meme
                    self._by_content_hash[content_hash] = new_meme.id
                    if author_title_key:
                        self._by_author_title[author_title_key] = new_meme.id
                    self._source_tokens_by_id[new_meme.id] = new_tokens

                    if stage == LifecycleStage.VIRAL:
                        try:
                            loop = asyncio.get_running_loop()
                            loop.create_task(dispatch_viral_webhook(new_meme))
                        except RuntimeError:
                            pass

            # Rebuild pre-sorted primary and secondary indices atomically
            all_memes = list(self._by_id.values())
            latest_sorted = sorted(all_memes, key=lambda x: (-x.created_at, x.id))
            trending_sorted = sorted(
                all_memes, key=lambda x: (-x.trending_score, -x.created_at, x.id)
            )

            self._latest_index = latest_sorted
            self._latest_index_sfw = [m for m in latest_sorted if not m.is_nsfw]
            self._trending_index = trending_sorted
            self._trending_index_sfw = [m for m in trending_sorted if not m.is_nsfw]

            by_src_latest: Dict[str, List[NormalizedMeme]] = {}
            by_src_latest_sfw: Dict[str, List[NormalizedMeme]] = {}
            for m in latest_sorted:
                tokens = self._source_tokens_by_id.get(m.id, set())
                for t in tokens:
                    if t not in by_src_latest:
                        by_src_latest[t] = []
                    by_src_latest[t].append(m)
                    if not m.is_nsfw:
                        if t not in by_src_latest_sfw:
                            by_src_latest_sfw[t] = []
                        by_src_latest_sfw[t].append(m)

            by_src_trending: Dict[str, List[NormalizedMeme]] = {}
            by_src_trending_sfw: Dict[str, List[NormalizedMeme]] = {}
            for m in trending_sorted:
                tokens = self._source_tokens_by_id.get(m.id, set())
                for t in tokens:
                    if t not in by_src_trending:
                        by_src_trending[t] = []
                    by_src_trending[t].append(m)
                    if not m.is_nsfw:
                        if t not in by_src_trending_sfw:
                            by_src_trending_sfw[t] = []
                        by_src_trending_sfw[t].append(m)

            self._by_source_latest = by_src_latest
            self._by_source_latest_sfw = by_src_latest_sfw
            self._by_source_trending = by_src_trending
            self._by_source_trending_sfw = by_src_trending_sfw

            # Update item counts for sources
            counts_by_source: Dict[str, int] = {}
            for m in all_memes:
                plat_str = (
                    m.source_platform.value
                    if isinstance(m.source_platform, SourcePlatform)
                    else str(m.source_platform)
                )
                source_key = f"{plat_str}:{m.source_community}"
                counts_by_source[source_key] = counts_by_source.get(source_key, 0) + 1

            for source_name, status in self._source_status.items():
                if source_name in counts_by_source:
                    status.item_count = counts_by_source[source_name]
                else:
                    # Check platform match
                    plat_prefix = source_name.split(":")[0]
                    matching_count = sum(
                        1
                        for m in all_memes
                        if (
                            m.source_platform.value
                            if isinstance(m.source_platform, SourcePlatform)
                            else str(m.source_platform)
                        )
                        == plat_prefix
                        and (
                            source_name.split(":")[-1] in (m.source_community or "")
                            or (m.source_community or "") in source_name
                            or not source_name.split(":")[-1]
                            or (plat_prefix == "youtube")
                        )
                    )
                    status.item_count = matching_count

            return len(self._by_id)

    def _resolve_source_query_key(self, source_filter: str) -> Optional[str]:
        """Resolve query filter string to a pre-indexed token key."""
        if not source_filter:
            return None
        q = source_filter.lower().strip()
        if not q:
            return None

        # Exact match in indexed tokens
        if q in self._by_source_latest:
            return q

        # Subreddit prefix variation (r/memes <-> memes)
        clean_q = q[2:].strip() if q.startswith("r/") else q
        if clean_q in self._by_source_latest:
            return clean_q
        if f"r/{clean_q}" in self._by_source_latest:
            return f"r/{clean_q}"

        # Composite parsing (reddit:r/memes, reddit/memes, etc.)
        if ":" in q or "/" in q:
            parts = [p.strip() for p in q.replace(":", "/").split("/") if p.strip()]
            if len(parts) >= 2:
                p_plat, p_comm = parts[0], parts[-1]
                p_clean_comm = p_comm[2:].strip() if p_comm.startswith("r/") else p_comm
                candidates = [
                    f"{p_plat}:{p_comm}",
                    f"{p_plat}/{p_comm}",
                    f"{p_plat}:{p_clean_comm}",
                    f"{p_plat}/{p_clean_comm}",
                    f"{p_plat}:r/{p_clean_comm}",
                    f"{p_plat}/r/{p_clean_comm}",
                ]
                for cand in candidates:
                    if cand in self._by_source_latest:
                        return cand

        # Unmatched filter string
        return None

    def _parse_time_window(self, time_window: Optional[str]) -> Optional[float]:
        """Parse time window string into cutoff seconds."""
        if not time_window:
            return None
        tw = time_window.lower().strip()
        if tw == "1h":
            return 3600.0
        if tw == "6h":
            return 21600.0
        if tw == "24h":
            return 86400.0
        if tw == "7d":
            return 604800.0
        return None

    def _matches_source(self, meme: NormalizedMeme, source_filter: Optional[str]) -> bool:
        """Check if a meme matches the source query filter (backward compatible)."""
        if not source_filter:
            return True
        q = source_filter.lower().strip()
        if not q:
            return True

        tokens = self._source_tokens_by_id.get(meme.id)
        if tokens is not None:
            resolved_key = self._resolve_source_query_key(source_filter)
            if resolved_key is not None and resolved_key in tokens:
                return True

        # Fallback to direct string logic if meme is not in indexed cache
        plat_str = (
            meme.source_platform.value
            if isinstance(meme.source_platform, SourcePlatform)
            else str(meme.source_platform)
        ).lower()
        comm_str = (meme.source_community or "").lower().strip()
        clean_q = q[2:].strip() if q.startswith("r/") else q
        clean_comm = comm_str[2:].strip() if comm_str.startswith("r/") else comm_str

        if q in ("reddit", "knowyourmeme", "bluesky", "mastodon", "youtube"):
            return plat_str == q
        if q in ("kym", "know your meme"):
            return plat_str in ("knowyourmeme", "kym")
        if q in ("bsky",):
            return plat_str in ("bluesky", "bsky")
        if q in ("masto", "fediverse"):
            return plat_str in ("mastodon", "masto", "fediverse")
        if q in ("yt",):
            return plat_str in ("youtube", "yt")
        if clean_q == clean_comm or q == comm_str:
            return True

        if ":" in q or "/" in q:
            parts = [p.strip() for p in q.replace(":", "/").split("/") if p.strip()]
            if len(parts) >= 2:
                p_plat, p_comm = parts[0], parts[-1]
                p_clean_comm = p_comm[2:].strip() if p_comm.startswith("r/") else p_comm
                plat_match = (p_plat == plat_str) or (
                    p_plat in ("kym", "knowyourmeme") and plat_str in ("knowyourmeme", "kym")
                )
                comm_match = (p_clean_comm == clean_comm) or (p_comm == comm_str)
                if plat_match and comm_match:
                    return True

        return q == plat_str

    def _apply_secondary_filters(
        self,
        candidates: List[NormalizedMeme],
        generation: Optional[str] = None,
        media_format: Optional[str] = None,
        category: Optional[str] = None,
        is_short: Optional[bool] = None,
        lifecycle: Optional[str] = None,
        min_velocity: Optional[float] = None,
        country: Optional[str] = None,
        language: Optional[str] = None,
    ) -> List[NormalizedMeme]:
        """Apply generation, media format, source category, short-form, lifecycle, country, and language filters."""
        if not candidates:
            return []

        res = candidates
        if generation and generation.lower() != "all":
            gen_val = generation.lower().strip()
            res = [
                m for m in res
                if str(getattr(m, "generation", "gen_z")).lower() == gen_val
                or (hasattr(getattr(m, "generation", None), "value") and getattr(m, "generation").value == gen_val)
            ]

        if media_format:
            fmt_val = media_format.lower().strip()
            res = [
                m for m in res
                if (isinstance(m.media_type, MediaType) and m.media_type.value == fmt_val)
                or str(m.media_type).lower() == fmt_val
            ]

        if category:
            cat_val = category.lower().strip()
            res = [
                m for m in res
                if getattr(m, "source_category", "community_forum").lower() == cat_val
            ]

        if is_short is not None:
            res = [
                m for m in res
                if getattr(m, "is_short", False) == is_short
            ]

        if lifecycle and lifecycle.lower() != "all":
            life_val = lifecycle.lower().strip()
            res = [
                m for m in res
                if getattr(m, "lifecycle_stage", "emerging").lower() == life_val
            ]

        if min_velocity is not None:
            res = [
                m for m in res
                if getattr(m, "velocity", 0.0) >= min_velocity
            ]

        if country and country.lower() != "all":
            c_target = country.upper().strip()
            if c_target == "GLOBAL":
                res = [
                    m for m in res
                    if getattr(m, "country_code", "GLOBAL").upper() == "GLOBAL"
                    or not getattr(m, "country_code", None)
                ]
            else:
                res = [
                    m for m in res
                    if getattr(m, "country_code", "GLOBAL").upper() == c_target
                ]

        if language and language.lower() != "all":
            l_target = language.lower().strip()
            res = [
                m for m in res
                if getattr(m, "language", "en").lower() == l_target
            ]

        return res

    def get_latest(
        self,
        limit: int = 20,
        offset: int = 0,
        source: Optional[str] = None,
        nsfw: bool = False,
        time_window: Optional[str] = None,
        generation: Optional[str] = None,
        format: Optional[str] = None,
        category: Optional[str] = None,
        is_short: Optional[bool] = None,
        lifecycle: Optional[str] = None,
        min_velocity: Optional[float] = None,
        country: Optional[str] = None,
        language: Optional[str] = None,
    ) -> Tuple[List[NormalizedMeme], int]:
        """Retrieve newest memes sorted by created_at descending."""
        with self._lock:
            # Resolve candidate list via pre-indexed maps
            if source:
                key = self._resolve_source_query_key(source)
                if key is None:
                    return [], 0
                candidates = (
                    self._by_source_latest.get(key, [])
                    if nsfw
                    else self._by_source_latest_sfw.get(key, [])
                )
            else:
                candidates = self._latest_index if nsfw else self._latest_index_sfw

            if not candidates:
                return [], 0

            # Apply secondary filters (generation, format, category, shorts, lifecycle, country, language)
            candidates = self._apply_secondary_filters(
                candidates,
                generation=generation,
                media_format=format,
                category=category,
                is_short=is_short,
                lifecycle=lifecycle,
                min_velocity=min_velocity,
                country=country,
                language=language,
            )

            if not candidates:
                return [], 0

            # Time window cutoff
            window_seconds = self._parse_time_window(time_window)
            if window_seconds is not None:
                cutoff = time.time() - window_seconds
                filtered = []
                for m in candidates:
                    if m.created_at < cutoff:
                        break
                    filtered.append(m)
                total = len(filtered)
                items = filtered[offset : offset + limit] if offset < total else []
                return items, total

            total = len(candidates)
            items = candidates[offset : offset + limit] if offset < total else []
            return items, total

    def get_trending(
        self,
        limit: int = 20,
        offset: int = 0,
        source: Optional[str] = None,
        nsfw: bool = False,
        time_window: Optional[str] = None,
        generation: Optional[str] = None,
        format: Optional[str] = None,
        category: Optional[str] = None,
        is_short: Optional[bool] = None,
        lifecycle: Optional[str] = None,
        min_velocity: Optional[float] = None,
        country: Optional[str] = None,
        language: Optional[str] = None,
    ) -> Tuple[List[NormalizedMeme], int]:
        """Retrieve trending memes sorted by trending_score descending."""
        with self._lock:
            # Resolve candidate list via pre-indexed maps
            if source:
                key = self._resolve_source_query_key(source)
                if key is None:
                    return [], 0
                candidates = (
                    self._by_source_trending.get(key, [])
                    if nsfw
                    else self._by_source_trending_sfw.get(key, [])
                )
            else:
                candidates = self._trending_index if nsfw else self._trending_index_sfw

            if not candidates:
                return [], 0

            # Apply secondary filters (generation, format, category, shorts, lifecycle, country, language)
            candidates = self._apply_secondary_filters(
                candidates,
                generation=generation,
                media_format=format,
                category=category,
                is_short=is_short,
                lifecycle=lifecycle,
                min_velocity=min_velocity,
                country=country,
                language=language,
            )

            if not candidates:
                return [], 0

            # Time window cutoff
            window_seconds = self._parse_time_window(time_window)
            if window_seconds is not None:
                cutoff = time.time() - window_seconds
                filtered = [m for m in candidates if m.created_at >= cutoff]
                total = len(filtered)
                items = filtered[offset : offset + limit] if offset < total else []
                return items, total

            total = len(candidates)
            items = candidates[offset : offset + limit] if offset < total else []
            return items, total

    def get_random(
        self,
        source: Optional[str] = None,
        nsfw: bool = False,
        generation: Optional[str] = None,
        format: Optional[str] = None,
        category: Optional[str] = None,
        is_short: Optional[bool] = None,
        lifecycle: Optional[str] = None,
        min_velocity: Optional[float] = None,
        country: Optional[str] = None,
        language: Optional[str] = None,
    ) -> Optional[NormalizedMeme]:
        """Retrieve single random meme matching filter criteria."""
        with self._lock:
            if source:
                key = self._resolve_source_query_key(source)
                if key is None:
                    return None
                candidates = (
                    self._by_source_latest.get(key, [])
                    if nsfw
                    else self._by_source_latest_sfw.get(key, [])
                )
            else:
                candidates = self._latest_index if nsfw else self._latest_index_sfw

            if not candidates:
                return None

            candidates = self._apply_secondary_filters(
                candidates,
                generation=generation,
                media_format=format,
                category=category,
                is_short=is_short,
                lifecycle=lifecycle,
                min_velocity=min_velocity,
                country=country,
                language=language,
            )

            if not candidates:
                return None
            return random.choice(candidates)

    def get_by_id(self, meme_id: str) -> Optional[NormalizedMeme]:
        """Retrieve a meme by its unique identifier."""
        with self._lock:
            return self._by_id.get(meme_id)

    def get_by_content_hash(self, content_hash: str) -> Optional[NormalizedMeme]:
        """Retrieve a meme by its content hash."""
        with self._lock:
            meme_id = self._by_content_hash.get(content_hash)
            if meme_id:
                return self._by_id.get(meme_id)
            return None

    def update_source_status(self, status: SourceStatus) -> None:
        """Update or register health status for an individual ingestion source."""
        with self._lock:
            self._source_status[status.name] = status

    def get_sources_status(self) -> List[SourceStatus]:
        """Return list of all registered source statuses."""
        with self._lock:
            return list(self._source_status.values())

    def get_sources(self) -> List[SourceStatus]:
        """Alias for get_sources_status."""
        return self.get_sources_status()

    def get_health_status(self) -> HealthResponse:
        """Return aggregated service health response."""
        with self._lock:
            uptime = round(time.time() - self._start_time, 2)
            sources = list(self._source_status.values())
            healthy_count = sum(1 for s in sources if s.status == "ok")
            total_sources = len(sources)
            total_items = len(self._by_id)

            overall_status = "ok"
            if healthy_count == 0 and total_sources > 0:
                overall_status = "unhealthy"
            elif healthy_count < total_sources:
                overall_status = "degraded"

            return HealthResponse(
                status=overall_status,
                uptime_seconds=uptime,
                total_memes=total_items,
                total_memes_cached=total_items,
                healthy_sources=healthy_count,
                total_sources=total_sources,
                sources=sources,
            )

    def get_health(self) -> HealthResponse:
        """Alias for get_health_status."""
        return self.get_health_status()

    async def hydrate_from_db(self, sqlite_store: Any) -> int:
        """Hydrate in-memory cache from persistent SQLite database."""
        loaded_memes = await sqlite_store.load_all_memes()
        if loaded_memes:
            self.upsert_memes(loaded_memes)
            logger.info("Hydrated %d memes from SQLite store.", len(loaded_memes))
        return len(loaded_memes)
