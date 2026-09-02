"""Vercel Serverless Function Entrypoint for Meme-ology."""

from __future__ import annotations

import os
import sys

# Ensure project root is on PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.main import app
except Exception:
    import traceback
    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse

    app = FastAPI()

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
    async def catch_all(path: str):
        return PlainTextResponse(f"FastAPI Startup Error:\n{traceback.format_exc()}", status_code=500)
