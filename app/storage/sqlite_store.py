"""Async SQLite persistence store using aiosqlite with WAL mode."""

from __future__ import annotations

import logging
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
        self.database_path = database_path or get_settings().DB_PATH
        self._db_path = Path(self.database_path)
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database schema, apply PRAGMAs (WAL mode), and build indices."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self.database_path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
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
                    discovered_at REAL NOT NULL DEFAULT 0.0
                );
                """
            )

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
                )
            )

        async with aiosqlite.connect(self.database_path) as db:
            await db.executemany(
                """
                INSERT INTO memes (
                    id, raw_id, title, media_url, media_type, source_platform,
                    source_community, permalink, author, score, num_comments,
                    created_at, is_nsfw, domain, content_hash, trending_score,
                    discovered_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
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
                    trending_score = excluded.trending_score;
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
        )

    async def load_all_memes(self) -> list[NormalizedMeme]:
        """Load all persisted memes sorted by created_at descending."""
        async with aiosqlite.connect(self.database_path) as db:
            async with db.execute(
                """
                SELECT
                    id, raw_id, title, media_url, media_type, source_platform,
                    source_community, permalink, author, score, num_comments,
                    created_at, is_nsfw, domain, content_hash, trending_score
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
                    created_at, is_nsfw, domain, content_hash, trending_score
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
                    created_at, is_nsfw, domain, content_hash, trending_score
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
