"""Vercel Serverless Function Entrypoint for Meme-ology using Mangum adapter."""

from __future__ import annotations

import os
import sys

# Ensure project root is on PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app

try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except Exception:
    handler = app

# Also export app for native ASGI runtimes
app = app
