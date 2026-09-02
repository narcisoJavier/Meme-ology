"""In-memory fast cache with atomic indices for sub-millisecond query latencies."""

from __future__ import annotations

import logging
import random
import threading
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from app.config import get_settings
from app.core.dedup import compute_content_hash
from app.core.ranking import calculate_trending_score
from app.models.meme import MediaType, Meme, NormalizedMeme, SourcePlatform
from app.models.source import HealthResponse, SourceStatus

logger = logging.getLogger(__name__)


def _extract_source_tokens(platform_val: str, comm_val: str) -> Set[str]:
    """Pre-extract all matching query tokens for a given platform and community."""
    tokens: Set[str] = set()
    plat = platform_val.lower().strip()
    comm = comm_val.lower().strip()
    clean_comm = comm[2:].strip() if comm.startswith("r/") else comm

    # Direct platform tokens
    tokens.add(plat)
    if plat == "reddit":
        tokens.add("reddit")
    elif plat in ("knowyourmeme", "kym"):
        tokens.add("knowyourmeme")
        tokens.add("kym")
        tokens.add("know your meme")

    # Community tokens
    if comm:
        tokens.add(comm)
    if clean_comm:
        tokens.add(clean_comm)
        tokens.add(f"r/{clean_comm}")

    # Composite tokens
    plats = [plat]
    if plat in ("knowyourmeme", "kym"):
        plats.extend(["knowyourmeme", "kym"])
    elif plat == "reddit":
        plats.append("reddit")

    comms = [c for c in (comm, clean_comm, f"r/{clean_comm}" if clean_comm else None) if c]
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
        self._source_tokens_by_id: Dict[str, Set[str]] = {}

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

                content_hash = m.content_hash or compute_content_hash(m.media_url, m.title)
                existing_id = self._by_content_hash.get(content_hash)
                target_id = existing_id if existing_id else m.id

                plat_str = (
                    m.source_platform.value
                    if isinstance(m.source_platform, SourcePlatform)
                    else str(m.source_platform)
                )
                comm_str = m.source_community or ""
                new_tokens = _extract_source_tokens(plat_str, comm_str)

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

                    updated_meme = existing.model_copy(
                        update={
                            "score": merged_score,
                            "num_comments": merged_comments,
                            "created_at": merged_created_at,
                            "is_nsfw": merged_nsfw,
                            "content_hash": content_hash,
                            "trending_score": recalculated_trending,
                        }
                    )
                    self._by_id[target_id] = updated_meme
                    self._by_content_hash[content_hash] = target_id
                    existing_tokens = self._source_tokens_by_id.get(target_id, set())
                    self._source_tokens_by_id[target_id] = existing_tokens | new_tokens
                else:
                    trending = m.trending_score or calculate_trending_score(
                        m.score,
                        m.num_comments,
                        m.created_at,
                    )
                    new_meme = m.model_copy(
                        update={
                            "content_hash": content_hash,
                            "trending_score": trending,
                        }
                    )
                    self._by_id[new_meme.id] = new_meme
                    self._by_content_hash[content_hash] = new_meme.id
                    self._source_tokens_by_id[new_meme.id] = new_tokens

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
                            or not source_name.split(":")[-1]
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

        # 1. Exact match in indexed tokens
        if q in self._by_source_latest:
            return q

        # 2. Subreddit prefix variation (r/memes <-> memes)
        clean_q = q[2:].strip() if q.startswith("r/") else q
        if clean_q in self._by_source_latest:
            return clean_q
        if f"r/{clean_q}" in self._by_source_latest:
            return f"r/{clean_q}"

        # 3. Composite parsing (reddit:r/memes, reddit/memes, etc.)
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

        if q in ("reddit", "knowyourmeme"):
            return plat_str == q
        if q in ("kym", "know your meme"):
            return plat_str in ("knowyourmeme", "kym")
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

    def get_latest(
        self,
        limit: int = 20,
        offset: int = 0,
        source: Optional[str] = None,
        nsfw: bool = False,
        time_window: Optional[str] = None,
        generation: Optional[str] = None,
    ) -> Tuple[List[NormalizedMeme], int]:
        """Retrieve newest memes sorted by created_at descending."""
        with self._lock:
            # 1. Resolve candidate list via pre-indexed maps
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

            # 2. Generational filter
            if generation and generation.lower() != "all":
                gen_val = generation.lower().strip()
                candidates = [
                    m for m in candidates
                    if str(getattr(m, "generation", "gen_z")).lower() == gen_val
                    or (hasattr(getattr(m, "generation", None), "value") and getattr(m, "generation").value == gen_val)
                ]

            if not candidates:
                return [], 0

            # 3. Time window cutoff
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
    ) -> Tuple[List[NormalizedMeme], int]:
        """Retrieve trending memes sorted by trending_score descending."""
        with self._lock:
            # 1. Resolve candidate list via pre-indexed maps
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

            # 2. Generational filter
            if generation and generation.lower() != "all":
                gen_val = generation.lower().strip()
                candidates = [
                    m for m in candidates
                    if str(getattr(m, "generation", "gen_z")).lower() == gen_val
                    or (hasattr(getattr(m, "generation", None), "value") and getattr(m, "generation").value == gen_val)
                ]

            if not candidates:
                return [], 0

            # 3. Time window cutoff
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

            if generation and generation.lower() != "all":
                gen_val = generation.lower().strip()
                candidates = [
                    m for m in candidates
                    if str(getattr(m, "generation", "gen_z")).lower() == gen_val
                    or (hasattr(getattr(m, "generation", None), "value") and getattr(m, "generation").value == gen_val)
                ]

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
