"""API v1 central router aggregating all v1 endpoint routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.memes import router as memes_router
from app.api.v1.sources import router as sources_router

api_v1_router = APIRouter()

api_v1_router.include_router(memes_router, prefix="/memes", tags=["memes"])
api_v1_router.include_router(sources_router)
