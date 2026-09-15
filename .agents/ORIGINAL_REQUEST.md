# Original User Request

## 2026-09-02T13:40:46Z

Build a high-performance Python FastAPI service and background aggregation engine that continuously discovers, curates, ranks, and serves the newest and trending memes from popular internet sources (Reddit meme communities and Know Your Meme trending feeds).

Working directory: d:/API/meme_tracker_api
Integrity mode: development

## Requirements

### R1. Multi-Source Meme Ingestion Engine
Build an asynchronous ingestion module that fetches memes from public feeds:
- Reddit meme communities (e.g., `r/memes`, `r/dankmemes`, `r/me_irl`, `r/wholesomememes`) using public JSON endpoints with proper User-Agent rotation/headers.
- Know Your Meme trending feeds / RSS.
Extract and normalize metadata for every meme: title, media URL (direct image/gif/video), source platform, permalink, author, upvotes/score, created timestamp, and NSFW flags.

### R2. Deduplication, Ranking & Background Cache Worker
- Implement content deduplication (by canonical media URL and content hashing).
- Implement a trending algorithm that scores memes based on engagement (upvotes, comment ratio, and recency/velocity decay).
- Implement a background task/worker that periodically refreshes the meme cache (with configurable polling intervals and in-memory/SQLite storage) so API requests are served with sub-millisecond latency.
- Provide graceful degradation and fallback if any upstream provider is temporarily rate-limited or unavailable.

### R3. REST API Endpoints with OpenAPI Documentation
Expose clean, fully-typed REST endpoints with Pydantic validation and interactive Swagger UI (`/docs`):
- `GET /api/v1/memes/latest`: Retrieve newest memes across all or specific sources with pagination (`limit`, `cursor`/`offset`).
- `GET /api/v1/memes/trending`: Retrieve currently trending memes ranked by hotness/velocity.
- `GET /api/v1/memes/random`: Fetch a random meme with optional source or category filters.
- `GET /api/v1/sources`: List active data sources, health status, and item counts.
- Query parameters for NSFW filtering (`nsfw=false` by default), source filtering, and sort orders.

### R4. Automated Verification & Test Suite
Include an automated `pytest` test suite covering:
- Unit tests for source parsers, data models, deduplication, and trending score calculations.
- Integration/API tests for all REST endpoints using `httpx.AsyncClient` or FastAPI `TestClient`.
- Resiliency tests verifying fallback behavior when upstream network feeds fail.

## Acceptance Criteria

### API Functionality & Schema Compliance
- [ ] FastAPI application starts cleanly on `http://127.0.0.1:8000` with interactive Swagger docs accessible at `/docs`.
- [ ] `GET /api/v1/memes/latest` returns HTTP 200 with valid JSON array containing normalized meme objects (`id`, `title`, `url`, `source`, `score`, `created_at`).
- [ ] `GET /api/v1/memes/trending` returns memes sorted in descending order of trending score.
- [ ] `GET /api/v1/memes/random` returns a single valid meme payload.
- [ ] Source filtering (`?source=reddit` or `?source=knowyourmeme`) accurately restricts returned items.

### Background Polling & Reliability
- [ ] Background polling worker runs automatically without blocking the main event loop.
- [ ] Data deduplication prevents duplicate meme URLs from appearing in latest/trending lists.
- [ ] Service returns cached data and handles network disconnections without crashing if external endpoints time out.

### Testing & Verification
53: - [ ] Running `pytest` in `d:/API/meme_tracker_api` executes all test cases and achieves 100% pass rate.
54: 
55: ## 2026-09-02T20:53:54Z
56: 
57: Build an upgraded multi-platform meme tracking service, live ranking engine, and sleek developer web portal that ingests 100% authentic memes from multiple open networks (Reddit, Bluesky, Know Your Meme, Mastodon), serves them via comprehensive OpenAPI/Swagger endpoints, and displays them in a modern, casual-typography UI with crisp vector SVGs and spring micro-animations.
58: 
59: Working directory: d:/API/meme_tracker_api
60: Integrity mode: development
61: 
62: ## Requirements
63: 
64: ### R1. Multi-Platform Authentic Ingestion (No Fakes)
65: Expand data ingestion beyond Reddit to include 100% authentic, open internet meme platforms with verified direct post permalinks and direct media attachments:
66: - **Reddit Public JSON feeds**: `r/dankmemes`, `r/memes`, `r/me_irl`, `r/GenAlpha`, `r/wholesomememes`, `r/AdviceAnimals`.
67: - **Bluesky AT Protocol Public API**: Ingest public meme feeds and trending humor via `public.api.bsky.app/xrpc/` with real `@handle` attributions, direct `https://bsky.app/profile/...` post links, and direct CDN images.
68: - **Know Your Meme**: Documented viral meme entries and cultural lore.
69: - **Mastodon / Fediverse Public Hashtag Feeds**: Public `#meme` timelines with genuine post URLs and author handles.
70: - Strictly **zero fake mock items or generic hashtag redirects**.
71: 
72: ### R2. Dynamic Trending Engine & Background Worker
73: - Implement background task polling on configurable intervals (default 5–10 mins) that updates meme records in SQLite and in-memory cache without blocking the main event loop.
74: - Dynamic scoring algorithm:
75:   $$\text{trending\_score} = (\text{score} + 1.5 \times \text{num\_comments}) \times e^{-\lambda \Delta t}$$
76:   where $\lambda = \ln(2) / 12$ (12-hour half-life), ensuring fresh viral memes posted today outrank older historical items.
77: - Real-time community upvoting on the web portal (+1) stored in `localStorage` and synchronized with the Top 10 Trending table.
78: 
79: ### R3. Updated Interactive OpenAPI / Swagger Documentation
80: - Update FastAPI route schemas and OpenAPI metadata accessible at `/docs` and `/redoc`:
81:   - Detailed parameter descriptions and enums for `generation` (`gen_alpha`, `gen_z`, `millennial`, `gen_x`).
82:   - Source platform filters (`reddit`, `bluesky`, `knowyourmeme`, `mastodon`).
83:   - Realistic response examples and schema models (`MemeResponse`, `PaginatedMemeResponse`, `SourceStats`).
84: 
85: ### R4. Sleek Developer Portal with Vector SVGs, Casual Typography & Micro-Animations
86: - **Typography**: Switch to casual, approachable, high-legibility typography (**Plus Jakarta Sans** for UI, **JetBrains Mono** for endpoints and code).
87: - **Vector / SVG Icons**: Replace all emoji icons (`⚡`, `●`, `★`, `▲`, `⌕`, `↗`, `🤍`, `❤️`) with crisp, scalable inline SVGs (flame, heart, trending-up, external-link, search, terminal, copy, check, github).
88: - **Spring Micro-Animations**:
89:   - Interactive cards with subtle spring hover elevation and glow.
90:   - Heart upvote vector spring bounce on click with active color fill.
91:   - Smooth sliding transition between Feed Explorer, Top 10 Trending, and API Studio.
92:   - 1-click cURL snippet copy with animated checkmark toast feedback.
93:   - Live API status dot with subtle pulse.
94: 
95: ### R5. Comprehensive Automated Test Suite & Resiliency
96: - Automated `pytest` suite verifying:
97:   - All REST endpoints (`/trending`, `/latest`, `/random`, `/sources`, `/health`, `/web`).
98:   - Upstream network fallback resilience (handling rate-limits or offline states gracefully).
99:   - Generation classification and trending velocity scoring.
100:   - 100% test pass rate across the full suite.
101: 
102: ## Acceptance Criteria
103: 
104: ### Data & Ingestion
105: - [ ] Ingestion engine fetches authentic posts from Reddit, Bluesky, Know Your Meme, and Mastodon with valid direct permalinks and direct media URLs.
106: - [ ] No fake mock items or dead search links exist in the dataset.
107: 
108: ### API & Docs
109: - [ ] Interactive Swagger UI at `/docs` displays complete parameter enums for `generation` and `source` with rich example schemas.
110: - [ ] `GET /api/v1/memes/trending` returns items ranked by dynamic velocity and recency decay.
111: 
112: ### UI & Aesthetics
113: - [ ] Web dashboard uses Plus Jakarta Sans typography and replaces all emojis with inline vector SVGs.
114: - [ ] Upvote interaction uses a crisp vector SVG with smooth spring animation and 1-vote persistence.
115: - [ ] Cards display unclipped media (`object-fit: contain;`) with real author credits and working thread links.
116: 
117: ### Verification
118: - [ ] All automated `pytest` tests pass cleanly with 100% pass rate.
