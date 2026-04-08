"""E2E smoke tests — health check and basic API surface.

Requires: FASTAPI_URL env var pointing to a running backend.
    FASTAPI_URL=http://127.0.0.1:7123 uv run pytest -m e2e tests/e2e/test_misc_e2e.py --tb=long
"""

import httpx
import pytest


@pytest.mark.e2e
class TestMiscE2E:
    async def test_health_check_returns_200(self, e2e_session):
        """GET /health returns HTTP 200."""
        async with httpx.AsyncClient(
            base_url=e2e_session["base_url"], timeout=10
        ) as client:
            resp = await client.get("/health")

        assert (
            resp.status_code == 200
        ), f"Health check failed: {resp.status_code} {resp.text}"

    async def test_health_check_body_has_status(self, e2e_session):
        """GET /health response body contains a 'status' field."""
        async with httpx.AsyncClient(
            base_url=e2e_session["base_url"], timeout=10
        ) as client:
            resp = await client.get("/health")

        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body, f"Missing 'status' key in health response: {body}"

    async def test_health_check_status_is_healthy(self, e2e_session):
        """GET /health response status value is 'healthy'."""
        async with httpx.AsyncClient(
            base_url=e2e_session["base_url"], timeout=10
        ) as client:
            resp = await client.get("/health")

        assert resp.status_code == 200
        assert (
            resp.json().get("status") == "healthy"
        ), f"Unexpected health status: {resp.json()}"

    async def test_unknown_route_returns_404(self, e2e_session):
        """GET on a non-existent route returns 404."""
        async with httpx.AsyncClient(
            base_url=e2e_session["base_url"], timeout=10
        ) as client:
            resp = await client.get("/this-route-does-not-exist")

        assert resp.status_code == 404
