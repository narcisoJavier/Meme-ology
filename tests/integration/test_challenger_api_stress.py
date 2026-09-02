"""Empirical challenger stress-test suite for Meme Tracker REST API endpoints (Milestone M3).

Adversarial testing dimensions:
1. Adversarial query parameters: negative offsets, excessive limits, non-integer inputs, SQL injection strings, unicode/emoji.
2. Empty state responses: empty cache store and zero-match filters across /latest, /trending, /random, /sources, /health.
3. High-concurrency burst HTTP requests: concurrent requests via httpx.AsyncClient under load and during concurrent writes.
4. Read latency benchmarking: latency profiling on read endpoints and in-memory cache lookups.
5. OpenAPI and schema validation: /docs, /openapi.json, /redoc, error structure compliance.
"""

from __future__ import annotations

import asyncio
import statistics
import time
from typing import List

import httpx
import pytest

from app.models.meme import MediaType, NormalizedMeme, SourcePlatform
from app.storage.memory_store import MemoryStore


def _create_mock_memes(count: int, now: float | None = None) -> List[NormalizedMeme]:
    """Helper to generate mock memes for populating MemoryStore."""
    if now is None:
        now = time.time()
    subreddits = ["memes", "dankmemes", "me_irl", "wholesomememes"]
    memes: List[NormalizedMeme] = []
    for i in range(count):
        is_reddit = (i % 2 == 0)
        comm = subreddits[(i // 2) % len(subreddits)] if is_reddit else "confirmed"
        plat = SourcePlatform.REDDIT if is_reddit else SourcePlatform.KNOWYOURMEME
        memes.append(
            NormalizedMeme(
                id=f"meme_{i:04d}",
                title=f"Meme Title {i} {'[NSFW]' if i % 10 == 0 else ''}",
                media_url=f"https://i.redd.it/meme_{i}.png" if is_reddit else f"https://kym.com/photos/{i}.jpg",
                media_type=MediaType.IMAGE,
                source_platform=plat,
                source_community=f"r/{comm}" if is_reddit else comm,
                permalink=f"https://reddit.com/r/{comm}/comments/{i}" if is_reddit else f"https://knowyourmeme.com/memes/{i}",
                author=f"author_{i % 20}",
                score=100 + i * 10,
                num_comments=10 + i * 2,
                created_at=now - (i * 300),  # spaced 5 mins apart
                is_nsfw=(i % 10 == 0),
                content_hash=f"hash_{i:04d}",
                trending_score=float(1000 - i),
            )
        )
    return memes


@pytest.mark.asyncio
class TestAdversarialQueryParameters:
    """Test API resilience against malformed, adversarial, and boundary query parameters."""

    async def test_negative_offset_returns_422(self, async_client: httpx.AsyncClient) -> None:
        """Verify negative offset triggers validation error (422) on /latest and /trending."""
        for endpoint in ["/api/v1/memes/latest", "/api/v1/memes/trending"]:
            for bad_offset in [-1, -5, -999999]:
                resp = await async_client.get(f"{endpoint}?offset={bad_offset}")
                assert resp.status_code == 422, f"Expected 422 for offset={bad_offset} on {endpoint}, got {resp.status_code}"
                err = resp.json()
                assert "detail" in err

    async def test_excessive_and_invalid_limit_returns_422(self, async_client: httpx.AsyncClient) -> None:
        """Verify limit <= 0 or limit > 100 triggers validation error (422)."""
        for endpoint in ["/api/v1/memes/latest", "/api/v1/memes/trending"]:
            for bad_limit in [0, -1, -50, 101, 500, 99999]:
                resp = await async_client.get(f"{endpoint}?limit={bad_limit}")
                assert resp.status_code == 422, f"Expected 422 for limit={bad_limit} on {endpoint}, got {resp.status_code}"
                err = resp.json()
                assert "detail" in err

    async def test_non_integer_query_parameters_returns_422(self, async_client: httpx.AsyncClient) -> None:
        """Verify non-integer inputs for limit and offset trigger 422."""
        bad_values = ["abc", "1.5", "true", "null", "[1,2]", "{'a':1}"]
        for endpoint in ["/api/v1/memes/latest", "/api/v1/memes/trending"]:
            for val in bad_values:
                resp_offset = await async_client.get(f"{endpoint}?offset={val}")
                assert resp_offset.status_code == 422
                resp_limit = await async_client.get(f"{endpoint}?limit={val}")
                assert resp_limit.status_code == 422

    async def test_invalid_boolean_nsfw_parameter_returns_422(self, async_client: httpx.AsyncClient) -> None:
        """Verify non-boolean nsfw parameter triggers 422."""
        for val in ["maybe", "invalid", "123", "none"]:
            resp = await async_client.get(f"/api/v1/memes/latest?nsfw={val}")
            assert resp.status_code == 422

    async def test_sql_injection_payloads_do_not_crash(self, async_client: httpx.AsyncClient) -> None:
        """Verify SQL injection strings in source and time_window do not cause 500 errors."""
        sqli_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE memes; --",
            "' UNION SELECT id, title, url FROM memes --",
            "1; SELECT pg_sleep(5); --",
            "' OR 1=1 #",
            "admin'--",
            "\" OR \"\"=\"",
        ]
        for sqli in sqli_payloads:
            # /latest with sqli source
            resp1 = await async_client.get("/api/v1/memes/latest", params={"source": sqli})
            assert resp1.status_code == 200, f"SQLi in source caused unexpected status {resp1.status_code}"
            assert resp1.json()["items"] == []  # No matches for weird string

            # /trending with sqli time_window
            resp2 = await async_client.get("/api/v1/memes/trending", params={"time_window": sqli})
            assert resp2.status_code == 200, f"SQLi in time_window caused unexpected status {resp2.status_code}"

            # /random with sqli source -> returns 404 (no match)
            resp3 = await async_client.get("/api/v1/memes/random", params={"source": sqli})
            assert resp3.status_code == 404, f"SQLi in random source caused unexpected status {resp3.status_code}"

    async def test_unicode_and_emoji_query_parameters(self, async_client: httpx.AsyncClient) -> None:
        """Verify unicode strings, non-Latin scripts, and emoji parameters are safely handled."""
        unicode_payloads = [
            "🔥meme🔥",
            "你好世界",
            "مرحبا",
            "русский_мем",
            "¯\\_(ツ)_/¯",
            "🎉🎊🚀",
            "r/🔥dank🔥",
            "& < > \" ' ` = ; /",
        ]
        for uni in unicode_payloads:
            resp = await async_client.get("/api/v1/memes/latest", params={"source": uni})
            assert resp.status_code == 200
            assert isinstance(resp.json()["items"], list)

            resp_rand = await async_client.get("/api/v1/memes/random", params={"source": uni})
            assert resp_rand.status_code == 404

    async def test_unrecognized_extra_query_parameters(self, async_client: httpx.AsyncClient) -> None:
        """Verify extraneous query parameters are safely ignored without error."""
        resp = await async_client.get("/api/v1/memes/latest?extra_param=123&foo=bar&unknown=true")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) > 0


@pytest.mark.asyncio
class TestEmptyStateResponses:
    """Test API behavior under empty cache and empty filter matches."""

    async def test_empty_store_behavior(self, async_client: httpx.AsyncClient) -> None:
        """Verify all endpoints handle completely empty cache gracefully."""
        from app.main import app
        store: MemoryStore = app.state.memory_store
        store.clear()

        # 1. /latest on empty store
        resp_latest = await async_client.get("/api/v1/memes/latest")
        assert resp_latest.status_code == 200
        data_latest = resp_latest.json()
        assert data_latest["items"] == []
        assert data_latest["total"] == 0
        assert data_latest["has_more"] is False
        assert data_latest["limit"] == 20
        assert data_latest["offset"] == 0

        # 2. /trending on empty store
        resp_trending = await async_client.get("/api/v1/memes/trending")
        assert resp_trending.status_code == 200
        data_trending = resp_trending.json()
        assert data_trending["items"] == []
        assert data_trending["total"] == 0
        assert data_trending["has_more"] is False

        # 3. /random on empty store -> 404
        resp_random = await async_client.get("/api/v1/memes/random")
        assert resp_random.status_code == 404
        assert "detail" in resp_random.json()

        # 4. /sources on empty store -> 200 OK with sources list
        resp_sources = await async_client.get("/api/v1/sources")
        assert resp_sources.status_code == 200
        sources = resp_sources.json()
        assert isinstance(sources, list)
        assert len(sources) > 0
        assert all(s["item_count"] == 0 for s in sources)

        # 5. /health on empty store -> 200 OK
        resp_health = await async_client.get("/health")
        assert resp_health.status_code == 200
        health = resp_health.json()
        assert health["total_memes"] == 0
        assert health["status"] in ("ok", "degraded")

    async def test_zero_match_filter_behavior(self, async_client: httpx.AsyncClient) -> None:
        """Verify zero-match filter queries return empty list for latest/trending and 404 for random."""
        from app.main import app
        store: MemoryStore = app.state.memory_store
        memes = _create_mock_memes(50)
        store.clear()
        store.upsert_memes(memes)

        # Unmatched source
        resp_latest = await async_client.get("/api/v1/memes/latest?source=nonexistent_community_9999")
        assert resp_latest.status_code == 200
        assert resp_latest.json()["items"] == []
        assert resp_latest.json()["total"] == 0
        assert resp_latest.json()["has_more"] is False

        resp_trending = await async_client.get("/api/v1/memes/trending?source=nonexistent_community_9999")
        assert resp_trending.status_code == 200
        assert resp_trending.json()["items"] == []
        assert resp_trending.json()["total"] == 0

        resp_random = await async_client.get("/api/v1/memes/random?source=nonexistent_community_9999")
        assert resp_random.status_code == 404

    async def test_offset_exceeding_total_items(self, async_client: httpx.AsyncClient) -> None:
        """Verify offset >= total returns empty list with has_more=False."""
        from app.main import app
        store: MemoryStore = app.state.memory_store
        memes = _create_mock_memes(30)
        store.clear()
        store.upsert_memes(memes)

        for offset in [30, 31, 1000]:
            resp = await async_client.get(f"/api/v1/memes/latest?offset={offset}&limit=10&nsfw=true")
            assert resp.status_code == 200
            data = resp.json()
            assert data["items"] == []
            assert data["total"] == 30
            assert data["has_more"] is False


@pytest.mark.asyncio
class TestHighConcurrencyBurstRequests:
    """Test API behavior under high-concurrency burst HTTP traffic."""

    async def test_burst_concurrent_reads(self, async_client: httpx.AsyncClient) -> None:
        """Send 200 concurrent HTTP requests across mixed read endpoints simultaneously."""
        from app.main import app
        store: MemoryStore = app.state.memory_store
        memes = _create_mock_memes(200)
        store.clear()
        store.upsert_memes(memes)

        endpoints = [
            "/api/v1/memes/latest?limit=10",
            "/api/v1/memes/latest?source=reddit&nsfw=true",
            "/api/v1/memes/trending?limit=15&time_window=24h",
            "/api/v1/memes/random",
            "/api/v1/memes/random?source=reddit",
            "/api/v1/sources",
            "/health",
            "/api/v1/memes/latest?offset=10&limit=5",
        ]

        total_requests = 200
        tasks = []
        for i in range(total_requests):
            ep = endpoints[i % len(endpoints)]
            tasks.append(async_client.get(ep))

        t0 = time.perf_counter()
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.perf_counter() - t0

        assert len(responses) == total_requests

        status_codes = []
        errors = []
        for r in responses:
            if isinstance(r, Exception):
                errors.append(str(r))
            else:
                status_codes.append(r.status_code)

        assert not errors, f"Exceptions occurred during concurrent burst: {errors}"
        # All requests should return 200 OK
        assert all(code == 200 for code in status_codes), f"Non-200 responses found: {set(status_codes)}"
        print(f"\n[BURST CONCURRENCY] 200 requests completed in {total_time * 1000.0:.2f}ms (avg {total_time/200*1000.0:.2f}ms/req)")

    async def test_concurrent_reads_during_active_writes(self, async_client: httpx.AsyncClient) -> None:
        """Verify API handles concurrent HTTP read requests while background upserts are occurring."""
        from app.main import app
        store: MemoryStore = app.state.memory_store
        store.clear()
        store.upsert_memes(_create_mock_memes(100))

        stop_writes = False

        async def writer_task() -> int:
            write_count = 0
            while not stop_writes:
                batch = _create_mock_memes(20, now=time.time())
                store.upsert_memes(batch)
                write_count += 1
                await asyncio.sleep(0.005)
            return write_count

        writer = asyncio.create_task(writer_task())

        # Perform 100 concurrent reads while writer is active
        tasks = [
            async_client.get("/api/v1/memes/latest?limit=20&nsfw=true") for _ in range(50)
        ] + [
            async_client.get("/api/v1/memes/trending?limit=20&nsfw=true") for _ in range(50)
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)
        stop_writes = True
        num_writes = await writer

        for r in responses:
            assert not isinstance(r, Exception)
            assert r.status_code == 200
            items = r.json()["items"]
            # Verify ordering invariant even amidst writes
            if "latest" in str(r.url):
                for i in range(len(items) - 1):
                    assert items[i]["created_at"] >= items[i + 1]["created_at"]

        print(f"\n[READ-WRITE CONCURRENCY] 100 reads succeeded alongside {num_writes} dynamic write batches.")


@pytest.mark.asyncio
class TestApiReadLatency:
    """Benchmark read endpoint response latencies under realistic cache workloads."""

    async def test_http_endpoint_latencies_on_populated_store(self, async_client: httpx.AsyncClient) -> None:
        """Measure HTTP round-trip latencies via ASGI transport across all endpoints."""
        from app.main import app
        store: MemoryStore = app.state.memory_store
        memes = _create_mock_memes(500)
        store.clear()
        store.upsert_memes(memes)

        endpoints = [
            ("/api/v1/memes/latest", "latest_default"),
            ("/api/v1/memes/trending", "trending_default"),
            ("/api/v1/memes/random", "random_default"),
            ("/api/v1/sources", "sources_list"),
            ("/health", "health_check"),
        ]

        results = {}
        iterations = 100

        for path, label in endpoints:
            latencies = []
            for _ in range(iterations):
                t0 = time.perf_counter()
                resp = await async_client.get(path)
                dt_ms = (time.perf_counter() - t0) * 1000.0
                assert resp.status_code == 200
                latencies.append(dt_ms)

            mean_lat = statistics.mean(latencies)
            p95_lat = statistics.quantiles(latencies, n=20)[18]
            results[label] = {"mean": mean_lat, "p95": p95_lat}

        print("\n[HTTP ASGI LATENCY PROFILE (100 iterations/endpoint)]:")
        for k, v in results.items():
            print(f"  - {k:20s}: mean={v['mean']:.3f}ms, P95={v['p95']:.3f}ms")

        # HTTP ASGI transport overhead in python is typically ~0.3-2.0ms
        for k, v in results.items():
            assert v["mean"] < 10.0, f"Endpoint {k} mean latency {v['mean']:.2f}ms was excessively slow (>10ms)"

    async def test_pure_memory_store_read_latency_sub_millisecond(self) -> None:
        """Measure pure in-memory cache lookup latency excluding HTTP ASGI stack."""
        store = MemoryStore()
        memes = _create_mock_memes(1000)
        store.upsert_memes(memes)

        iterations = 500

        # Benchmark get_latest
        lats_latest = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            items, total = store.get_latest(limit=20, offset=0)
            lats_latest.append((time.perf_counter() - t0) * 1000.0)

        # Benchmark get_trending
        lats_trending = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            items, total = store.get_trending(limit=20, offset=0)
            lats_trending.append((time.perf_counter() - t0) * 1000.0)

        # Benchmark get_random
        lats_random = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            item = store.get_random()
            lats_random.append((time.perf_counter() - t0) * 1000.0)

        mean_latest = statistics.mean(lats_latest)
        mean_trending = statistics.mean(lats_trending)
        mean_random = statistics.mean(lats_random)

        print(
            f"\n[PURE CACHE READ LATENCY (1,000 items, 500 iter)] "
            f"latest: {mean_latest:.4f}ms | trending: {mean_trending:.4f}ms | random: {mean_random:.4f}ms"
        )

        assert mean_latest < 1.0, f"Latest read latency {mean_latest:.4f}ms exceeded 1.0ms"
        assert mean_trending < 1.0, f"Trending read latency {mean_trending:.4f}ms exceeded 1.0ms"
        assert mean_random < 1.0, f"Random read latency {mean_random:.4f}ms exceeded 1.0ms"


@pytest.mark.asyncio
class TestOpenApiDocumentationIntegrity:
    """Verify OpenAPI 3.x schema generation and documentation endpoints."""

    async def test_openapi_json_structure(self, async_client: httpx.AsyncClient) -> None:
        """Verify /openapi.json returns valid OpenAPI 3.x specification with all required routes."""
        resp = await async_client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()

        assert schema.get("openapi", "").startswith("3.")
        assert "info" in schema
        assert schema["info"]["title"] == "Meme Tracker API"
        assert "paths" in schema

        paths = schema["paths"]
        expected_endpoints = [
            "/api/v1/memes/latest",
            "/api/v1/memes/trending",
            "/api/v1/memes/random",
            "/api/v1/sources",
            "/health",
            "/",
        ]
        for ep in expected_endpoints:
            assert ep in paths, f"Expected endpoint {ep} missing from OpenAPI paths"
            assert "get" in paths[ep], f"GET method missing for {ep}"

    async def test_swagger_ui_and_redoc_endpoints(self, async_client: httpx.AsyncClient) -> None:
        """Verify /docs (Swagger) and /redoc return HTTP 200 with HTML documentation."""
        resp_docs = await async_client.get("/docs")
        assert resp_docs.status_code == 200
        assert "swagger-ui" in resp_docs.text.lower() or "swagger" in resp_docs.text.lower()

        resp_redoc = await async_client.get("/redoc")
        assert resp_redoc.status_code == 200
        assert "redoc" in resp_redoc.text.lower()
