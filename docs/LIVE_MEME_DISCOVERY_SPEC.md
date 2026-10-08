# Meme-Ology Live Meme Discovery Specification

**Status:** Proposed implementation specification
**Version:** 1.0
**Date:** 2026-09-22
**Repository:** `narcisojavier/meme-ology`

## 1. Purpose

Meme-Ology currently presents old, mixed-quality records as if they were current popular memes. The product needs a discovery pipeline that is recent, honest about evidence quality, and useful without pretending to have a complete free feed from every major social platform.

This document defines the implementation required to:

1. Serve live observations through the deployed API instead of bypassing FastAPI with stale JSON rewrites.
2. Keep the existing low-cost deployment model through short-lived caching and a safe static fallback.
3. Separate recent posts, verified trends, editorial signals, and meme catalog records.
4. Prevent fabricated timestamps, comments, views, scores, or popularity rankings.
5. Promote a meme as a real trend only when there is sufficient recent evidence.
6. Use free public feeds and curated sources first, while keeping the data model ready for future X, TikTok, and Instagram integrations.

## 2. Current Problem

### 2.1 Deployed requests bypass the application

`vercel.json` currently rewrites these routes directly to checked-in files:

- `/api/v1/memes/trending` -> `/data/trending.json`
- `/api/v1/memes/latest` -> `/data/latest.json`
- `/api/v1/memes/random` -> `/data/random.json`
- `/api/v1/sources` -> `/data/sources.json`
- `/health` -> `/data/health.json`

The result is that deployed clients do not use the FastAPI route handlers, the live store, or the current ingestion logic. The application can contain a correct harvester while the public site continues serving old data.

### 2.2 The Vercel runtime does not run a continuous poller

`app/main.py` deliberately skips the continuous `MemePollingWorker` when `VERCEL` is set. That is correct for a serverless runtime, but it means Vercel cannot depend on an in-process daemon to keep data fresh.

The serverless design therefore needs request-triggered refresh with a short cache, not a background loop.

### 2.3 The checked-in snapshot is stale

The current `public/data` snapshot was generated on September 3, 2026. The screenshots showing records marked approximately 16 days old are consistent with that snapshot age.

The static health file can also report `ok` while the interface reports `API Degraded`. Both are reading different or stale views of system health.

### 2.4 Sources are being compared as if their metrics were equivalent

The existing data mixes:

- Reddit-style post scores and comments.
- YouTube publication records.
- Know Your Meme catalog entries.
- Bluesky and Mastodon posts.

These are not directly comparable. A KYM catalog count is not equivalent to a recent Reddit score, and a YouTube RSS item may have no view count at all.

No source may receive invented metrics merely to make cross-platform ranking possible.

### 2.5 Legacy generators can create false freshness

Several older scripts generated timestamps and engagement using formulas or hardcoded values. Those scripts must not be used by deployment, scheduled jobs, or documentation.

The pushed commit `ecf6514` added a fail-closed live harvester, but the static output was not regenerated after that change. This specification includes the deployment and publication work needed to make that fix visible.

## 3. Product Definitions

The API and interface must use these terms consistently.

### 3.1 Observation

A single record received from a source, with a source identifier, source URL, publication time, and whatever metrics the source actually supplied.

Examples:

- A public Reddit post.
- A Bluesky post.
- A YouTube video listed in a channel RSS feed.
- A Mastodon post.

### 3.2 Catalog entry

A reference record describing a known meme format or topic. A catalog entry is not evidence that the format is currently popular.

Know Your Meme belongs in this category by default.

### 3.3 Editorial signal

A recent item from a trusted, explicitly configured creator or publication that identifies or discusses a meme trend.

Lessons in Meme Culture is an editorial signal source. Its presence may support promotion, but it must be visibly labeled as editorial evidence.

### 3.4 Candidate

A fresh observation or group of observations that may represent a developing trend but has not passed the evidence threshold.

Candidates may appear in the recent feed with an `unverified` confidence label.

### 3.5 Promoted trend

A candidate that satisfies the evidence rules in Section 8. A promoted trend may appear in `/trending`.

## 4. Product Goals and Non-Goals

### 4.1 Goals

- Show content observed recently, with accurate source publication times.
- Make the difference between latest, trending, editorial, and catalog content obvious.
- Rank only records with usable observed evidence.
- Show users why an item was promoted.
- Continue to work when one or more upstream sources fail.
- Keep the first version usable without paid social APIs.
- Make future official platform adapters compatible with the same normalized contract.

### 4.2 Non-goals for version one

- Claiming a complete view of all memes on the internet.
- Scraping private pages, authenticated feeds, or internal platform endpoints.
- Circumventing CAPTCHAs, rate limits, access controls, or platform restrictions.
- Treating a single post as proof of a global trend.
- Backfilling old data and presenting it as newly observed.
- Generating synthetic engagement to fill an empty feed.
- Using Know Your Meme as a live popularity meter.

## 5. Target Architecture

```text
                         +----------------------+
                         | Browser / API Client |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         | FastAPI on Vercel   |
                         | live snapshot cache  |
                         +----------+-----------+
                                    |
                 cache hit --------+-------- cache miss
                                    |                  |
                                    v                  v
                         +----------------+   +----------------------+
                         | Current memory |   | Source refresh       |
                         | snapshot       |   | with timeout and lock |
                         +--------+-------+   +----------+-----------+
                                  |                       |
                                  |                       v
                                  |             +----------------------+
                                  |             | Normalized observations|
                                  |             +----------+-----------+
                                  |                       |
                                  |                       v
                                  |             +----------------------+
                                  |             | Quality gate          |
                                  |             | dedupe and evidence   |
                                  |             +----------+-----------+
                                  |                       |
                                  +-----------+-----------+
                                              v
                                  +------------------------+
                                  | latest / trending      |
                                  | editorial / catalog    |
                                  +------------------------+

       checked-in static snapshot --------------------^
       used only when a live refresh is unavailable
```

### 5.1 Runtime modes

#### Local or persistent runtime

- Start the existing `MemePollingWorker`.
- Persist live observations to SQLite.
- Hydrate the in-memory store from SQLite on startup.
- Continue polling on the configured interval.

#### Vercel serverless runtime

- Do not start a continuous daemon.
- Load the latest checked-in snapshot on cold start.
- Refresh source data on cache miss or when the live snapshot is older than the refresh TTL.
- Use an in-process lock so concurrent requests do not trigger duplicate refreshes within one function instance.
- Return the last successful live snapshot if the newest refresh partially fails.
- Return the static snapshot only when no live snapshot is available.
- Mark fallback data as stale or degraded in the response and health metadata.

### 5.2 Required implementation areas

The implementation should update these areas:

- `vercel.json`: stop routing API endpoints directly to static JSON.
- `api/index.py`: add a Vercel ASGI entrypoint that imports the FastAPI application.
- `app/main.py`: preserve local polling while exposing the application correctly in serverless mode.
- `app/ingestion/`: add or refine free-feed adapters and source quality handling.
- `app/storage/`: add snapshot freshness and evidence-aware retrieval behavior.
- `app/models/meme.py`: extend the public provenance and evidence contract.
- `scripts/harvest_live_sources.py`: remain the canonical offline publication command.
- `public/data/*`: regenerate only from successful live observations.

## 6. Source Strategy

### 6.1 Source classes

Every source must declare one class:

| Source class | Purpose | Can rank directly? | Example |
|---|---|---:|---|
| `social_observation` | Recent public post with source metrics | Yes, if metrics are observed | Reddit, Bluesky, Mastodon |
| `editorial_signal` | Recent video or publication discussing trends | Yes as supporting evidence | LIMC YouTube RSS |
| `catalog` | Known meme format or reference page | No | Know Your Meme |
| `unknown` | Data with insufficient provenance | No | Any unverified fixture |

### 6.2 Free first-version sources

The first implementation may use:

1. YouTube channel RSS feeds for configured meme-culture creators, including LIMC.
2. Public RSS, Atom, or JSON feeds that are explicitly configured in the application.
3. Existing public Bluesky or Mastodon endpoints only when enabled by configuration and when their timestamps and source IDs are present.
4. Know Your Meme feeds as catalog or editorial reference data only.

The application must not imply that this set represents all activity on X, TikTok, or Instagram.

### 6.3 X, TikTok, and Instagram

Version one must define adapter interfaces for future official integrations but keep them disabled until credentials and permitted access are available.

The adapters must not use browser automation or undocumented internal endpoints as a default strategy.

Future adapters must provide:

- Stable platform post or video ID.
- Canonical permalink.
- Source publication timestamp.
- Platform-native metrics with a declared metric type.
- Rate-limit and authentication status.
- Terms and retention constraints documented in the adapter.

### 6.4 YouTube RSS rules

YouTube RSS is a publication feed, not a complete engagement feed. A YouTube RSS item must therefore:

- Preserve the video publication timestamp.
- Set `source_class=editorial_signal` for trusted meme-culture channels.
- Set `metrics_quality=partial` when views or interaction counts are absent.
- Never invent view counts.
- Be eligible for editorial evidence promotion but not for raw social engagement ranking unless observed metrics are available.

### 6.5 Know Your Meme rules

KYM records must:

- Use `source_class=catalog`.
- Preserve the KYM permalink.
- Never be assigned synthetic current timestamps.
- Never be assigned invented social engagement.
- Never enter `/trending` solely because a catalog value is numerically large.
- Be available through `/catalog` or an explicit catalog filter.

## 7. Configuration Contract

Add settings with safe defaults. Environment variables must be optional unless a source adapter requires credentials.

```text
LIVE_REFRESH_TTL_SECONDS=300
LIVE_SNAPSHOT_MAX_AGE_SECONDS=3600
LATEST_DEFAULT_WINDOW_SECONDS=86400
TRENDING_WINDOW_SECONDS=86400
EDITORIAL_WINDOW_SECONDS=172800
SOURCE_REQUEST_TIMEOUT_SECONDS=10
SOURCE_MAX_RETRIES=2
MAX_ITEMS_PER_SOURCE=50
TRUSTED_EDITORIAL_CHANNELS=["UCaHT88aobpcvRFEuy4v5Clg"]
PUBLIC_FEED_URLS=[]
ENABLE_BLUESKY=false
ENABLE_MASTODON=false
ENABLE_KYM_CATALOG=true
ENABLE_X_API=false
ENABLE_TIKTOK_API=false
ENABLE_INSTAGRAM_API=false
```

Configuration requirements:

- Disabled sources must not be reported as healthy active sources.
- A source with no recent observations may be `ok` only if its request succeeded and the feed was empty.
- A source that returned fixture data after a live failure must be `degraded`, and fixture records must be excluded from live output.
- Source names and IDs must be stable so evidence can be grouped across refreshes.

## 8. Normalization and Provenance

### 8.1 Existing normalized record

Continue using `NormalizedMeme` as the internal contract. The following fields are mandatory for live records:

| Field | Requirement |
|---|---|
| `id` | Stable internal ID derived from source and raw ID |
| `raw_id` | Original source identifier when available |
| `title` | Source title or normalized caption, without invented text |
| `media_url` | Original media URL when available |
| `source_platform` | Platform enum or documented source name |
| `source_community` | Channel, feed, tag, or community |
| `permalink` | Canonical source URL |
| `created_at` | Source publication time, never fetch time |
| `score` | Observed native score, otherwise `0` with quality metadata |
| `num_comments` | Observed native comment count, otherwise `0` with quality metadata |
| `data_origin` | `live`, `fixture`, or `catalog` |
| `metrics_quality` | `observed`, `partial`, `unknown`, or `fixture` |
| `observed_at` | Time the tracker fetched the observation |

### 8.2 Required additions

Add these fields to the normalized and public response models:

```python
source_class: Literal[
    "social_observation",
    "editorial_signal",
    "catalog",
    "unknown",
]
feed_kind: Literal[
    "recent",
    "trend",
    "editorial",
    "catalog",
]
evidence_count: int
source_count: int
confidence: Literal["unverified", "supported", "promoted"]
canonical_key: str | None
```

Defaults must be conservative:

- `evidence_count=1` for a single observation.
- `source_count=1` for a single source.
- `confidence="unverified"` unless promotion rules pass.
- `source_class="unknown"` if the adapter cannot prove its class.

### 8.3 Example observation

```json
{
  "id": "youtube_dQw4w9WgXcQ",
  "raw_id": "dQw4w9WgXcQ",
  "title": "Recent meme culture topic",
  "media_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
  "media_type": "video",
  "source_platform": "youtube",
  "source_community": "Lessons in Meme Culture",
  "permalink": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "author": "Lessons in Meme Culture",
  "score": 0,
  "num_comments": 0,
  "created_at": 1780000000.0,
  "data_origin": "live",
  "metrics_quality": "partial",
  "observed_at": 1780000300.0,
  "source_class": "editorial_signal",
  "feed_kind": "editorial",
  "evidence_count": 1,
  "source_count": 1,
  "confidence": "unverified",
  "canonical_key": "recent-meme-culture-topic"
}
```

The example timestamp is illustrative only. Production records must contain the timestamp received from the source.

## 9. Deduplication and Meme Identity

### 9.1 Deduplication order

Apply deduplication in this order:

1. Exact `(source_platform, raw_id)` match.
2. Exact canonical media URL match.
3. Exact content hash match when the media is available.
4. Canonical key match using normalized title, hashtags, sound/template name, and explicit source metadata.
5. Token similarity only when the records have the same source class and overlapping time window.

Deduplication must never merge unrelated posts only because they both contain generic words such as `meme`, `funny`, `trend`, or `viral`.

### 9.2 Canonical key normalization

The canonical key builder must:

- Lowercase text.
- Remove URLs, punctuation, and common stop words.
- Preserve distinctive proper nouns, phrases, hashtags, sound names, and template names.
- Remove source boilerplate such as `post by`, `screenshot`, or `new meme` when it is clearly feed formatting.
- Reject keys that contain no distinctive token.
- Store the original title separately for display.

Generic titles must remain generic observations and must not be presented as named meme formats.

## 10. Evidence and Promotion Rules

### 10.1 Evidence window

The default evidence window is 24 hours for social observations and 48 hours for editorial signals.

The window must be configurable for tests and future tuning.

### 10.2 Independence rules

Evidence counts by source identity, not by raw item count.

Examples:

- Ten Reddit posts from one subreddit count as one source group.
- Reddit plus Bluesky count as two source groups.
- LIMC plus KYM count as two source classes, but KYM alone cannot provide popularity evidence.
- Duplicate copies of the same URL count once.

### 10.3 Promotion criteria

A candidate is `promoted` when either condition is true:

1. At least two independent social source groups reference the same canonical key inside the evidence window.
2. A trusted editorial signal references the canonical key inside the editorial window and the record has no contradictory freshness or provenance information.

A single ordinary social post remains `unverified`.

KYM alone can never promote a trend.

### 10.4 Confidence values

| Confidence | Meaning |
|---|---|
| `unverified` | One source or insufficient identity evidence |
| `supported` | Multiple recent observations or one strong supporting signal |
| `promoted` | Meets the trend promotion rule and is eligible for `/trending` |

## 11. Ranking Rules

### 11.1 General requirements

- Do not compare raw Reddit scores to raw YouTube views as if they were the same unit.
- Do not use catalog values in social engagement ranking.
- Do not rank records with fabricated or fixture metrics.
- Freshness must reduce the score of old observations.
- Source spread must increase confidence only when the sources are independent.

### 11.2 Per-source engagement normalization

Within each refresh cycle, calculate a percentile rank separately for each source class and metric type:

- Reddit: score and comments.
- Bluesky: likes, reposts, or available native engagement.
- Mastodon: favourites, boosts, or available native engagement.
- YouTube: views only when observed from an approved metric source.

Missing metrics receive no percentile contribution. They do not receive a guessed value.

### 11.3 Trend score

For a promoted candidate, calculate:

```text
freshness = exp(-age_hours / 24)
engagement = mean(observed_source_percentiles)
spread_bonus = 1 + 0.25 * min(source_count - 1, 3)
editorial_bonus = 0.10 when a trusted editorial signal is present, otherwise 0

trend_score = 100 * freshness * (0.75 * engagement + 0.25 * editorial_bonus) * spread_bonus
```

Implementation notes:

- The score is a ranking aid, not a claim that one platform's number equals another platform's number.
- If no observed engagement exists, the item may remain in the editorial or recent feed but must not receive a fabricated trend score.
- The UI must display evidence and confidence alongside the score.

### 11.4 Latest ordering

`/latest` is ordered by source publication time descending, not by `trending_score`.

Default behavior:

- Include live social observations from the last 24 hours.
- Include recent editorial signals from the last 48 hours when the caller requests editorial content or the source category is enabled.
- Exclude catalog entries from the default latest feed.
- Exclude fixture records.

## 12. API Contract

### 12.1 `GET /api/v1/memes/latest`

Returns recent live observations.

Default query behavior:

```text
limit=20
offset=0
time_window=24h
source_class=social_observation
include_editorial=false
include_catalog=false
```

Existing filters remain supported where meaningful. Add:

- `source_class`
- `confidence`
- `include_editorial`
- `include_catalog`

### 12.2 `GET /api/v1/memes/trending`

Returns promoted trend representatives, not an arbitrary list of old posts.

Default query behavior:

```text
limit=20
offset=0
time_window=24h
confidence=promoted
```

Each item must include evidence links or a clear explanation of the promotion reason.

### 12.3 `GET /api/v1/memes/editorial`

Returns recent trusted editorial signals, including LIMC uploads.

Required behavior:

- Ordered by publication time.
- Clearly labeled `editorial_signal`.
- Does not imply that the video itself is a globally trending meme.
- Preserves the video permalink.

### 12.4 `GET /api/v1/memes/catalog`

Returns catalog entries such as KYM records.

Required behavior:

- No social popularity claims.
- No synthetic current timestamps.
- Catalog age and source publication information are displayed separately.

### 12.5 `GET /api/v1/memes/random`

Returns one item from the current live recent or promoted trend pool.

It must not randomly select a stale catalog record unless the caller explicitly requests `source_class=catalog`.

### 12.6 `GET /api/v1/sources`

Returns source telemetry with:

```json
{
  "name": "youtube:UCaHT88aobpcvRFEuy4v5Clg",
  "source_class": "editorial_signal",
  "status": "ok",
  "item_count": 5,
  "last_success_at": 1780000300.0,
  "last_error": null,
  "metrics_quality": "partial",
  "is_enabled": true
}
```

### 12.7 `GET /health`

The health response must be calculated from runtime state, not a hardcoded static answer.

Required fields:

```json
{
  "status": "ok",
  "snapshot_state": "live",
  "snapshot_age_seconds": 42,
  "last_successful_refresh": 1780000300.0,
  "total_memes": 120,
  "total_sources": 6,
  "healthy_sources": 5,
  "degraded_sources": 1,
  "has_fallback": true
}
```

Status rules:

- `ok`: live snapshot age is within 10 minutes and at least one enabled source succeeded.
- `degraded`: live snapshot is older than 10 minutes, or one or more important sources failed.
- `stale`: only a fallback snapshot is available and it is older than one hour.
- `unavailable`: no usable snapshot exists.

## 13. Cache and Failure Behavior

### 13.1 Refresh policy

- Cache TTL: 300 seconds.
- One refresh per process at a time.
- Per-source request timeout: 10 seconds.
- Maximum retries: 2 for transient failures only.
- Do not retry authentication, access-control, or malformed-feed failures indefinitely.

### 13.2 Partial source failure

If one source fails:

- Keep successful observations from other sources.
- Mark the failed source as `degraded`.
- Preserve the last successful snapshot for that source if it has not exceeded the maximum age.
- Do not insert fixture records into live output.

### 13.3 No live result

If every live source fails:

- Return the last successful live snapshot if available.
- Otherwise return the checked-in fallback snapshot with `snapshot_state=stale`.
- Do not label stale fallback items as newly observed.
- If the fallback is older than the default latest window, `/latest` must return an empty list rather than showing old items as recent.
- `/health` must report the degraded or stale state.

### 13.4 Static publication

The canonical static publication command remains:

```bash
python scripts/harvest_live_sources.py
```

The command must:

- Fail closed when no live records are returned.
- Preserve the existing output files when the refresh fails.
- Write source IDs and timestamps received from upstream.
- Exclude fixture and catalog-only records from ranked output.
- Write freshness metadata into the generated files.

## 14. Frontend Behavior

The interface must make the source and evidence distinction visible without requiring users to understand the internals.

### 14.1 Primary navigation

Use four meaningful feed views:

1. **Live now**: recent observed social posts.
2. **Emerging**: candidates with supporting evidence but not necessarily promoted.
3. **Editorial**: recent LIMC and other trusted meme-culture videos.
4. **Catalog**: known meme formats and references from KYM.

The existing “Trending” label must only refer to the promoted trend endpoint.

### 14.2 Card requirements

Every card must show:

- Original source.
- Source publication age.
- Evidence or confidence label.
- Whether it is a post, editorial signal, or catalog entry.
- The canonical source link.
- Observed engagement only when available.

Never display a large catalog number using the same visual treatment as a live social score.

### 14.3 Status badge

The status badge must use `/health` and show:

- Live.
- Degraded.
- Stale.
- Unavailable.

The badge must include a useful reason, such as `1 source delayed` or `last live refresh 42m ago`.

### 14.4 Required interface states

Implement and verify:

- Loading state while a refresh is pending.
- Empty state when no recent records meet the window.
- Partial-result state when some sources fail.
- Stale fallback state when old data is displayed.
- Error state when there is no usable snapshot.

## 15. Implementation Phases

### Phase 1: Runtime routing

1. Add the Vercel ASGI entrypoint.
2. Remove endpoint-specific rewrites to static JSON.
3. Route API and health requests through FastAPI.
4. Preserve static `/data/*` files as fallback assets only.
5. Add a deployment smoke test for route reachability.

### Phase 2: Live snapshot provider

1. Add the five-minute process-local cache.
2. Add an async refresh lock.
3. Add fallback loading and age tracking.
4. Return runtime health metadata.
5. Keep local polling behavior unchanged.

### Phase 3: Source quality and adapters

1. Make source class and metric quality mandatory in normalization.
2. Ensure YouTube RSS is included in live harvesting.
3. Configure LIMC as a trusted editorial source.
4. Move KYM into catalog handling.
5. Add configurable public feed adapters.
6. Add disabled interfaces for future official X, TikTok, and Instagram integrations.

### Phase 4: Evidence aggregation

1. Build canonical keys.
2. Deduplicate observations.
3. Group evidence across independent source groups.
4. Apply promotion rules.
5. Calculate platform-normalized trend scores.
6. Add evidence links and confidence to responses.

### Phase 5: API and interface separation

1. Make `/latest` recent-only.
2. Make `/trending` promotion-only.
3. Add `/editorial` and `/catalog`.
4. Update cards and status badges.
5. Add empty, degraded, and stale states.

### Phase 6: Cleanup and publication

1. Mark legacy synthetic generators as unsupported.
2. Remove them from deployment instructions and CI.
3. Run one successful live harvest.
4. Verify the generated snapshot contains current timestamps and provenance.
5. Deploy to a preview environment.
6. Run smoke tests.
7. Publish to production.

## 16. Testing Specification

### 16.1 Unit tests

Test:

- Canonical key normalization.
- Generic-title rejection.
- Exact source-ID deduplication.
- Media URL and content-hash deduplication.
- Source independence counting.
- Promotion with two independent sources.
- Non-promotion with one ordinary source.
- Promotion through a trusted editorial signal.
- KYM exclusion from ranked trends.
- Freshness decay.
- Missing metrics remaining missing.
- Fixture records excluded from live output.

### 16.2 Adapter tests

For every adapter, test:

- Valid response parsing.
- Missing timestamp behavior.
- Missing metric behavior.
- Malformed response behavior.
- Timeout behavior.
- Retry behavior.
- Rate-limit behavior.
- Stable source ID generation.
- Correct source class assignment.

YouTube-specific tests must parse a fixture containing multiple recent channel entries and verify that publication time and permalink are preserved.

### 16.3 Store and API tests

Test:

- `/latest` excludes records outside the default window.
- `/latest` is ordered by publication time.
- `/trending` contains only promoted candidates.
- `/editorial` returns trusted editorial signals.
- `/catalog` returns KYM records without ranking them.
- `/random` excludes stale catalog records by default.
- Health state changes across fresh, degraded, stale, and unavailable conditions.
- Existing pagination and validation behavior remains compatible.

### 16.4 Serverless tests

Run the app with `VERCEL=1` and verify:

- The ASGI entrypoint loads.
- API routes do not resolve to static JSON rewrites.
- The continuous poller is not started.
- A cache miss performs one refresh.
- Concurrent cache misses share one refresh.
- A failed refresh returns the last successful snapshot.
- A cold start can load the fallback snapshot.

### 16.5 Deployment smoke tests

After deployment, verify:

```text
GET /health
GET /api/v1/memes/latest?limit=5
GET /api/v1/memes/trending?limit=5
GET /api/v1/memes/editorial?limit=5
GET /api/v1/memes/catalog?limit=5
GET /api/v1/sources
```

The smoke test must confirm that:

- `generated_at` or equivalent freshness data is current.
- At least one live source has succeeded or the response clearly reports stale fallback.
- `latest` and `trending` are not identical by construction.
- No record claims observed metrics when the source did not supply them.
- YouTube editorial items appear when the configured feed has recent entries.

## 17. Observability

Log these fields for each refresh:

- Refresh ID.
- Start and end time.
- Source name and class.
- Request duration.
- Item count.
- Freshest and oldest source timestamps.
- Error category.
- Number of live, partial, catalog, and rejected records.
- Number of candidates and promoted trends.

Do not log credentials, private tokens, or full user-generated content unnecessarily.

The health endpoint must provide enough data to explain an `API Degraded` badge without requiring server logs.

## 18. Security and Platform Compliance

- Store API credentials only in environment variables or the deployment secret manager.
- Never commit platform tokens.
- Use an allowlist for configurable feed URLs where practical.
- Reject non-HTTP(S) source URLs.
- Apply per-source request timeouts and response-size limits.
- Do not bypass CAPTCHAs or access controls.
- Do not use undocumented private platform endpoints.
- Respect source terms, robots guidance where applicable, rate limits, and retention requirements.
- Keep original source links so users can verify the evidence.

## 19. Rollback Plan

If the live route causes a production problem:

1. Revert the deployment to the last known working version.
2. Keep static `/data/*` files available as a read-only fallback.
3. Disable the failing source through configuration rather than deleting the whole pipeline.
4. Restore the previous API route only as an emergency fallback, with a visible stale-data status.
5. Do not republish synthetic records to make the interface look full.

## 20. Definition of Done

The implementation is complete only when all of the following are true:

- Deployed API requests reach FastAPI.
- The continuous poller remains local-only and serverless refresh is request-driven.
- The deployed feed contains current live observations or explicitly reports stale fallback.
- `latest`, `trending`, `editorial`, and `catalog` have distinct semantics.
- KYM does not rank as social popularity without independent evidence.
- No generated timestamp, score, comment count, or view count is presented as observed.
- LIMC RSS entries appear in the editorial feed when available.
- Single-source records are not mislabeled as global trends.
- The health badge matches actual source and snapshot state.
- All tests in Section 16 pass.
- A production smoke test passes.
- Legacy synthetic generators are no longer part of the supported publication path.
- The generated static fallback has been refreshed from a successful live harvest.

## 21. References

- Vercel rewrites: <https://vercel.com/docs/routing/rewrites>
- Vercel cron jobs: <https://vercel.com/docs/cron-jobs>
- YouTube Data API search documentation: <https://developers.google.com/youtube/v3/docs/search/list>
- YouTube Data API getting started: <https://developers.google.com/youtube/v3/getting-started>
- TikTok Research API: <https://developers.tiktok.com/products/research-api>
