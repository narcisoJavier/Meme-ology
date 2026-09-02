"""Adversarial and empirical challenge test suite for Meme Tracker API.

Milestone 3 Challenger Verification:
1. Lifespan startup/shutdown under repeated restart cycles (resource cleanup, idempotency, data persistence).
2. OpenAPI 3.x schema integrity at /openapi.json (all paths, parameters, response schemas, and $ref resolution).
3. Interactive documentation at /docs (Swagger UI) and /redoc (Redoc).
4. System health and /api/v1/sources telemetry under simulated single/all source failures and recovery.
5. Live API endpoint validation boundaries (422 for invalid limit/offset/type, 404 for random meme miss, 405 for unsupported verbs).
6. Concurrent background poller writes under heavy concurrent API reads.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import tempfile
import time
from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from app.config import get_settings
from app.ingestion.base import BaseSourceFetcher
from app.ingestion.worker import MemePollingWorker
from app.main import create_app, lifespan
from app.models.meme import MediaType, NormalizedMeme, SourcePlatform
from app.models.source import HealthResponse, SourceStatus
from app.storage.memory_store import MemoryStore
from app.storage.sqlite_store import SqliteStore


# ==============================================================================
# Helper Mock Fetchers
# ==============================================================================


class MockFailingFetcher(BaseSourceFetcher):
    """Fetcher that unconditionally fails with simulated errors."""

    def __init__(self, name: str, error_to_raise: Exception) -> None:
        super().__init__(name=name, platform=SourcePlatform.REDDIT, community="r/failing")
        self.error_to_raise = error_to_raise

    async def fetch_memes(self) -> List[NormalizedMeme]:
        raise self.error_to_raise

    def load_offline_fixtures(self) -> List[NormalizedMeme]:
        return []


class MockFlappingFetcher(BaseSourceFetcher):
    """Fetcher that fails on first attempt and succeeds on second attempt."""

    def __init__(self, name: str, success_memes: List[NormalizedMeme]) -> None:
        super().__init__(name=name, platform=SourcePlatform.KNOWYOURMEME, community="trending")
        self.success_memes = success_memes
        self.call_count = 0

    async def fetch_memes(self) -> List[NormalizedMeme]:
        self.call_count += 1
        if self.call_count == 1:
            raise ConnectionResetError("Simulated connection reset by peer")
        self.update_success(len(self.success_memes), latency_ms=45.2)
        return self.success_memes

    def load_offline_fixtures(self) -> List[NormalizedMeme]:
        return self.success_memes


# ==============================================================================
# 1. FastAPI Lifespan Startup/Shutdown Under Repeated Restart Cycles
# ==============================================================================


class TestLifespanAdversarialCycles:
    """Stress test FastAPI lifespan startup and shutdown cycles."""

    @pytest.mark.asyncio
    async def test_lifespan_repeated_restart_cycles_10x(self, temp_sqlite_db: str) -> None:
        """Verify lifespan handles 10 consecutive restart cycles cleanly without resource leakage or deadlocks."""
        test_app = FastAPI(lifespan=lifespan)
        test_app.state.sqlite_store = SqliteStore(database_path=temp_sqlite_db)
        test_app.state.memory_store = MemoryStore()

        # Seed initial meme in SQLite
        await test_app.state.sqlite_store.initialize()
        seed_meme = NormalizedMeme(
            id="seed_meme_cycle",
            title="Seed Cycle Meme",
            media_url="https://i.redd.it/cycle_seed.jpg",
            source_platform=SourcePlatform.REDDIT,
            source_community="r/memes",
            permalink="https://reddit.com/r/memes/cycle_seed",
            score=500,
            num_comments=30,
            created_at=time.time(),
        )
        await test_app.state.sqlite_store.save_memes([seed_meme])

        for cycle in range(10):
            # Create mock worker to track start/stop calls cleanly
            mock_worker = AsyncMock(spec=MemePollingWorker)
            mock_worker.start = AsyncMock()
            mock_worker.stop = AsyncMock()
            test_app.state.poller = mock_worker

            async with lifespan(test_app):
                # Verify DB initialized and cache hydrated
                assert test_app.state.memory_store.count() >= 1
                assert test_app.state.memory_store.get_by_id("seed_meme_cycle") is not None
                mock_worker.start.assert_awaited_once()

            mock_worker.stop.assert_awaited_once()

        # Clean close
        await test_app.state.sqlite_store.close()

    @pytest.mark.asyncio
    async def test_lifespan_idempotent_worker_start_stop(self, temp_sqlite_db: str) -> None:
        """Verify MemePollingWorker start and stop are idempotent and safe against repeated calls."""
        memory_store = MemoryStore()
        sqlite_store = SqliteStore(database_path=temp_sqlite_db)
        await sqlite_store.initialize()

        worker = MemePollingWorker(
            memory_store=memory_store,
            sqlite_store=sqlite_store,
            poll_interval_seconds=60.0,
            fetchers=[],
        )

        assert not worker.is_running
        await worker.start()
        assert worker.is_running
        # Second start call should be a no-op
        await worker.start()
        assert worker.is_running

        # Stop worker
        await worker.stop()
        assert not worker.is_running
        # Second stop call should be a no-op
        await worker.stop()
        assert not worker.is_running

        await sqlite_store.close()

    @pytest.mark.asyncio
    async def test_lifespan_state_persistence_across_app_instances(self, temp_sqlite_db: str) -> None:
        """Verify data saved in cycle 1 persists and hydrates cleanly in cycle 2 across distinct app instances."""
        # --- Instance 1 ---
        app1 = FastAPI(lifespan=lifespan)
        app1.state.sqlite_store = SqliteStore(database_path=temp_sqlite_db)
        app1.state.memory_store = MemoryStore()

        async with lifespan(app1):
            # Upsert new memes into app1
            new_memes = [
                NormalizedMeme(
                    id=f"persisted_meme_{i}",
                    title=f"Persisted Meme #{i}",
                    media_url=f"https://i.redd.it/persisted_{i}.png",
                    source_platform=SourcePlatform.REDDIT,
                    source_community="r/dankmemes",
                    permalink=f"https://reddit.com/r/dankmemes/p_{i}",
                    score=1000 * (i + 1),
                    num_comments=50 * (i + 1),
                    created_at=time.time() - (i * 100),
                )
                for i in range(5)
            ]
            await app1.state.sqlite_store.save_memes(new_memes)
            app1.state.memory_store.upsert_memes(new_memes)
            assert app1.state.memory_store.count() == 5

        # --- Instance 2 ---
        app2 = FastAPI(lifespan=lifespan)
        app2.state.sqlite_store = SqliteStore(database_path=temp_sqlite_db)
        app2.state.memory_store = MemoryStore()

        async with lifespan(app2):
            # Instance 2 should automatically hydrate the 5 memes from SQLite
            assert app2.state.memory_store.count() == 5
            for i in range(5):
                m = app2.state.memory_store.get_by_id(f"persisted_meme_{i}")
                assert m is not None
                assert m.title == f"Persisted Meme #{i}"

    @pytest.mark.asyncio
    async def test_lifespan_graceful_cancellation_during_inflight_task(self, temp_sqlite_db: str) -> None:
        """Verify poller task cleanly cancels and does not hang when lifespan exits during background sleep."""
        memory_store = MemoryStore()
        sqlite_store = SqliteStore(database_path=temp_sqlite_db)
        await sqlite_store.initialize()

        test_app = FastAPI(lifespan=lifespan)
        test_app.state.sqlite_store = sqlite_store
        test_app.state.memory_store = memory_store
        test_app.state.poller = MemePollingWorker(
            memory_store=memory_store,
            sqlite_store=sqlite_store,
            poll_interval_seconds=10.0,
            fetchers=[],
        )

        t0 = time.time()
        async with lifespan(test_app):
            assert test_app.state.poller.is_running
            # Brief sleep to allow worker event loop to spin
            await asyncio.sleep(0.05)

        # Shutdown should complete in < 2 seconds without hanging on 10s sleep
        duration = time.time() - t0
        assert duration < 3.0
        assert not test_app.state.poller.is_running


# ==============================================================================
# 2. OpenAPI 3.x Schema Integrity at /openapi.json
# ==============================================================================


class TestOpenApi3SchemaIntegrity:
    """Comprehensive validation of OpenAPI 3.x spec, paths, parameters, responses, and schema refs."""

    @pytest.mark.asyncio
    async def test_openapi_schema_version_and_metadata(self, async_client: httpx.AsyncClient) -> None:
        """Verify OpenAPI spec metadata: 3.x version, title, description, and tags."""
        response = await async_client.get("/openapi.json")
        assert response.status_code == 200
        spec = response.json()

        # OpenAPI 3.x check
        assert spec.get("openapi", "").startswith("3.")
        info = spec.get("info", {})
        assert "title" in info
        assert "version" in info
        assert "description" in info
        assert len(info["description"]) > 0

        # Tags check
        tags = spec.get("tags", [])
        tag_names = {t.get("name") for t in tags}
        assert "memes" in tag_names
        assert "sources" in tag_names
        assert "health" in tag_names

    @pytest.mark.asyncio
    async def test_all_expected_paths_and_methods_registered(self, async_client: httpx.AsyncClient) -> None:
        """Verify all mandatory endpoints are registered in the OpenAPI paths object."""
        response = await async_client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json().get("paths", {})

        expected_endpoints = [
            "/",
            "/health",
            "/api/v1/memes/latest",
            "/api/v1/memes/trending",
            "/api/v1/memes/random",
            "/api/v1/sources",
            "/api/v1/health",
        ]

        for endpoint in expected_endpoints:
            assert endpoint in paths, f"Endpoint {endpoint} is missing from OpenAPI paths!"
            assert "get" in paths[endpoint], f"GET method missing for {endpoint} in OpenAPI spec!"

    @pytest.mark.asyncio
    async def test_openapi_parameter_schemas_and_validation_rules(self, async_client: httpx.AsyncClient) -> None:
        """Verify query parameter types and validation constraints for meme querying endpoints."""
        response = await async_client.get("/openapi.json")
        spec = response.json()
        paths = spec.get("paths", {})

        # 1. /api/v1/memes/latest parameter validation
        latest_params = {p["name"]: p for p in paths["/api/v1/memes/latest"]["get"].get("parameters", [])}
        assert "limit" in latest_params
        assert "offset" in latest_params
        assert "source" in latest_params
        assert "nsfw" in latest_params
        assert "time_window" in latest_params

        # Validate limit constraint details
        limit_schema = latest_params["limit"].get("schema", {})
        assert limit_schema.get("type") == "integer"
        assert limit_schema.get("minimum") == 1
        assert limit_schema.get("maximum") == 100
        assert limit_schema.get("default") == 20

        # Validate offset constraint details
        offset_schema = latest_params["offset"].get("schema", {})
        assert offset_schema.get("type") == "integer"
        assert offset_schema.get("minimum") == 0
        assert offset_schema.get("default") == 0

        # Validate nsfw constraint details
        nsfw_schema = latest_params["nsfw"].get("schema", {})
        assert nsfw_schema.get("type") == "boolean"
        assert nsfw_schema.get("default") is False

        # 2. /api/v1/memes/trending parameter validation
        trending_params = {p["name"]: p for p in paths["/api/v1/memes/trending"]["get"].get("parameters", [])}
        assert "limit" in trending_params
        assert "offset" in trending_params
        assert trending_params["limit"]["schema"]["maximum"] == 100

        # 3. /api/v1/memes/random parameter validation
        random_params = {p["name"]: p for p in paths["/api/v1/memes/random"]["get"].get("parameters", [])}
        assert "source" in random_params
        assert "nsfw" in random_params

    @pytest.mark.asyncio
    async def test_openapi_response_status_codes_and_models(self, async_client: httpx.AsyncClient) -> None:
        """Verify response status codes (200, 404, 422) and content schemas across all endpoints."""
        response = await async_client.get("/openapi.json")
        spec = response.json()
        paths = spec.get("paths", {})

        # /api/v1/memes/latest: must have 200 and 422
        latest_resps = paths["/api/v1/memes/latest"]["get"].get("responses", {})
        assert "200" in latest_resps
        assert "422" in latest_resps
        assert "application/json" in latest_resps["200"].get("content", {})

        # /api/v1/memes/trending: must have 200 and 422
        trending_resps = paths["/api/v1/memes/trending"]["get"].get("responses", {})
        assert "200" in trending_resps
        assert "422" in trending_resps

        # /api/v1/memes/random: must have 200, 404, and 422
        random_resps = paths["/api/v1/memes/random"]["get"].get("responses", {})
        assert "200" in random_resps
        assert "404" in random_resps
        assert "422" in random_resps

        # /api/v1/sources: must have 200
        sources_resps = paths["/api/v1/sources"]["get"].get("responses", {})
        assert "200" in sources_resps

        # /health: must have 200
        health_resps = paths["/health"]["get"].get("responses", {})
        assert "200" in health_resps

    @pytest.mark.asyncio
    async def test_openapi_all_schema_refs_are_resolvable(self, async_client: httpx.AsyncClient) -> None:
        """Adversarial check: extract every '$ref' across the entire OpenAPI spec and verify it points to a valid component."""
        response = await async_client.get("/openapi.json")
        spec = response.json()
        schemas = spec.get("components", {}).get("schemas", {})

        refs_found: List[str] = []

        def _collect_refs(node: Any) -> None:
            if isinstance(node, dict):
                for k, v in node.items():
                    if k == "$ref" and isinstance(v, str):
                        refs_found.append(v)
                    else:
                        _collect_refs(v)
            elif isinstance(node, list):
                for item in node:
                    _collect_refs(item)

        _collect_refs(spec)
        assert len(refs_found) > 0, "No $ref schemas found in OpenAPI spec!"

        for ref in refs_found:
            assert ref.startswith("#/components/schemas/"), f"Unexpected ref format: {ref}"
            schema_name = ref.replace("#/components/schemas/", "")
            assert schema_name in schemas, f"Dangling reference: '{ref}' not found in components.schemas!"


# ==============================================================================
# 3. Interactive Documentation Endpoints (/docs and /redoc)
# ==============================================================================


class TestInteractiveDocsEndpoints:
    """Validate HTML rendering and structure of Swagger UI and Redoc endpoints."""

    @pytest.mark.asyncio
    async def test_swagger_ui_docs_html_and_assets(self, async_client: httpx.AsyncClient) -> None:
        """Verify GET /docs returns HTTP 200 text/html with Swagger UI JavaScript/CSS bundles."""
        response = await async_client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        content = response.text

        # Verify Swagger bundle indicators
        assert "swagger" in content.lower()
        assert "openapi.json" in content
        assert "<!doctype html>" in content.lower() or "<html" in content.lower()

    @pytest.mark.asyncio
    async def test_redoc_ui_html_and_assets(self, async_client: httpx.AsyncClient) -> None:
        """Verify GET /redoc returns HTTP 200 text/html with Redoc library bundles."""
        response = await async_client.get("/redoc")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        content = response.text

        # Verify Redoc bundle indicators
        assert "redoc" in content.lower()
        assert "openapi.json" in content

    @pytest.mark.asyncio
    async def test_docs_head_and_cors_options(self, async_client: httpx.AsyncClient) -> None:
        """Verify HEAD on docs and preflight CORS OPTIONS requests."""
        # HEAD /docs
        head_docs = await async_client.head("/docs")
        assert head_docs.status_code == 200
        assert "text/html" in head_docs.headers.get("content-type", "")

        # HEAD /openapi.json
        head_openapi = await async_client.head("/openapi.json")
        assert head_openapi.status_code == 200
        assert "application/json" in head_openapi.headers.get("content-type", "")

        # CORS preflight OPTIONS request
        cors_headers = {
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        }
        options_resp = await async_client.options("/api/v1/memes/latest", headers=cors_headers)
        assert options_resp.status_code == 200
        assert "access-control-allow-origin" in options_resp.headers

    @pytest.mark.asyncio
    async def test_root_endpoint_provides_documentation_links(self, async_client: httpx.AsyncClient) -> None:
        """Verify GET / root endpoint returns service identification and explicit links to docs."""
        response = await async_client.get("/")
        assert response.status_code == 200
        data = response.json()

        assert "name" in data
        assert data.get("docs_url") == "/docs"
        assert data.get("openapi_url") == "/openapi.json"
        assert data.get("health_url") == "/health"


# ==============================================================================
# 4. Source Status and Health Under Simulated Background Polling Errors
# ==============================================================================


class TestSourceMonitoringAndHealthUnderPollingErrors:
    """Stress test /api/v1/sources and /health telemetry under simulated failures, degraded states, and recovery."""

    @pytest.mark.asyncio
    async def test_single_source_failure_isolation_and_degraded_health(self) -> None:
        """When 1 source fails (e.g. Rate limit 429) and others succeed, health should report 'degraded'."""
        memory_store = MemoryStore()

        # Build 1 failing fetcher and 1 succeeding fetcher
        failing_fetcher = MockFailingFetcher(
            name="reddit:r/memes",
            error_to_raise=RuntimeError("HTTP 429 Too Many Requests"),
        )
        flapping_fetcher = MockFlappingFetcher(
            name="knowyourmeme:trending",
            success_memes=[
                NormalizedMeme(
                    id="kym_mock_01",
                    title="KYM Successful Ingestion",
                    media_url="https://i.kym-cdn.com/kym01.jpg",
                    source_platform=SourcePlatform.KNOWYOURMEME,
                    source_community="trending",
                    permalink="https://knowyourmeme.com/memes/mock01",
                    score=2000,
                    num_comments=100,
                    created_at=time.time(),
                )
            ],
        )

        worker = MemePollingWorker(
            memory_store=memory_store,
            fetchers=[failing_fetcher, flapping_fetcher],
        )

        # Cycle 1: Failing fetcher raises RuntimeError; flapping fetcher raises ConnectionResetError
        await worker.poll_once()

        # In cycle 1, 2 sources failed out of 7 total configured -> status is 'degraded'
        health1 = memory_store.get_health_status()
        assert health1.status == "degraded"
        assert health1.healthy_sources == 5  # 5 default sources still ok

        # Cycle 2: Flapping fetcher succeeds; failing fetcher still fails
        await worker.poll_once()

        health2 = memory_store.get_health_status()
        assert health2.status == "degraded"
        assert health2.healthy_sources == 6  # 5 default + 1 flapping succeeded
        assert health2.total_memes >= 1

        # Check /api/v1/sources status breakdown
        sources = memory_store.get_sources_status()
        status_by_name = {s.name: s for s in sources}

        assert "reddit:r/memes" in status_by_name
        assert status_by_name["reddit:r/memes"].status in ("failing", "degraded", "error")
        assert "429" in (status_by_name["reddit:r/memes"].last_error or "")
        assert status_by_name["knowyourmeme:trending"].status == "ok"
        assert status_by_name["knowyourmeme:trending"].item_count == 1

    @pytest.mark.asyncio
    async def test_all_sources_failure_does_not_crash_cache_reads(self) -> None:
        """When all background feeds fail, /health reports unhealthy but cached memes remain queryable."""
        memory_store = MemoryStore()

        # Pre-seed 3 memes in cache
        cached_memes = [
            NormalizedMeme(
                id=f"cached_safe_{i}",
                title=f"Safe Cached Meme {i}",
                media_url=f"https://i.redd.it/cached_{i}.jpg",
                source_platform=SourcePlatform.REDDIT,
                source_community="r/memes",
                permalink=f"https://reddit.com/r/memes/c_{i}",
                score=5000,
                num_comments=150,
                created_at=time.time() - (i * 60),
            )
            for i in range(3)
        ]
        memory_store.upsert_memes(cached_memes)

        # Mark all registered sources in memory store as degraded/failing
        for s in memory_store.get_sources_status():
            memory_store.update_source_status(
                SourceStatus(
                    id=s.id,
                    name=s.name,
                    platform=s.platform,
                    community=s.community,
                    status="failing",
                    last_error="Simulated upstream outage",
                )
            )

        # Set up worker with crashing fetchers
        failing_1 = MockFailingFetcher(name="reddit:r/memes", error_to_raise=TimeoutError("Connection timed out"))
        failing_2 = MockFailingFetcher(name="knowyourmeme:confirmed", error_to_raise=ValueError("Corrupt XML feed"))

        worker = MemePollingWorker(
            memory_store=memory_store,
            fetchers=[failing_1, failing_2],
        )

        # Execute poll_once cycle with failures
        result = await worker.poll_once()
        assert result["status"] == "ok"
        assert result["new_items"] == 0

        # Health status should report unhealthy because healthy_sources == 0
        health = memory_store.get_health_status()
        assert health.status == "unhealthy"
        assert health.healthy_sources == 0
        assert health.total_memes == 3

        # Memes can still be queried reliably
        items, total = memory_store.get_latest(limit=10)
        assert total == 3
        assert len(items) == 3

        rand_meme = memory_store.get_random()
        assert rand_meme is not None

    @pytest.mark.asyncio
    async def test_full_source_recovery_restores_health_status_to_ok(self) -> None:
        """Verify that when a failed source recovers, service health returns to 'ok'."""
        memory_store = MemoryStore()

        # Mark all sources as failing initially
        for s in memory_store.get_sources_status():
            memory_store.update_source_status(
                SourceStatus(
                    id=s.id,
                    name=s.name,
                    platform=s.platform,
                    community=s.community,
                    status="failing",
                    last_error="Temporary network failure",
                )
            )

        h1 = memory_store.get_health_status()
        assert h1.status == "unhealthy"
        assert h1.healthy_sources == 0

        # Now simulate all sources recovering
        for s in memory_store.get_sources_status():
            memory_store.update_source_status(
                SourceStatus(
                    id=s.id,
                    name=s.name,
                    platform=s.platform,
                    community=s.community,
                    status="ok",
                    last_synced_at=time.time(),
                    latency_ms=35.0,
                    item_count=10,
                )
            )

        h2 = memory_store.get_health_status()
        assert h2.status == "ok"
        assert h2.healthy_sources == h2.total_sources

        # Check source metrics
        for src in memory_store.get_sources_status():
            assert src.status == "ok"
            assert src.last_synced_at is not None
            assert src.latency_ms is not None

    @pytest.mark.asyncio
    async def test_http_api_sources_and_health_integration(self, async_client: httpx.AsyncClient) -> None:
        """Verify GET /api/v1/sources and GET /health via HTTP client match schema and data."""
        # 1. Test GET /health
        health_resp = await async_client.get("/health")
        assert health_resp.status_code == 200
        health_data = health_resp.json()
        parsed_health = HealthResponse(**health_data)
        assert parsed_health.status in ("ok", "degraded", "unhealthy")
        assert parsed_health.uptime_seconds >= 0.0
        assert parsed_health.total_memes is not None

        # 2. Test GET /api/v1/sources
        sources_resp = await async_client.get("/api/v1/sources")
        assert sources_resp.status_code == 200
        sources_data = sources_resp.json()
        assert isinstance(sources_data, list)
        assert len(sources_data) > 0

        # Validate each item matches SourceStatus schema
        for src in sources_data:
            parsed_src = SourceStatus(**src)
            assert parsed_src.name
            assert parsed_src.platform in (SourcePlatform.REDDIT, SourcePlatform.KNOWYOURMEME, "reddit", "knowyourmeme")
            assert parsed_src.item_count >= 0


# ==============================================================================
# 5. Live API Endpoint Boundary Validation & Error Responses
# ==============================================================================


class TestLiveApiQueryValidationAdversarial:
    """Stress test query parameter validation limits, 404s, 422s, and 405s on live HTTP client."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("invalid_limit", [0, -1, -50, 101, 500, "not_an_int", "10.5"])
    async def test_latest_and_trending_reject_invalid_limits_with_422(
        self, async_client: httpx.AsyncClient, invalid_limit: Any
    ) -> None:
        """Verify /latest and /trending return 422 Unprocessable Entity for invalid limit inputs."""
        res1 = await async_client.get(f"/api/v1/memes/latest?limit={invalid_limit}")
        assert res1.status_code == 422
        err1 = res1.json()
        assert "detail" in err1

        res2 = await async_client.get(f"/api/v1/memes/trending?limit={invalid_limit}")
        assert res2.status_code == 422

    @pytest.mark.asyncio
    @pytest.mark.parametrize("valid_limit", [1, 20, 50, 100])
    async def test_latest_accepts_valid_boundary_limits(
        self, async_client: httpx.AsyncClient, valid_limit: int
    ) -> None:
        """Verify boundary limit values 1 and 100 are accepted and return 200 OK."""
        res = await async_client.get(f"/api/v1/memes/latest?limit={valid_limit}")
        assert res.status_code == 200
        data = res.json()
        assert data["limit"] == valid_limit
        assert len(data["items"]) <= valid_limit

    @pytest.mark.asyncio
    @pytest.mark.parametrize("invalid_offset", [-1, -100, "abc", "0.5"])
    async def test_latest_rejects_negative_and_malformed_offsets_with_422(
        self, async_client: httpx.AsyncClient, invalid_offset: Any
    ) -> None:
        """Verify /latest returns 422 for negative or non-integer offset."""
        res = await async_client.get(f"/api/v1/memes/latest?offset={invalid_offset}")
        assert res.status_code == 422

    @pytest.mark.asyncio
    async def test_offset_beyond_total_returns_empty_items(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Verify offset exceeding dataset size returns empty items list, total count, and has_more=False."""
        res = await async_client.get("/api/v1/memes/latest?offset=9999")
        assert res.status_code == 200
        data = res.json()
        assert data["items"] == []
        assert data["offset"] == 9999
        assert data["has_more"] is False

    @pytest.mark.asyncio
    async def test_random_meme_returns_404_when_no_match(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Verify /random returns HTTP 404 when filter criteria matches 0 items."""
        res = await async_client.get("/api/v1/memes/random?source=nonexistent_subreddit_999")
        assert res.status_code == 404
        data = res.json()
        assert "detail" in data
        assert "no memes found" in data["detail"].lower()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("unsupported_method,endpoint", [
        ("post", "/api/v1/memes/latest"),
        ("delete", "/api/v1/memes/trending"),
        ("put", "/api/v1/memes/random"),
        ("patch", "/api/v1/sources"),
        ("delete", "/health"),
    ])
    async def test_unsupported_http_methods_return_405(
        self, async_client: httpx.AsyncClient, unsupported_method: str, endpoint: str
    ) -> None:
        """Verify unsupported HTTP verbs on read-only endpoints return 405 Method Not Allowed."""
        client_func = getattr(async_client, unsupported_method)
        res = await client_func(endpoint)
        assert res.status_code == 405


# ==============================================================================
# 6. Concurrency Under Poller Ingestion & Concurrent API Reads
# ==============================================================================


class TestConcurrentPollerAndApiReads:
    """Stress test memory store and API routes under high concurrent read/write loads."""

    @pytest.mark.asyncio
    async def test_50_concurrent_api_reads_during_active_upserts(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Hammer the API with 50 concurrent requests while simulated poller worker writes memes."""
        from app.main import app

        store: MemoryStore = app.state.memory_store

        # Background writer coroutine
        async def _background_writer() -> None:
            for i in range(20):
                new_item = NormalizedMeme(
                    id=f"concurrent_test_meme_{i}",
                    title=f"Concurrent Test Meme {i}",
                    media_url=f"https://i.redd.it/concur_{i}.jpg",
                    source_platform=SourcePlatform.REDDIT,
                    source_community="r/memes",
                    permalink=f"https://reddit.com/r/memes/c_{i}",
                    score=100 + i * 10,
                    num_comments=5 + i,
                    created_at=time.time() - (i * 10),
                )
                store.upsert_memes([new_item])
                await asyncio.sleep(0.01)

        # Reader coroutines
        async def _read_endpoint(path: str) -> int:
            r = await async_client.get(path)
            return r.status_code

        writer_task = asyncio.create_task(_background_writer())

        endpoints = [
            "/api/v1/memes/latest?limit=10",
            "/api/v1/memes/trending?limit=10",
            "/api/v1/memes/random",
            "/api/v1/sources",
            "/health",
        ]

        # Dispatch 50 concurrent requests
        reader_tasks = [_read_endpoint(random.choice(endpoints)) for _ in range(50)]
        results = await asyncio.gather(*reader_tasks)
        await writer_task

        # Verify all 50 requests returned HTTP 200 without race conditions or locks hanging
        assert all(code == 200 for code in results)
        assert len(results) == 50
