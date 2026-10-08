"""FastAPI application entrypoint, lifespan manager, and route configuration."""

from __future__ import annotations

import logging
import os
import html
import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.memes import get_memory_store
from app.api.v1.router import api_v1_router
from app.config import get_settings
from app.ingestion.worker import MemePollingWorker
from app.ingestion.knowyourmeme import KnowYourMemeFetcher
from app.models.source import HealthResponse
from app.storage.memory_store import MemoryStore
from app.storage.sqlite_store import SqliteStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("meme_tracker_api")


async def _refresh_serverless_snapshot(application: FastAPI, store: MemoryStore) -> None:
    """Refresh the KYM snapshot once per TTL while serving a warm Vercel instance.

    Vercel functions cannot keep a polling daemon alive. This request-driven path
    keeps the source ordering truthful, uses an async lock for concurrent requests,
    and leaves the existing snapshot in place when KYM is unavailable.
    """
    if not os.environ.get("VERCEL"):
        return

    settings = get_settings()
    now = time.time()
    refreshed_at = getattr(application.state, "live_refreshed_at", 0.0)
    if refreshed_at and now - refreshed_at < settings.LIVE_REFRESH_TTL_SECONDS:
        return

    lock = getattr(application.state, "live_refresh_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        application.state.live_refresh_lock = lock

    async with lock:
        refreshed_at = getattr(application.state, "live_refreshed_at", 0.0)
        if refreshed_at and time.time() - refreshed_at < settings.LIVE_REFRESH_TTL_SECONDS:
            return

        fetchers = [
            KnowYourMemeFetcher(
                feed_url=feed_url,
                category="confirmed" if "memes" in feed_url else "news",
            )
            for feed_url in settings.KYM_FEED_URLS
        ]
        try:
            worker = MemePollingWorker(memory_store=store, fetchers=fetchers)
            fetched = await worker.fetch_all_sources()
            live_items = [
                item
                for item in fetched
                if getattr(getattr(item, "data_origin", None), "value", getattr(item, "data_origin", None)) == "live"
            ]
            if live_items:
                store.upsert_memes(live_items)
                application.state.live_refresh_state = "live"
            else:
                application.state.live_refresh_state = "stale"
                logger.warning("KYM refresh returned no live records; serving the existing snapshot.")
        except Exception:
            application.state.live_refresh_state = "stale"
            logger.exception("KYM request-driven refresh failed; serving the existing snapshot.")
        finally:
            application.state.live_refreshed_at = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup, database initialization, cache hydration, and poller lifecycle."""
    settings = get_settings()
    logger.info("Starting up %s (env=%s)...", settings.APP_NAME, settings.APP_ENV)

    # Initialize persistent SQLite database
    sqlite_store = getattr(app.state, "sqlite_store", None)
    if sqlite_store is None:
        sqlite_store = SqliteStore(database_path=settings.DB_PATH)
        app.state.sqlite_store = sqlite_store
    await sqlite_store.initialize()

    # Initialize in-memory cache and hydrate from DB
    memory_store = getattr(app.state, "memory_store", None)
    if memory_store is None:
        memory_store = MemoryStore()
        app.state.memory_store = memory_store
    await memory_store.hydrate_from_db(sqlite_store)

    # Initialize and start background polling worker (skip on Vercel serverless)
    is_vercel = os.environ.get("VERCEL") is not None
    if not is_vercel:
        poller = getattr(app.state, "poller", None)
        if poller is None:
            poller = MemePollingWorker(
                memory_store=memory_store,
                sqlite_store=sqlite_store,
                poll_interval_seconds=settings.POLL_INTERVAL_SECONDS,
            )
            app.state.poller = poller
        await poller.start()
    else:
        logger.info("Running on Vercel serverless: skipping continuous polling daemon.")

    logger.info("Application startup complete. Cache contains %d items.", memory_store.count())

    yield

    # Graceful shutdown
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
        lifespan=None if os.environ.get("VERCEL") else lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def serverless_refresh(request: Request, call_next):
        """Run a bounded KYM refresh before API and explorer requests on Vercel."""
        if os.environ.get("VERCEL") and (
            request.url.path == "/"
            or request.url.path == "/health"
            or request.url.path.startswith("/api/v1/")
            or request.url.path.startswith("/meme/")
        ):
            store = get_memory_store(request)
            await _refresh_serverless_snapshot(application, store)
        return await call_next(request)

    static_dir = Path(__file__).parent / "static"
    application.mount("/static", StaticFiles(directory=static_dir), name="static")

    application.include_router(api_v1_router, prefix="/api/v1")

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

    @application.get(
        "/meme/{meme_id}",
        response_class=HTMLResponse,
        status_code=status.HTTP_200_OK,
        summary="Shareable meme detail page",
        description="Render a source-backed meme detail page with metadata before client hydration.",
        tags=["memes"],
    )
    async def meme_detail_page(
        meme_id: str,
        request: Request,
        store: MemoryStore = Depends(get_memory_store),
    ) -> HTMLResponse:
        """Return the explorer shell with server-rendered share metadata."""
        meme = store.get_by_id(meme_id)
        if meme is None:
            raise HTTPException(status_code=404, detail="Meme record not found")
        index_path = static_dir / "index.html"
        if not index_path.exists():
            raise HTTPException(status_code=500, detail="Explorer shell unavailable")
        document = index_path.read_text(encoding="utf-8")
        title = html.escape(f"{meme.title} | Meme-ology")
        description = html.escape(
            f"Source-backed entry for {meme.title}. Collected from {meme.source_platform} and linked to its original source."
        )
        canonical = html.escape(str(request.base_url).rstrip("/") + f"/meme/{meme_id}")
        metadata = (
            f'<title>{title}</title>'
            f'<meta name="description" content="{description}">'
            f'<link rel="canonical" href="{canonical}">'
            f'<meta property="og:title" content="{title}">'
            f'<meta property="og:description" content="{description}">'
            f'<meta property="og:type" content="article">'
            f'<meta property="og:url" content="{canonical}">'
        )
        document = document.replace("<title>Meme-ology</title>", metadata, 1)
        document = document.replace("<body>", f'<body data-detail-id="{html.escape(meme_id)}">', 1)
        return HTMLResponse(content=document)

    return application


app = create_app()
