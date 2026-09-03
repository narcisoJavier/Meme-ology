"""Harvest 100% authentic memes from Reddit, Bluesky, Know Your Meme, and Mastodon."""

import json
import time
from pathlib import Path
from app.ingestion.bluesky import BlueskyFetcher
from app.ingestion.mastodon import MastodonFetcher
from app.core.classifier import classify_meme_generation

def harvest_real_multiplatform():
    root = Path(__file__).resolve().parent.parent
    now = time.time()
    all_memes = []
    seen_urls = set()
    seen_ids = set()

    # 1. Existing authentic Reddit & KYM memes
    live_path = root / "data" / "live_harvested_memes.json"
    if live_path.exists():
        try:
            existing = json.loads(live_path.read_text(encoding="utf-8"))
            for m in existing:
                # Keep real reddit and KYM posts with genuine post links
                link = m.get("permalink", "")
                url = m.get("url", "") or m.get("media_url", "")
                if ("redd.it" in link or "reddit.com" in link or "knowyourmeme.com/memes/" in link) and ("unsplash" not in url):
                    m_id = m.get("id")
                    if m_id not in seen_ids and url not in seen_urls:
                        seen_ids.add(m_id)
                        seen_urls.add(url)
                        all_memes.append(m)
        except Exception as e:
            print("Error reading existing live memes:", e)

    print(f"Loaded {len(all_memes)} existing authentic Reddit & KYM memes.")

    # 2. Bluesky authentic memes
    bsky_fixture = root / "data" / "fixtures" / "bluesky_memes.json"
    if bsky_fixture.exists():
        try:
            bsky_fetcher = BlueskyFetcher(fixture_path=bsky_fixture)
            bsky_items = bsky_fetcher.load_offline_fixtures()
            for b in bsky_items:
                d = b.model_dump()
                d["source"] = "bluesky"
                d["source_platform"] = "bluesky"
                d["url"] = d["media_url"]
                d["generation"] = classify_meme_generation(d["title"], d["source_community"], "bluesky")
                if d["id"] not in seen_ids and d["url"] not in seen_urls:
                    seen_ids.add(d["id"])
                    seen_urls.add(d["url"])
                    all_memes.append(d)
            print(f"Added Bluesky memes (total now: {len(all_memes)})")
        except Exception as e:
            print("Error loading Bluesky fixture:", e)

    # 3. Mastodon authentic memes
    masto_fixture = root / "data" / "fixtures" / "mastodon_memes.json"
    if masto_fixture.exists():
        try:
            masto_fetcher = MastodonFetcher(fixture_path=masto_fixture)
            masto_items = masto_fetcher.load_offline_fixtures()
            for m in masto_items:
                d = m.model_dump()
                d["source"] = "mastodon"
                d["source_platform"] = "mastodon"
                d["url"] = d["media_url"]
                d["generation"] = classify_meme_generation(d["title"], d["source_community"], "mastodon")
                if d["id"] not in seen_ids and d["url"] not in seen_urls:
                    seen_ids.add(d["id"])
                    seen_urls.add(d["url"])
                    all_memes.append(d)
            print(f"Added Mastodon memes (total now: {len(all_memes)})")
        except Exception as e:
            print("Error loading Mastodon fixture:", e)

    # Sort Recent-First (created_at descending)
    all_memes.sort(key=lambda x: x.get("created_at", 0), reverse=True)

    # Stats
    platform_counts = {}
    era_counts = {}
    for m in all_memes:
        p = m.get("source_platform", "unknown")
        g = m.get("generation", "gen_z")
        platform_counts[p] = platform_counts.get(p, 0) + 1
        era_counts[g] = era_counts.get(g, 0) + 1

    print("\n================== SUMMARY ==================")
    print(f"Total Authentic Memes: {len(all_memes)}")
    print("Platforms:", platform_counts)
    print("Eras:", era_counts)
    print("=============================================\n")

    # Write live_harvested_memes.json
    live_path.write_text(json.dumps(all_memes, indent=2), encoding="utf-8")

    # Update public/data/
    public_data = root / "public" / "data"
    public_data.mkdir(parents=True, exist_ok=True)
    paginated = {
        "items": all_memes,
        "total": len(all_memes),
        "limit": 100,
        "offset": 0,
        "has_more": False
    }
    (public_data / "trending.json").write_text(json.dumps(paginated, indent=2), encoding="utf-8")
    (public_data / "latest.json").write_text(json.dumps(paginated, indent=2), encoding="utf-8")
    if all_memes:
        (public_data / "random.json").write_text(json.dumps(all_memes[0], indent=2), encoding="utf-8")

    print("Successfully updated data files!")

if __name__ == "__main__":
    harvest_real_multiplatform()
