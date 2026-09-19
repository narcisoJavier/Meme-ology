"""Build the static API dataset from live observations only.

This command deliberately fails closed. It never pads a feed with fixtures and
never invents comments, timestamps, or popularity scores when an upstream does
not provide them.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.ingestion.worker import MemePollingWorker
from app.models.meme import NormalizedMeme
from app.storage.memory_store import MemoryStore

logger = logging.getLogger("live_harvester")


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _is_live(meme: NormalizedMeme) -> bool:
    return (
        _enum_value(getattr(meme, "data_origin", "live")) == "live"
        and "kym_placeholder" not in (meme.media_url or "")
    )


def _is_rankable(meme: NormalizedMeme) -> bool:
    return _enum_value(getattr(meme, "metrics_quality", "observed")) == "observed"


def _serialize(items: Iterable[NormalizedMeme]) -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in items]


def _paginated(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "items": items,
        "total": len(items),
        "limit": len(items),
        "offset": 0,
        "has_more": False,
    }


async def harvest() -> int:
    settings = get_settings()
    if settings.OFFLINE_MODE:
        raise RuntimeError("OFFLINE_MODE is enabled. Refusing to publish fixture data as live data.")

    store = MemoryStore()
    worker = MemePollingWorker(memory_store=store)
    fetched = await worker.fetch_all_sources()
    live_items = [item for item in fetched if _is_live(item)]

    if not live_items:
        raise RuntimeError("No live observations were fetched. Existing output files were left untouched.")

    store.upsert_memes(live_items)
    latest, _ = store.get_latest(limit=1000, offset=0, nsfw=True)
    trending, _ = store.get_trending(limit=1000, offset=0, nsfw=True)
    trending = [item for item in trending if _is_live(item) and _is_rankable(item)]

    if not latest:
        raise RuntimeError("The live observations produced no usable records.")

    public_dir = PROJECT_ROOT / "public" / "data"
    public_dir.mkdir(parents=True, exist_ok=True)
    live_path = PROJECT_ROOT / "data" / "live_harvested_memes.json"

    latest_json = _serialize(latest)
    trending_json = _serialize(trending)
    live_json = _serialize(latest)

    live_path.write_text(json.dumps(live_json, indent=2), encoding="utf-8")
    (public_dir / "latest.json").write_text(
        json.dumps(_paginated(latest_json), indent=2), encoding="utf-8"
    )
    (public_dir / "trending.json").write_text(
        json.dumps(_paginated(trending_json), indent=2), encoding="utf-8"
    )
    (public_dir / "random.json").write_text(
        json.dumps(trending_json[0] if trending_json else latest_json[0], indent=2),
        encoding="utf-8",
    )

    sources = [status.model_dump(mode="json") for status in store.get_sources_status()]
    (public_dir / "sources.json").write_text(
        json.dumps({"sources": sources, "total_sources": len(sources)}, indent=2),
        encoding="utf-8",
    )
    (public_dir / "health.json").write_text(
        json.dumps(
            {
                "status": "ok",
                "app_name": settings.APP_NAME,
                "total_memes": len(latest_json),
                "total_memes_cached": len(latest_json),
                "healthy_sources": sum(1 for source in sources if source.get("status") == "ok"),
                "total_sources": len(sources),
                "generated_at": time.time(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    platform_counts: dict[str, int] = {}
    for item in latest:
        platform = _enum_value(item.source_platform)
        platform_counts[platform] = platform_counts.get(platform, 0) + 1

    logger.info(
        "Published %d live observations, %d rankable trending records, platforms=%s",
        len(latest),
        len(trending),
        platform_counts,
    )
    return len(latest)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    try:
        count = asyncio.run(harvest())
    except Exception as exc:
        logger.error("Live harvest failed: %s", exc)
        raise SystemExit(1) from exc
    logger.info("Done. %d records published.", count)


if __name__ == "__main__":
    main()
