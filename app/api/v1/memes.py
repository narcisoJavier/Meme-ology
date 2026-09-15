"""Meme REST API endpoints for latest, trending, and random meme discovery."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.models.meme import GlobalTrendsResponse, Meme, PaginatedMemeResponse, TrendingTopic
from app.storage.memory_store import MemoryStore

logger = logging.getLogger(__name__)

router = APIRouter()


def get_memory_store(request: Request) -> MemoryStore:
    """Dependency provider for retrieving the MemoryStore from application state."""
    store = getattr(request.app.state, "memory_store", None)
    if store is None:
        store = MemoryStore()
        request.app.state.memory_store = store
        if not getattr(request.app.state, "_is_seeded", False):
            request.app.state._is_seeded = True
            from app.core.seed_data import get_initial_generational_memes
            store.upsert_memes(get_initial_generational_memes())
    return store


@router.get(
    "/latest",
    response_model=PaginatedMemeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get newest memes",
    description="Retrieve newest memes across Reddit, Bluesky, Know Your Meme, and Mastodon sorted by publication date descending with pagination and filtering.",
    responses={
        200: {"description": "Paginated list of newest memes"},
        422: {"description": "Validation error on query parameters"},
    },
)
async def get_latest_memes(
    limit: int = Query(default=20, ge=1, le=100, description="Page limit (1-100 items)"),
    offset: int = Query(default=0, ge=0, description="Pagination offset index"),
    source: Optional[str] = Query(
        default=None,
        description="Filter by platform ('reddit', 'bluesky', 'knowyourmeme', 'mastodon') or specific community (e.g. 'r/dankmemes', '#meme')",
    ),
    nsfw: bool = Query(default=False, description="Include NSFW content if true (default false)"),
    time_window: Optional[str] = Query(
        default=None,
        description="Optional time window filter (e.g., 1h, 6h, 24h, 7d, all)",
    ),
    generation: Optional[str] = Query(
        default=None,
        description="Generational era filter ('gen_alpha', 'gen_z', 'millennial', 'gen_x')",
    ),
    format: Optional[str] = Query(
        default=None,
        description="Media format filter ('video', 'image', 'gif')",
    ),
    category: Optional[str] = Query(
        default=None,
        description="Source category taxonomy filter ('video_creator', 'community_forum', 'encyclopedia', 'federated_social')",
    ),
    is_short: Optional[bool] = Query(
        default=None,
        description="Filter for vertical short-form videos (YouTube Shorts, Reels, etc.)",
    ),
    lifecycle: Optional[str] = Query(
        default=None,
        description="Lifecycle stage filter ('emerging', 'viral', 'peak', 'cooling')",
    ),
    min_velocity: Optional[float] = Query(
        default=None,
        description="Minimum score/engagement growth velocity per hour",
    ),
    country: Optional[str] = Query(
        default=None,
        description="Filter by country or region code (e.g. 'US', 'DE', 'FR', 'BR', 'GLOBAL')",
    ),
    language: Optional[str] = Query(
        default=None,
        description="Filter by language code (e.g. 'en', 'de', 'fr', 'pt', 'es')",
    ),
    store: MemoryStore = Depends(get_memory_store),
) -> PaginatedMemeResponse:
    """Return paginated list of newest memes ordered by created_at DESC."""
    items, total = store.get_latest(
        limit=limit,
        offset=offset,
        source=source,
        nsfw=nsfw,
        time_window=time_window,
        generation=generation,
        format=format,
        category=category,
        is_short=is_short,
        lifecycle=lifecycle,
        min_velocity=min_velocity,
        country=country,
        language=language,
    )
    has_more = (offset + len(items)) < total
    pydantic_memes = [Meme.from_normalized(m) for m in items]

    return PaginatedMemeResponse(
        items=pydantic_memes,
        total=total,
        limit=limit,
        offset=offset,
        has_more=has_more,
    )


@router.get(
    "/trending",
    response_model=PaginatedMemeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get trending memes",
    description="Retrieve trending memes ranked by virality/velocity score using time-decay: trending_score = (upvotes + 1.5 * comments) * exp(-lambda * delta_t), with pagination and filtering across Reddit, Bluesky, Know Your Meme, and Mastodon.",
    responses={
        200: {"description": "Paginated list of trending memes sorted by trending_score"},
        422: {"description": "Validation error on query parameters"},
    },
)
async def get_trending_memes(
    limit: int = Query(default=20, ge=1, le=100, description="Page limit (1-100 items)"),
    offset: int = Query(default=0, ge=0, description="Pagination offset index"),
    source: Optional[str] = Query(
        default=None,
        description="Filter by platform ('reddit', 'bluesky', 'knowyourmeme', 'mastodon') or specific community (e.g. 'r/dankmemes', '#meme')",
    ),
    nsfw: bool = Query(default=False, description="Include NSFW content if true (default false)"),
    time_window: Optional[str] = Query(
        default=None,
        description="Optional time window filter (e.g., 1h, 6h, 24h, 7d, all)",
    ),
    generation: Optional[str] = Query(
        default=None,
        description="Generational era filter ('gen_alpha', 'gen_z', 'millennial', 'gen_x')",
    ),
    format: Optional[str] = Query(
        default=None,
        description="Media format filter ('video', 'image', 'gif')",
    ),
    category: Optional[str] = Query(
        default=None,
        description="Source category taxonomy filter ('video_creator', 'community_forum', 'encyclopedia', 'federated_social')",
    ),
    is_short: Optional[bool] = Query(
        default=None,
        description="Filter for vertical short-form videos (YouTube Shorts, Reels, etc.)",
    ),
    lifecycle: Optional[str] = Query(
        default=None,
        description="Lifecycle stage filter ('emerging', 'viral', 'peak', 'cooling')",
    ),
    min_velocity: Optional[float] = Query(
        default=None,
        description="Minimum score/engagement growth velocity per hour",
    ),
    country: Optional[str] = Query(
        default=None,
        description="Filter by country or region code (e.g. 'US', 'DE', 'FR', 'BR', 'GLOBAL')",
    ),
    language: Optional[str] = Query(
        default=None,
        description="Filter by language code (e.g. 'en', 'de', 'fr', 'pt', 'es')",
    ),
    store: MemoryStore = Depends(get_memory_store),
) -> PaginatedMemeResponse:
    """Return paginated list of trending memes ordered by trending_score DESC."""
    items, total = store.get_trending(
        limit=limit,
        offset=offset,
        source=source,
        nsfw=nsfw,
        time_window=time_window,
        generation=generation,
        format=format,
        category=category,
        is_short=is_short,
        lifecycle=lifecycle,
        min_velocity=min_velocity,
        country=country,
        language=language,
    )
    has_more = (offset + len(items)) < total
    pydantic_memes = [Meme.from_normalized(m) for m in items]

    return PaginatedMemeResponse(
        items=pydantic_memes,
        total=total,
        limit=limit,
        offset=offset,
        has_more=has_more,
    )


@router.get(
    "/viral",
    response_model=PaginatedMemeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get breakout viral memes",
    description="Retrieve memes currently in the 'viral' breakout stage with highest growth velocity.",
)
async def get_viral_breakout_memes(
    limit: int = Query(default=20, ge=1, le=100, description="Page limit"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    store: MemoryStore = Depends(get_memory_store),
) -> PaginatedMemeResponse:
    """Return memes in the viral breakout stage."""
    items, total = store.get_trending(limit=limit, offset=offset, lifecycle="viral")
    if not items:
        # Fallback to top velocity memes if none strictly tagged viral yet
        items, total = store.get_trending(limit=limit, offset=offset)
    has_more = (offset + len(items)) < total
    return PaginatedMemeResponse(
        items=[Meme.from_normalized(m) for m in items],
        total=total,
        limit=limit,
        offset=offset,
        has_more=has_more,
    )


@router.get(
    "/random",
    response_model=Meme,
    status_code=status.HTTP_200_OK,
    summary="Get a random meme",
    description="Fetch a single pseudo-random meme matching optional source platform, community, generation, and NSFW filters.",
    responses={
        200: {"description": "Random meme payload"},
        404: {"description": "No memes found matching the specified criteria"},
        422: {"description": "Validation error on query parameters"},
    },
)
async def get_random_meme(
    source: Optional[str] = Query(
        default=None,
        description="Optional source filter ('reddit', 'bluesky', 'knowyourmeme', 'mastodon', 'r/dankmemes', etc.)",
    ),
    nsfw: bool = Query(default=False, description="Include NSFW content if true (default false)"),
    generation: Optional[str] = Query(
        default=None,
        description="Optional generational filter ('gen_alpha', 'gen_z', 'millennial', 'gen_x')",
    ),
    format: Optional[str] = Query(
        default=None,
        description="Media format filter ('video', 'image', 'gif')",
    ),
    category: Optional[str] = Query(
        default=None,
        description="Source category filter ('video_creator', 'community_forum', 'encyclopedia', 'federated_social')",
    ),
    is_short: Optional[bool] = Query(
        default=None,
        description="Filter for vertical short-form videos",
    ),
    lifecycle: Optional[str] = Query(
        default=None,
        description="Lifecycle stage filter ('emerging', 'viral', 'peak', 'cooling')",
    ),
    min_velocity: Optional[float] = Query(
        default=None,
        description="Minimum score growth velocity per hour",
    ),
    country: Optional[str] = Query(
        default=None,
        description="Filter by country or region code (e.g. 'US', 'DE', 'FR', 'BR', 'GLOBAL')",
    ),
    language: Optional[str] = Query(
        default=None,
        description="Filter by language code (e.g. 'en', 'de', 'fr', 'pt', 'es')",
    ),
    store: MemoryStore = Depends(get_memory_store),
) -> Meme:
    """Return a single random meme matching specified criteria."""
    meme = store.get_random(
        source=source,
        nsfw=nsfw,
        generation=generation,
        format=format,
        category=category,
        is_short=is_short,
        lifecycle=lifecycle,
        min_velocity=min_velocity,
        country=country,
        language=language,
    )
    if meme is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No memes found matching the specified criteria",
        )
    return Meme.from_normalized(meme)


@router.get(
    "/local",
    response_model=PaginatedMemeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get localized memes for user's region",
    description="Retrieve trending memes tailored to the user's detected or specified geographic location/country.",
)
async def get_local_memes(
    request: Request,
    country: Optional[str] = Query(default=None, description="Country code (e.g. 'US', 'DE', 'FR', 'BR', 'GLOBAL')"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    store: MemoryStore = Depends(get_memory_store),
) -> PaginatedMemeResponse:
    """Return memes personalized to the user's detected or specified country/region."""
    target_country = country
    if not target_country:
        h_country = (
            request.headers.get("cf-ipcountry")
            or request.headers.get("x-country-code")
            or request.headers.get("x-vercel-ip-country")
        )
        if h_country:
            target_country = h_country.upper().strip()
        else:
            accept_lang = request.headers.get("accept-language", "").lower()
            if "de" in accept_lang:
                target_country = "DE"
            elif "fr" in accept_lang:
                target_country = "FR"
            elif "pt" in accept_lang or "br" in accept_lang:
                target_country = "BR"
            elif "es" in accept_lang:
                target_country = "ES"
            elif "ja" in accept_lang:
                target_country = "JP"
            else:
                target_country = "US"

    items, total = store.get_trending(limit=limit, offset=offset, country=target_country)
    if not items and target_country != "GLOBAL":
        items, total = store.get_trending(limit=limit, offset=offset)

    has_more = (offset + len(items)) < total
    return PaginatedMemeResponse(
        items=[Meme.from_normalized(m) for m in items],
        total=total,
        limit=limit,
        offset=offset,
        has_more=has_more,
    )


@router.get(
    "/trends/global",
    response_model=GlobalTrendsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get global meme trends and viral topics",
    description="Retrieve live global trends across all monitored networks, top viral topic clusters, and regional spread.",
)
async def get_global_trends(
    limit: int = Query(default=10, ge=1, le=50, description="Number of top global memes"),
    store: MemoryStore = Depends(get_memory_store),
) -> GlobalTrendsResponse:
    """Return global viral topics, trending memes, and active regions."""
    import collections
    import re
    import time

    # Retrieve top trending memes
    top_memes, _ = store.get_trending(limit=limit, nsfw=False)

    # Extract trending topic clusters from recent top memes
    all_memes, _ = store.get_trending(limit=100, nsfw=False)
    topic_counts: collections.Counter = collections.Counter()
    topic_scores: collections.defaultdict = collections.defaultdict(float)
    active_regions: set = set()

    for m in all_memes:
        c_code = getattr(m, "country_code", "GLOBAL") or "GLOBAL"
        active_regions.add(c_code.upper())
        tags = re.findall(r"#(\w+)", m.title)
        words = re.findall(r"\b[a-zA-Z0-9_]{4,}\b", m.title.lower())
        candidates = set(tags + words) - {
            "meme", "memes", "reddit", "bluesky", "post", "video", "image",
            "with", "from", "that", "this", "have", "they", "will", "when",
            "just", "like", "what", "your", "more", "some", "good"
        }
        for topic in candidates:
            topic_counts[topic] += 1
            topic_scores[topic] += getattr(m, "trending_score", 0.0)

    top_topics: list[TrendingTopic] = []
    for topic, count in topic_counts.most_common(8):
        top_topics.append(TrendingTopic(
            topic=f"#{topic}",
            count=count,
            trending_score=round(topic_scores[topic], 2),
        ))

    return GlobalTrendsResponse(
        timestamp=time.time(),
        top_topics=top_topics,
        top_memes=[Meme.from_normalized(m) for m in top_memes],
        active_regions=sorted(list(active_regions)),
    )
