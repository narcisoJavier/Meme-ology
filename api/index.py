"""Vercel Serverless Function Entrypoint for Meme-ology.

Exports the FastAPI ASGI application instance for zero-config serverless deployment.
"""

from __future__ import annotations

import os
import sys

# Ensure project root is on PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app

# Export for Vercel Python serverless runtime
handler = app
