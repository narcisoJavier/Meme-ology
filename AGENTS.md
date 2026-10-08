<!-- antislop:start -->
## antislop
For UI, copy, people, mobile layout, or code comments work, load the antislop skill for the task:
- Core filter, always on: `antislop`
- UI / visual: `antislop-ui`
- Copy & text: `antislop-copywriting`
- People: `antislop-human`
- Mobile / responsive: `antislop-layoutmobile`
- Code comments: `antislop-code`
Before starting, ask the user when antislop applies: during the work, or after it is done.
<!-- antislop:end -->

## Live Meme Discovery & Data Integrity Guardrails

Whenever writing, modifying, or testing code in `meme_tracker_api`, adhere to these non-negotiable invariants:

### 1. Zero Metric Fabrication & Truthful Provenance
- **Never invent** timestamps, view counts, scores, comment counts, or popularity rankings.
- If an upstream source does not supply a metric (e.g., YouTube RSS without views), set `metrics_quality="partial"` and native score to 0. Do NOT estimate or synthesize numbers.
- Never generate synthetic engagement or backfill old data to make an interface look active.
- `created_at` must always represent original publication time, never fetch time.

### 2. Source Classification & Separation
- Every ingested source must explicitly declare its class:
  - `social_observation`: Recent public post with source metrics (Reddit, Bluesky, Mastodon).
  - `editorial_signal`: Recent trusted curation/commentary (e.g., LIMC YouTube RSS).
  - `catalog`: Known format reference (e.g., Know Your Meme).
  - `unknown`: Insufficient provenance. Cannot rank directly.
- **Know Your Meme (KYM)** is reference/catalog data only. Never treat KYM records as live social trends or assign them current timestamps.
- **YouTube RSS** is an editorial signal, not a raw social engagement meter.

### 3. Trend Promotion & Evidence Requirements
- An observation remains `confidence="unverified"` unless promoted.
- Promotion to `/trending` requires:
  - At least 2 independent social source groups within the 24h evidence window, OR
  - A trusted editorial signal within the 48h editorial window.
- Single-source posts must never be labeled or promoted as global trends.
- Deduplication must reject generic stop words ("meme", "funny", "viral") from forming canonical keys.

### 4. Serverless Routing & Concurrency
- Never route API endpoints directly to static JSON files in `vercel.json`. All API requests must be handled by FastAPI via `api/index.py`.
- Do NOT run continuous polling daemons (`MemePollingWorker`) in serverless environments (`VERCEL=1`).
- Serverless refreshes must be request-driven with:
  - In-process memory caching (TTL = 300s).
  - An async in-process lock to prevent duplicate concurrent upstream requests.
- Graceful degradation: If refresh fails, return the last successful live snapshot. If unavailable, return fallback static data explicitly flagged as `stale` or `degraded`.

### 5. Dynamic Health & Fail-Closed Publication
- `/health` must be dynamically computed from current runtime snapshot state and source status. Never return a hardcoded static health status.
- `scripts/harvest_live_sources.py` must fail closed: never overwrite valid static snapshots when live source harvesting fails.
