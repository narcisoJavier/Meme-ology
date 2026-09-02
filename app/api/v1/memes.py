"""Meme REST API endpoints for latest, trending, and random meme discovery."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.models.meme import Meme, PaginatedMemeResponse
from app.storage.memory_store import MemoryStore

logger = logging.getLogger(__name__)

router = APIRouter()


def get_memory_store(request: Request) -> MemoryStore:
    """Dependency provider for retrieving the MemoryStore from application state."""
    store = getattr(request.app.state, "memory_store", None)
    if store is None:
        store = MemoryStore()
        request.app.state.memory_store = store
    return store


@router.get(
    "/latest",
    response_model=PaginatedMemeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get newest memes",
    description="Retrieve newest memes sorted by publication date descending with pagination and filtering.",
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
        description="Filter by source platform (reddit, knowyourmeme) or community (r/memes, dankmemes)",
    ),
    nsfw: bool = Query(default=False, description="Include NSFW content if true (default false)"),
    time_window: Optional[str] = Query(
        default=None,
        description="Optional time window filter (e.g., 1h, 6h, 24h, 7d, all)",
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
    description="Retrieve trending memes ranked by virality/velocity score with gravity decay, pagination, and filtering.",
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
        description="Filter by source platform (reddit, knowyourmeme) or community (r/memes, dankmemes)",
    ),
    nsfw: bool = Query(default=False, description="Include NSFW content if true (default false)"),
    time_window: Optional[str] = Query(
        default=None,
        description="Optional time window filter (e.g., 1h, 6h, 24h, 7d, all)",
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
    "/random",
    response_model=Meme,
    status_code=status.HTTP_200_OK,
    summary="Get a random meme",
    description="Fetch a single pseudo-random meme matching optional source and NSFW filters.",
    responses={
        200: {"description": "Random meme payload"},
        404: {"description": "No memes found matching the specified criteria"},
        422: {"description": "Validation error on query parameters"},
    },
)
async def get_random_meme(
    source: Optional[str] = Query(
        default=None,
        description="Optional source filter (reddit, knowyourmeme, dankmemes, etc.)",
    ),
    nsfw: bool = Query(default=False, description="Include NSFW content if true (default false)"),
    store: MemoryStore = Depends(get_memory_store),
) -> Meme:
    """Return a single random meme matching specified criteria."""
    meme = store.get_random(source=source, nsfw=nsfw)
    if meme is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No memes found matching the specified criteria",
        )
    return Meme.from_normalized(meme)
