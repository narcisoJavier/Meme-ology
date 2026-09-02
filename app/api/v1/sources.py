"""Sources and system health status endpoints."""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, Request, status

from app.models.source import HealthResponse, SourceStatus
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
    "/sources",
    response_model=List[SourceStatus],
    status_code=status.HTTP_200_OK,
    summary="List ingestion sources",
    description="Retrieve status, cached item counts, latency, and error metrics for all ingestion sources.",
    tags=["sources"],
    responses={
        200: {"description": "List of tracked data sources and their operational status"},
    },
)
async def get_sources(
    store: MemoryStore = Depends(get_memory_store),
) -> List[SourceStatus]:
    """Return status list for all configured Reddit and Know Your Meme ingestion sources."""
    return store.get_sources_status()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Service health check",
    description="Retrieve service operational status, uptime, cached meme counts, and healthy source counts.",
    tags=["health"],
    responses={
        200: {"description": "Service health metrics"},
    },
)
async def get_api_health(
    store: MemoryStore = Depends(get_memory_store),
) -> HealthResponse:
    """Return aggregated system and source health metrics."""
    return store.get_health_status()
