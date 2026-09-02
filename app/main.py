"""FastAPI application entrypoint, lifespan manager, and route configuration."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from app.api.v1.memes import get_memory_store
from app.api.v1.router import api_v1_router
from app.config import get_settings
from app.ingestion.worker import MemePollingWorker
from app.models.source import HealthResponse
from app.storage.memory_store import MemoryStore
from app.storage.sqlite_store import SqliteStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("meme_tracker_api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup, database initialization, cache hydration, and poller lifecycle."""
    settings = get_settings()
    logger.info("Starting up %s (env=%s)...", settings.APP_NAME, settings.APP_ENV)

    # 1. Initialize persistent SQLite database
    sqlite_store = getattr(app.state, "sqlite_store", None)
    if sqlite_store is None:
        sqlite_store = SqliteStore(database_path=settings.DB_PATH)
        app.state.sqlite_store = sqlite_store
    await sqlite_store.initialize()

    # 2. Initialize in-memory cache and hydrate from DB
    memory_store = getattr(app.state, "memory_store", None)
    if memory_store is None:
        memory_store = MemoryStore()
        app.state.memory_store = memory_store
    await memory_store.hydrate_from_db(sqlite_store)

    # 3. Initialize and start background polling worker
    poller = getattr(app.state, "poller", None)
    if poller is None:
        poller = MemePollingWorker(
            memory_store=memory_store,
            sqlite_store=sqlite_store,
            poll_interval_seconds=settings.POLL_INTERVAL_SECONDS,
        )
        app.state.poller = poller
    await poller.start()

    logger.info("Application startup complete. Cache contains %d items.", memory_store.count())

    yield

    # 4. Graceful shutdown
    logger.info("Shutting down %s...", settings.APP_NAME)
    if hasattr(app.state, "poller") and app.state.poller:
        await app.state.poller.stop()
    if hasattr(app.state, "sqlite_store") and app.state.sqlite_store:
        await app.state.sqlite_store.close()
    logger.info("Application shutdown complete.")


tags_metadata = [
    {
        "name": "memes",
        "description": "Endpoints for querying newest, trending, and random memes across Reddit and Know Your Meme.",
    },
    {
        "name": "sources",
        "description": "Endpoints for monitoring active ingestion sources, health status, and sync telemetry.",
    },
    {
        "name": "health",
        "description": "System operational health checks, uptime metrics, and cache statistics.",
    },
]


def create_app() -> FastAPI:
    """Application factory building configured FastAPI instance."""
    settings = get_settings()

    application = FastAPI(
        title=settings.APP_NAME,
        description=(
            "High-performance Python FastAPI service and background aggregation engine that continuously discovers, "
            "curates, ranks, and serves the newest and trending memes from popular internet sources (Reddit and Know Your Meme)."
        ),
        version="1.0.0",
        openapi_tags=tags_metadata,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Cross-Origin Resource Sharing (CORS)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API v1 router
    application.include_router(api_v1_router, prefix="/api/v1")

    # Root health endpoint
    @application.get(
        "/health",
        response_model=HealthResponse,
        status_code=status.HTTP_200_OK,
        summary="Service health check",
        description="System health check returning operational status, uptime, cached memes, and healthy source counts.",
        tags=["health"],
        responses={
            200: {"description": "Service health metrics"},
        },
    )
    async def root_health(store: MemoryStore = Depends(get_memory_store)) -> HealthResponse:
        """Return operational health status and cached metrics."""
        return store.get_health_status()

    # Root index endpoint
    @application.get(
        "/",
        status_code=status.HTTP_200_OK,
        summary="Root index",
        description="Service overview and documentation links, or web UI for browsers.",
        tags=["health"],
    )
    async def root_index(request: Request) -> Response:
        """Return service identity and documentation link, or web UI for browsers."""
        accept = request.headers.get("accept", "")
        if "text/html" in accept and "application/json" not in accept:
            index_path = Path(__file__).parent / "static" / "index.html"
            if index_path.exists():
                return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
        return JSONResponse({
            "name": settings.APP_NAME,
            "version": "1.0.0",
            "docs_url": "/docs",
            "openapi_url": "/openapi.json",
            "health_url": "/health",
        })

    # Web portal endpoint
    @application.get(
        "/web",
        response_class=HTMLResponse,
        status_code=status.HTTP_200_OK,
        summary="Web Explorer & Documentation Portal",
        description="Interactive Meme Explorer and API documentation portal.",
        tags=["memes"],
    )
    async def web_portal() -> HTMLResponse:
        """Serve the Meme-ology web dashboard and interactive documentation."""
        index_path = Path(__file__).parent / "static" / "index.html"
        if index_path.exists():
            return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>Meme-ology</h1><p>Visit <a href='/docs'>/docs</a> for API documentation.</p>")

    return application


app = create_app()
