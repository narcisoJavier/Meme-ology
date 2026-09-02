"""Vercel Serverless Function Entrypoint for Meme-ology."""

from __future__ import annotations

import os
import sys

# Ensure project root is on PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app

# Export native ASGI app for Vercel Python runtime
app = app
