"""Async SQLite persistence store using aiosqlite with WAL mode."""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Optional, Sequence

import aiosqlite

from app.config import get_settings
from app.models.meme import MediaType, NormalizedMeme, SourcePlatform

logger = logging.getLogger(__name__)


class SqliteStore:
    """Async SQLite repository for persistent meme storage."""

    def __init__(self, database_path: Optional[str] = None) -> None:
        if os.environ.get("VERCEL"):
            self.database_path = "/tmp/memes.db"
        else:
            self.database_path = database_path or get_settings().DB_PATH
        self._db_path = Path(self.database_path)
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database schema, apply PRAGMAs (WAL mode), and build indices."""
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as err:
            logger.warning("Could not create db directory %s: %s", self._db_path.parent, err)

        is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
        async with aiosqlite.connect(self.database_path) as db:
            if not is_serverless:
                await db.execute("PRAGMA journal_mode=WAL;")
            else:
                await db.execute("PRAGMA journal_mode=MEMORY;")
            await db.execute("PRAGMA synchronous=NORMAL;")
            await db.execute("PRAGMA busy_timeout=5000;")

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS memes (
                    id TEXT PRIMARY KEY,
                    raw_id TEXT,
                    title TEXT NOT NULL,
                    media_url TEXT NOT NULL,
                    media_type TEXT NOT NULL DEFAULT 'image',
                    source_platform TEXT NOT NULL,
                    source_community TEXT NOT NULL,
                    permalink TEXT,
                    author TEXT,
                    score INTEGER NOT NULL DEFAULT 0,
                    num_comments INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    is_nsfw INTEGER NOT NULL DEFAULT 0,
                    domain TEXT,
                    content_hash TEXT NOT NULL,
                    trending_score REAL NOT NULL DEFAULT 0.0,
                    discovered_at REAL NOT NULL DEFAULT 0.0,
                    language TEXT DEFAULT 'en',
                    country_code TEXT DEFAULT 'GLOBAL',
                    data_origin TEXT DEFAULT 'live',
                    metrics_quality TEXT DEFAULT 'observed',
                    observed_at REAL
                );
                """
            )

            # Migration for existing tables without language/country_code
            try:
                await db.execute("ALTER TABLE memes ADD COLUMN language TEXT DEFAULT 'en';")
            except Exception:
                pass
            try:
                await db.execute("ALTER TABLE memes ADD COLUMN country_code TEXT DEFAULT 'GLOBAL';")
            except Exception:
                pass
            try:
                # Existing rows predate provenance tracking, so treat them as a
                # seed snapshot until a fresh upstream observation replaces them.
                await db.execute("ALTER TABLE memes ADD COLUMN data_origin TEXT DEFAULT 'fixture';")
            except Exception:
                pass
            try:
                await db.execute("ALTER TABLE memes ADD COLUMN metrics_quality TEXT DEFAULT 'unknown';")
            except Exception:
                pass
            try:
                await db.execute("ALTER TABLE memes ADD COLUMN observed_at REAL;")
            except Exception:
                pass

            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_memes_created_at ON memes(created_at DESC);"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_memes_trending_score ON memes(trending_score DESC);"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_memes_content_hash ON memes(content_hash);"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_memes_source_platform ON memes(source_platform);"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_memes_source_community ON memes(source_community);"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_memes_is_nsfw ON memes(is_nsfw);"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_memes_language ON memes(language);"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_memes_country_code ON memes(country_code);"
            )

            await db.commit()

        self._initialized = True
        logger.info("SqliteStore initialized at %s with WAL mode enabled.", self.database_path)

    async def save_memes(self, memes: Sequence[NormalizedMeme]) -> int:
        """Upsert a batch of normalized memes into SQLite.
        
        Merges engagement metrics (score, num_comments) and preserves earliest created_at.
        """
        if not memes:
            return 0

        now = time.time()
        rows = []
        for m in memes:
            media_type_str = m.media_type.value if isinstance(m.media_type, MediaType) else str(m.media_type)
            source_platform_str = (
                m.source_platform.value
                if isinstance(m.source_platform, SourcePlatform)
                else str(m.source_platform)
            )
            lang = getattr(m, "language", "en") or "en"
            country = getattr(m, "country_code", "GLOBAL") or "GLOBAL"
            data_origin = getattr(m, "data_origin", "live")
            data_origin = data_origin.value if hasattr(data_origin, "value") else str(data_origin)
            metrics_quality = getattr(m, "metrics_quality", "observed")
            metrics_quality = metrics_quality.value if hasattr(metrics_quality, "value") else str(metrics_quality)
            observed_at = getattr(m, "observed_at", None)

            rows.append(
                (
                    m.id,
                    m.raw_id or "",
                    m.title,
                    m.media_url,
                    media_type_str,
                    source_platform_str,
                    m.source_community,
                    m.permalink,
                    m.author,
                    m.score,
                    m.num_comments,
                    m.created_at,
                    1 if m.is_nsfw else 0,
                    m.domain,
                    m.content_hash or "",
                    m.trending_score,
                    now,
                    lang,
                    country,
                    data_origin,
                    metrics_quality,
                    observed_at,
                )
            )

        async with aiosqlite.connect(self.database_path) as db:
            await db.executemany(
                """
                INSERT INTO memes (
                    id, raw_id, title, media_url, media_type, source_platform,
                    source_community, permalink, author, score, num_comments,
                    created_at, is_nsfw, domain, content_hash, trending_score,
                    discovered_at, language, country_code, data_origin,
                    metrics_quality, observed_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    media_url = excluded.media_url,
                    media_type = excluded.media_type,
                    source_platform = excluded.source_platform,
                    source_community = excluded.source_community,
                    permalink = excluded.permalink,
                    author = excluded.author,
                    score = MAX(memes.score, excluded.score),
                    num_comments = MAX(memes.num_comments, excluded.num_comments),
                    created_at = MIN(memes.created_at, excluded.created_at),
                    is_nsfw = excluded.is_nsfw,
                    domain = excluded.domain,
                    content_hash = excluded.content_hash,
                    trending_score = excluded.trending_score,
                    language = excluded.language,
                    country_code = excluded.country_code,
                    data_origin = excluded.data_origin,
                    metrics_quality = excluded.metrics_quality,
                    observed_at = excluded.observed_at;
                """,
                rows,
            )
            await db.commit()

        return len(rows)

    def _row_to_meme(self, row: sqlite3.Row | tuple) -> NormalizedMeme:
        """Convert a database row into NormalizedMeme instance."""
        (
            id_,
            raw_id,
            title,
            media_url,
            media_type,
            source_platform,
            source_community,
            permalink,
            author,
            score,
            num_comments,
            created_at,
            is_nsfw,
            domain,
            content_hash,
            trending_score,
        ) = row[:16]

        lang = row[17] if len(row) > 17 and row[17] else "en"
        country = row[18] if len(row) > 18 and row[18] else "GLOBAL"
        data_origin = row[19] if len(row) > 19 and row[19] else "live"
        metrics_quality = row[20] if len(row) > 20 and row[20] else "observed"
        observed_at = row[21] if len(row) > 21 else None

        try:
            m_type = MediaType(media_type)
        except ValueError:
            m_type = MediaType.IMAGE

        try:
            s_plat = SourcePlatform(source_platform)
        except ValueError:
            s_plat = source_platform

        return NormalizedMeme(
            id=id_,
            raw_id=raw_id or None,
            title=title or "",
            media_url=media_url,
            media_type=m_type,
            source_platform=s_plat,
            source_community=source_community or "",
            permalink=permalink or "",
            author=author or "unknown",
            score=int(score or 0),
            num_comments=int(num_comments or 0),
            created_at=float(created_at or 0.0),
            is_nsfw=bool(is_nsfw),
            domain=domain or "",
            content_hash=content_hash or "",
            trending_score=float(trending_score or 0.0),
            language=lang,
            country_code=country,
            data_origin=data_origin,
            metrics_quality=metrics_quality,
            observed_at=observed_at,
        )

    async def load_all_memes(self) -> list[NormalizedMeme]:
        """Load all persisted memes sorted by created_at descending."""
        async with aiosqlite.connect(self.database_path) as db:
            async with db.execute(
                """
                SELECT
                    id, raw_id, title, media_url, media_type, source_platform,
                    source_community, permalink, author, score, num_comments,
                    created_at, is_nsfw, domain, content_hash, trending_score,
                    discovered_at, language, country_code, data_origin,
                    metrics_quality, observed_at
                FROM memes
                ORDER BY created_at DESC;
                """
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_meme(r) for r in rows]

    async def get_meme_by_id(self, meme_id: str) -> Optional[NormalizedMeme]:
        """Retrieve single meme by its unique primary ID."""
        async with aiosqlite.connect(self.database_path) as db:
            async with db.execute(
                """
                SELECT
                    id, raw_id, title, media_url, media_type, source_platform,
                    source_community, permalink, author, score, num_comments,
                    created_at, is_nsfw, domain, content_hash, trending_score,
                    discovered_at, language, country_code, data_origin,
                    metrics_quality, observed_at
                FROM memes
                WHERE id = ?;
                """,
                (meme_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_meme(row)
                return None

    async def get_meme_by_content_hash(self, content_hash: str) -> Optional[NormalizedMeme]:
        """Retrieve single meme by its deduplication content hash."""
        async with aiosqlite.connect(self.database_path) as db:
            async with db.execute(
                """
                SELECT
                    id, raw_id, title, media_url, media_type, source_platform,
                    source_community, permalink, author, score, num_comments,
                    created_at, is_nsfw, domain, content_hash, trending_score,
                    discovered_at, language, country_code, data_origin,
                    metrics_quality, observed_at
                FROM memes
                WHERE content_hash = ?
                ORDER BY created_at DESC
                LIMIT 1;
                """,
                (content_hash,),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_meme(row)
                return None

    async def count(self) -> int:
        """Return total count of persisted memes in SQLite."""
        async with aiosqlite.connect(self.database_path) as db:
            async with db.execute("SELECT COUNT(*) FROM memes;") as cursor:
                row = await cursor.fetchone()
                return int(row[0]) if row else 0

    async def close(self) -> None:
        """Close any open connections / resources."""
        pass
