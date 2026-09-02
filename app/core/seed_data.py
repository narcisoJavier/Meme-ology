"""Curated generational meme catalog representing internet culture eras."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List
from app.models.meme import NormalizedMeme

_LIVE_HARVEST_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "live_harvested_memes.json"

if _LIVE_HARVEST_PATH.exists():
    try:
        INITIAL_GENERATIONAL_MEMES = json.loads(_LIVE_HARVEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        INITIAL_GENERATIONAL_MEMES = []
else:
    INITIAL_GENERATIONAL_MEMES = []


def get_initial_generational_memes() -> List[NormalizedMeme]:
    """Return normalized instances of the curated generational catalog."""
    return [NormalizedMeme(**item) for item in INITIAL_GENERATIONAL_MEMES]
