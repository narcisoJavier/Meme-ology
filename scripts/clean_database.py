"""Clean data/memes.db by removing non-meme false positives, merging duplicates, and backfilling location metadata."""

import sqlite3
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to sys.path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from app.core.classifier import is_valid_meme_content
from app.core.location import detect_meme_location
from app.core.dedup import normalize_author_handle, normalize_title, compute_semantic_title_hash, normalize_url


def main():
    db_path = root / "data" / "memes.db"
    if not db_path.exists():
        print("Database does not exist at:", db_path)
        return

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Add language and country_code columns if missing
    columns = [row["name"] for row in cursor.execute("PRAGMA table_info(memes)").fetchall()]
    if "language" not in columns:
        print("Adding column language to memes table...")
        cursor.execute("ALTER TABLE memes ADD COLUMN language TEXT NOT NULL DEFAULT 'en'")
    if "country_code" not in columns:
        print("Adding column country_code to memes table...")
        cursor.execute("ALTER TABLE memes ADD COLUMN country_code TEXT NOT NULL DEFAULT 'GLOBAL'")

    # 2. Fetch all memes
    rows = cursor.execute("SELECT * FROM memes ORDER BY created_at ASC").fetchall()
    print(f"Total rows before cleanup: {len(rows)}")

    # 3. Filter invalid memes (French homographs without meme intent, spam links, obituary hoaxes)
    invalid_ids = []
    for r in rows:
        title = r["title"] or ""
        media_url = r["media_url"] or ""
        if not is_valid_meme_content(title, media_url):
            invalid_ids.append((r["id"], title, media_url))

    print(f"Found {len(invalid_ids)} invalid/spam/homograph memes to remove:")
    for mid, t, u in invalid_ids:
        print(f"  - [{mid}] '{t[:60]}...' | {u[:50]}...")

    if invalid_ids:
        cursor.executemany("DELETE FROM memes WHERE id = ?", [(mid,) for mid, _, _ in invalid_ids])
        conn.commit()

    # 4. Check for duplicates among remaining items
    remaining_rows = cursor.execute("SELECT * FROM memes ORDER BY created_at ASC").fetchall()
    seen_media_urls = {}
    seen_author_titles = {}
    to_delete = set()
    updates = []

    for r in remaining_rows:
        mid = r["id"]
        media_url = r["media_url"] or ""
        clean_url = normalize_url(media_url).lower().strip()
        title = r["title"] or ""
        author = r["author"] or ""
        norm_auth = normalize_author_handle(author)
        clean_t = normalize_title(title)
        title_hash = compute_semantic_title_hash(title) if clean_t else ""

        # Dedup key 1: Canonical media URL
        is_dup = False
        if clean_url:
            if clean_url in seen_media_urls:
                existing_id = seen_media_urls[clean_url]
                print(f"  [Duplicate URL] {mid} is duplicate of {existing_id} ('{title[:40]}')")
                to_delete.add(mid)
                is_dup = True
            else:
                seen_media_urls[clean_url] = mid

        # Dedup key 2: Author + Title
        if not is_dup and norm_auth and norm_auth not in ("unknown", "anonymous") and len(clean_t) >= 6:
            author_key = f"{norm_auth}|{title_hash}"
            if author_key in seen_author_titles:
                existing_id = seen_author_titles[author_key]
                print(f"  [Duplicate Cross-Platform/Bridgy] {mid} is duplicate of {existing_id} ('{title[:40]}' by {norm_auth})")
                to_delete.add(mid)
                is_dup = True
            else:
                seen_author_titles[author_key] = mid

        if not is_dup:
            # Detect location and language
            country, lang = detect_meme_location(
                title=title,
                source_community=r["source_community"] or "",
                source_platform=r["source_platform"] or "",
                author=r["author"] or "",
            )
            updates.append((country, lang, mid))

    if to_delete:
        print(f"Deleting {len(to_delete)} duplicate memes...")
        cursor.executemany("DELETE FROM memes WHERE id = ?", [(mid,) for mid in to_delete])

    if updates:
        print(f"Backfilling location and language for {len(updates)} memes...")
        cursor.executemany("UPDATE memes SET country_code = ?, language = ? WHERE id = ?", updates)

    conn.commit()
    final_count = cursor.execute("SELECT count(*) FROM memes").fetchone()[0]
    print(f"Cleanup complete. Total rows now: {final_count}")
    conn.close()


if __name__ == "__main__":
    main()
