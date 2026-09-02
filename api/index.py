"""Vercel Serverless Function Entrypoint for Meme-ology."""

from __future__ import annotations

import os
import sys
import traceback

# Ensure project root is on PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.main import app
    handler = app
except Exception as e:
    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse
    err_app = FastAPI()
    err_msg = traceback.format_exc()

    @err_app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
    async def catch_all(path: str):
        return PlainTextResponse(f"Vercel Startup Exception:\n{err_msg}", status_code=500)

    app = err_app
    handler = err_app
