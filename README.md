# Meme Tracker API

High-performance Python FastAPI service and background aggregation engine that continuously discovers, curates, ranks, deduplicates, and serves the newest and trending memes from popular internet communities (Reddit and Know Your Meme).

---

## Architecture Overview

```
                          ┌──────────────────────────────────────────────┐
                          │             FastAPI Web Server               │
                          │   - GET /api/v1/memes/latest                 │
                          │   - GET /api/v1/memes/trending               │
                          │   - GET /api/v1/memes/random                 │
                          │   - GET /api/v1/sources                      │
                          │   - GET /health                              │
                          │   - Interactive Swagger UI at /docs          │
                          └──────────────────────┬───────────────────────┘
                                                 │ Reads (< 1ms latency)
                                                 ▼
                          ┌──────────────────────────────────────────────┐
                          │          In-Memory Hot Store Cache           │
                          │   - Pre-sorted Latest & Trending Indices     │
                          │   - SFW / NSFW Partitioned Lookup Indices    │
                          │   - Source & Community Indexed Token Maps    │
                          │   - Atomic Upsert & Engagement Merging       │
                          └──────────────────────▲───────────────────────┘
                                                 │ Async Sync / Hydration
                                                 ▼
                          ┌──────────────────────────────────────────────┐
                          │       Async Background Polling Worker        │
                          │         (FastAPI Lifespan Manager)           │
                          └───────┬──────────────┬──────────────┬────────┘
                                  │              │              │
                        ┌─────────▼────────┐ ┌───▼────┐ ┌───────▼────────┐
                        │ Multi-Source     │ │ Dedupl.│ │ SQLite Storage │
                        │ Ingestion Engine │ │ Engine │ │ Persistence    │
                        │ - Reddit JSON    │ │ & Hash │ │ (WAL Mode)     │
                        │ - KYM RSS/XML    │ │ Ranking│ └────────────────┘
                        └──────────────────┘ └────────┘
```

---

## Core Capabilities & Features

1. **Multi-Source Ingestion Engine**:
   - **Reddit**: Asynchronous fetcher querying public JSON endpoints for `r/memes`, `r/dankmemes`, `r/me_irl`, `r/wholesomememes`.
   - **Know Your Meme**: Asynchronous parser supporting RSS 2.0 feeds (`memes.rss`, `news.rss`) and trending feeds with robust RFC 822 date conversion.
   - **User-Agent Pool & Rate Limiter**: Domain-isolated polite rate limiter with User-Agent header rotation and exponential backoff on HTTP 429/403.
   - **Media Resolution Hierarchy**: Extracts direct images, Reddit video (`v.redd.it`) MP4 streams, multi-image galleries, Imgur direct image links, and unescapes HTML entities.
   - **Offline Fixture Fallback**: Bundled static JSON/XML fixtures in `data/fixtures/` allowing isolated testing and network outage recovery.

2. **Deduplication & Virality Ranking**:
   - **Canonical Normalization**: URL lowercase normalization, query parameter stripping (UTM, ref, share tracking), and hosting domain alias resolution.
   - **Deterministic SHA-256 Hashing**: Content hashing based on canonical media URL and cleaned title to prevent cross-posted duplicate memes.
   - **Engagement Merging**: Merges engagement metrics (taking highest score and latest comment counts) across duplicate submissions.
   - **Gravity Virality Scoring**:
     $$\text{Trending Score} = \frac{\max(0, \text{score}) + \max(0, \text{comments}) \times 1.5}{(\text{age\_in\_hours} + 2.0)^{1.5}}$$

3. **Dual-Layer Storage Subsystem**:
   - **In-Memory Cache**: Thread-safe lock-protected hot store with indexed slices for latest and trending memes providing $<1\text{ms}$ query latency.
   - **SQLite Persistence**: Asynchronous SQLite repository using `aiosqlite` configured with Write-Ahead Logging (`PRAGMA journal_mode=WAL;`) for crash-resilient persistence and fast restarts.

4. **REST API & OpenAPI 3.0 Documentation**:
   - Fully-typed Pydantic v2 domain schemas.
   - Interactive Swagger documentation at `/docs` and ReDoc at `/redoc`.
   - Comprehensive query validation, offset/limit pagination, time window filters (`1h`, `6h`, `24h`, `7d`), NSFW filtering, and source filtering.

---

## Quickstart & Installation

### Prerequisites
- Python 3.10+
- [`uv`](https://github.com/astral-sh/uv) (recommended) or standard `pip`

### 1. Clone & Setup Virtual Environment

```bash
cd d:/API/meme_tracker_api

# Using uv (fastest):
uv venv .venv
# Activate on Windows:
.venv\Scripts\activate
# Activate on Linux/macOS:
source .venv/bin/activate

# Install dependencies:
uv pip install -r requirements-dev.txt
```

### 2. Environment Configuration

Copy `.env.example` to `.env` and adjust configuration if needed:

```bash
cp .env.example .env
```

### 3. Run the Development Server

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The application will start on `http://127.0.0.1:8000`.
- Interactive Swagger UI: `http://127.0.0.1:8000/docs`
- Interactive ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI Specification: `http://127.0.0.1:8000/openapi.json`
- Health Check: `http://127.0.0.1:8000/health`

---

## REST API Reference

### 1. `GET /api/v1/memes/latest`
Retrieve newest memes sorted chronologically descending (`created_at` DESC).

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | `20` | Items per page ($1 \le \text{limit} \le 100$) |
| `offset` | integer | `0` | Offset index for pagination ($\ge 0$) |
| `source` | string | `None` | Filter by platform (`reddit`, `knowyourmeme`) or community (`r/memes`, `dankmemes`, `confirmed`) |
| `nsfw` | boolean | `false` | Include NSFW items if `true` |
| `time_window` | string | `None` | Restrict by age (`1h`, `6h`, `24h`, `7d`) |

**Sample Response (HTTP 200):**
```json
{
  "items": [
    {
      "id": "reddit_memes_1d8xyz",
      "title": "When code passes all 400+ unit tests on first run",
      "url": "https://i.redd.it/viral_pass.png",
      "media_url": "https://i.redd.it/viral_pass.png",
      "media_type": "image",
      "source": "reddit",
      "source_platform": "reddit",
      "source_community": "r/memes",
      "permalink": "https://reddit.com/r/memes/comments/1d8xyz/",
      "author": "dev_guru",
      "score": 4200,
      "num_comments": 128,
      "created_at": 1725300000.0,
      "is_nsfw": false,
      "domain": "i.redd.it",
      "content_hash": "a1b2c3d4e5f67890...",
      "trending_score": 142.85
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0,
  "has_more": false
}
```

---

### 2. `GET /api/v1/memes/trending`
Retrieve viral and high-engagement memes ranked by decaying velocity (`trending_score` DESC).

**Query Parameters:** Same as `/latest` (`limit`, `offset`, `source`, `nsfw`, `time_window`).

**Sample Response (HTTP 200):**
```json
{
  "items": [
    {
      "id": "reddit_dankmemes_2a9abc",
      "title": "Fast breaking viral meme",
      "url": "https://i.redd.it/fresh_viral.jpg",
      "media_url": "https://i.redd.it/fresh_viral.jpg",
      "media_type": "image",
      "source": "reddit",
      "source_platform": "reddit",
      "source_community": "r/dankmemes",
      "permalink": "https://reddit.com/r/dankmemes/comments/2a9abc/",
      "author": "meme_king",
      "score": 18500,
      "num_comments": 450,
      "created_at": 1725301800.0,
      "is_nsfw": false,
      "domain": "i.redd.it",
      "content_hash": "e9f8d7c6b5a43210...",
      "trending_score": 584.21
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0,
  "has_more": false
}
```

---

### 3. `GET /api/v1/memes/random`
Fetch a single pseudo-random meme from the cached store matching optional filter criteria.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | string | `None` | Filter by platform or subreddit |
| `nsfw` | boolean | `false` | Include NSFW items if `true` |

**Sample Response (HTTP 200):**
```json
{
  "id": "kym_Entry-57336",
  "title": "Distracted Boyfriend",
  "url": "https://i.kym-cdn.com/photos/images/original/001/292/377/206.jpg",
  "media_url": "https://i.kym-cdn.com/photos/images/original/001/292/377/206.jpg",
  "media_type": "image",
  "source": "knowyourmeme",
  "source_platform": "knowyourmeme",
  "source_community": "confirmed",
  "permalink": "https://knowyourmeme.com/memes/distracted-boyfriend",
  "author": "Know Your Meme",
  "score": 500,
  "num_comments": 45,
  "created_at": 1725200000.0,
  "is_nsfw": false,
  "domain": "i.kym-cdn.com",
  "content_hash": "b2c3d4e5f6a1...",
  "trending_score": 18.25
}
```

---

### 4. `GET /api/v1/sources`
List all tracked upstream ingestion feeds, operational status, item counts, and telemetry.

**Sample Response (HTTP 200):**
```json
[
  {
    "name": "reddit:r/memes",
    "platform": "reddit",
    "community": "r/memes",
    "status": "ok",
    "item_count": 25,
    "last_synced_at": 1725302400.0,
    "last_error": null,
    "latency_ms": 142.5
  },
  {
    "name": "knowyourmeme:memes",
    "platform": "knowyourmeme",
    "community": "memes",
    "status": "ok",
    "item_count": 20,
    "last_synced_at": 1725302400.0,
    "last_error": null,
    "latency_ms": 210.8
  }
]
```

---

### 5. `GET /health`
System operational health check.

**Sample Response (HTTP 200):**
```json
{
  "status": "ok",
  "uptime_seconds": 1845.2,
  "total_memes_cached": 150,
  "sources_healthy": 6,
  "sources_total": 6,
  "timestamp": 1725302400.0
}
```

---

## Configuration Reference

Configuration is managed via environment variables or `.env`:

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APP_NAME` | string | `Meme Tracker API` | Application title in OpenAPI docs |
| `APP_ENV` | string | `development` | Deployment environment (`development`, `test`, `production`) |
| `DEBUG` | boolean | `true` | Enable debug logs |
| `HOST` | string | `0.0.0.0` | Server bind host |
| `PORT` | integer | `8000` | Server bind port |
| `POLL_INTERVAL_SECONDS` | integer | `60` | Background ingestion polling cycle interval in seconds |
| `OFFLINE_MODE` | boolean | `false` | Enable offline mode using bundled static JSON/XML fixtures |
| `REQUEST_TIMEOUT_SECONDS`| float | `10.0` | HTTP request timeout for outbound fetchers |
| `MAX_RETRIES` | integer | `3` | Maximum retry attempts for transient errors |
| `REDDIT_SUBREDDITS` | list/str | `["memes", "dankmemes", "me_irl", "wholesomememes"]` | Target subreddits to monitor |
| `KYM_FEED_URLS` | list/str | `["https://knowyourmeme.com/memes.rss", "https://knowyourmeme.com/news.rss"]` | Know Your Meme RSS feed endpoints |
| `DB_PATH` | string | `data/memes.db` | Persistent SQLite database file path |

---

## Automated Test Suite Execution

The repository contains an automated test suite across unit, integration, network resilience, lifecycle, and adversarial hardening categories.

### Run All Tests with Coverage Report

```bash
uv run pytest --cov=app --cov-report=term-missing -v
```

### Test Suite Structure

```
tests/
├── unit/
│   ├── test_parsers.py                       # Unit tests for Reddit and KnowYourMeme parsers
│   ├── test_dedup.py                         # URL canonicalization and SHA-256 content hashing
│   ├── test_ranking.py                       # Gravity virality algorithm unit tests
│   ├── test_storage.py                       # In-memory hot store and SQLite persistence tests
│   ├── test_models.py                        # Pydantic v2 schemas and alias synchronization
│   ├── test_reddit_adversarial.py            # Malformed payloads, galleries, videos, crossposts
│   ├── test_challenger_kym_security.py       # XML bomb prevention, rate limiting, header rotation
│   ├── test_challenger_memory_store.py       # Memory store stress and sub-millisecond benchmarks
│   ├── test_security_and_config.py           # User-Agent rotation, backoff, and config parsing
│   └── test_m4_edge_cases_and_coverage.py    # M4 edge case verification and branch coverage
├── integration/
│   ├── test_api_latest.py                    # GET /api/v1/memes/latest pagination and filters
│   ├── test_api_trending.py                  # GET /api/v1/memes/trending ordering and pagination
│   ├── test_api_random.py                    # GET /api/v1/memes/random retrieval and filters
│   ├── test_api_sources.py                   # GET /api/v1/sources status and metrics
│   ├── test_lifespan.py                      # FastAPI lifespan startup/shutdown and DB hydration
│   ├── test_openapi.py                       # OpenAPI 3.0 schema and Swagger UI /docs
│   ├── test_challenger_api_stress.py         # Concurrent burst requests and pagination sweeps
│   └── test_challenger_m3_lifecycle_openapi.py# Full lifecycle, CORS, and endpoint integration
├── resiliency/
│   ├── test_resilience.py                    # Network disconnects, timeouts, 429 backoff handling
│   ├── test_worker_lifecycle.py              # Background worker start/stop and polling loop
│   ├── test_ingestion_resilience.py          # Outage recovery and fallback fixture loading
│   ├── test_challenger_sqlite_and_worker_stress.py # SQLite concurrency and worker restart stress
│   └── test_tier5_adversarial_hardening.py   # Thread stress, malformed feeds, and boundary tests
└── scenarios/
    └── test_tier4_scenarios.py               # 7 End-to-end real-world discovery journey workflows
```

---

## License

MIT License. Designed and built as a clean, performant meme discovery and tracking engine.
