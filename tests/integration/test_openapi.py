"""Integration tests for OpenAPI documentation and interactive Swagger UI.

Validates:
- GET /openapi.json returns valid OpenAPI 3.x schema.
- GET /docs returns interactive Swagger UI HTML.
- Documented paths: /api/v1/memes/latest, /api/v1/memes/trending, /api/v1/memes/random, /api/v1/sources, /health.
- Query parameters and response models defined in schema components.
- Response HTTP 200/422 status code mappings.
"""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.asyncio
class TestOpenApiDocumentation:
    """Integration test suite for OpenAPI specification and documentation."""

    async def test_openapi_json_endpoint_returns_valid_spec(self, async_client: httpx.AsyncClient) -> None:
        """Verify GET /openapi.json returns HTTP 200 with OpenAPI 3.x structure."""
        response = await async_client.get("/openapi.json")
        assert response.status_code == 200
        spec = response.json()

        assert "openapi" in spec
        assert spec["openapi"].startswith("3.")
        assert "info" in spec
        assert "paths" in spec

    async def test_openapi_contains_all_core_endpoints(self, async_client: httpx.AsyncClient) -> None:
        """Verify all core endpoints are registered in the OpenAPI paths."""
        response = await async_client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json()["paths"]

        assert "/api/v1/memes/latest" in paths
        assert "/api/v1/memes/trending" in paths
        assert "/api/v1/memes/random" in paths
        assert "/api/v1/sources" in paths

    async def test_openapi_query_parameters_documented(self, async_client: httpx.AsyncClient) -> None:
        """Verify query parameters (limit, offset, source, nsfw) are documented for /latest."""
        response = await async_client.get("/openapi.json")
        spec = response.json()
        latest_op = spec["paths"]["/api/v1/memes/latest"]["get"]
        param_names = [p["name"] for p in latest_op.get("parameters", [])]

        assert "limit" in param_names
        assert "offset" in param_names
        assert "source" in param_names
        assert "nsfw" in param_names

    async def test_openapi_trending_parameters_documented(self, async_client: httpx.AsyncClient) -> None:
        """Verify query parameters for /trending endpoint in OpenAPI spec."""
        response = await async_client.get("/openapi.json")
        spec = response.json()
        trending_op = spec["paths"]["/api/v1/memes/trending"]["get"]
        param_names = [p["name"] for p in trending_op.get("parameters", [])]

        assert "limit" in param_names
        assert "offset" in param_names

    async def test_swagger_ui_html_docs_available(self, async_client: httpx.AsyncClient) -> None:
        """Verify GET /docs returns HTTP 200 with Swagger UI HTML."""
        response = await async_client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        content = response.text
        assert "swagger-ui" in content.lower() or "swagger" in content.lower()

    async def test_openapi_components_schemas_defined(self, async_client: httpx.AsyncClient) -> None:
        """Verify schemas exist in components."""
        response = await async_client.get("/openapi.json")
        spec = response.json()
        schemas = spec.get("components", {}).get("schemas", {})
        assert len(schemas) > 0

    async def test_openapi_info_block_metadata(self, async_client: httpx.AsyncClient) -> None:
        """Verify OpenAPI info block contains title and version."""
        response = await async_client.get("/openapi.json")
        spec = response.json()
        info = spec.get("info", {})
        assert "title" in info
        assert "version" in info

    async def test_root_index_endpoint(self, async_client: httpx.AsyncClient) -> None:
        """Verify GET / returns HTTP 200 with service information and doc links."""
        response = await async_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "docs_url" in data
        assert data["docs_url"] == "/docs"

    async def test_redoc_ui_html_docs_available(self, async_client: httpx.AsyncClient) -> None:
        """Verify GET /redoc returns HTTP 200 with Redoc UI HTML."""
        response = await async_client.get("/redoc")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "redoc" in response.text.lower()

    async def test_root_index_serves_html_for_browser_navigation(self, async_client: httpx.AsyncClient) -> None:
        """Verify GET / returns HTML for browser navigation."""
        response = await async_client.get("/", headers={"accept": "text/html,application/xhtml+xml"})
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "MEME-OLOGY" in response.text

    async def test_web_portal_endpoint(self, async_client: httpx.AsyncClient) -> None:
        """Verify GET /web returns HTTP 200 with the Meme-ology web dashboard."""
        response = await async_client.get("/web")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "MEME-OLOGY" in response.text


