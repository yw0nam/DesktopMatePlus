"""E2E tests for LTM (Long-Term Memory) HTTP API.

Requires: FASTAPI_URL env var pointing to a running backend.
    FASTAPI_URL=http://127.0.0.1:7123 uv run pytest -m e2e tests/e2e/test_ltm_e2e.py --tb=long

Note: LTM requires Qdrant. Tests skip gracefully if LTM is not available (503).
"""

import asyncio

import httpx
import pytest

USER_ID = "e2e-user"
AGENT_ID = "e2e-agent"
_LTM_UNAVAILABLE_MSG = "LTM service not available (503) — Qdrant may not be running"
_LTM_TIMEOUT = 90  # mem0 add() involves LLM + embedding + vector/graph store writes
_ADD_MEMORY_RETRIES = (
    2  # mem0 add can fail transiently (embedding → None, graph KeyError)
)


async def _add_memory_with_retry(
    client: httpx.AsyncClient,
    retries: int = _ADD_MEMORY_RETRIES,
) -> httpx.Response:
    """POST add_memory with retry for transient mem0 failures."""
    for attempt in range(retries):
        resp = await client.post(
            "/v1/ltm/add_memory",
            json={
                "user_id": USER_ID,
                "agent_id": AGENT_ID,
                "memory_dict": "E2E test memory: the user prefers concise answers.",
            },
        )
        if resp.status_code in (200, 503):
            return resp
        if attempt < retries - 1:
            await asyncio.sleep(2)
    return resp


@pytest.mark.e2e
class TestLtmE2E:
    async def test_ltm_add_memory(self, e2e_session):
        """POST /v1/ltm/add_memory stores a memory entry."""
        base_url = e2e_session["base_url"]

        async with httpx.AsyncClient(base_url=base_url, timeout=_LTM_TIMEOUT) as client:
            resp = await _add_memory_with_retry(client)

        if resp.status_code == 503:
            pytest.skip(_LTM_UNAVAILABLE_MSG)

        assert (
            resp.status_code == 200
        ), f"add_memory failed: {resp.status_code} {resp.text}"

    async def test_ltm_search_memory_returns_results(self, e2e_session):
        """POST /v1/ltm/search_memory returns success=True with results."""
        base_url = e2e_session["base_url"]

        async with httpx.AsyncClient(base_url=base_url, timeout=_LTM_TIMEOUT) as client:
            # Store first (retry for transient mem0 failures)
            add_resp = await _add_memory_with_retry(client)
            if add_resp.status_code == 503:
                pytest.skip(_LTM_UNAVAILABLE_MSG)
            assert (
                add_resp.status_code == 200
            ), f"add_memory failed after retries: {add_resp.status_code} {add_resp.text}"

            # Search
            resp = await client.post(
                "/v1/ltm/search_memory",
                json={
                    "user_id": USER_ID,
                    "agent_id": AGENT_ID,
                    "query": "concise answers",
                },
            )

        if resp.status_code == 503:
            pytest.skip(_LTM_UNAVAILABLE_MSG)

        assert (
            resp.status_code == 200
        ), f"search_memory failed: {resp.status_code} {resp.text}"
        result = resp.json()
        assert (
            result.get("success") is True
        ), f"search_memory returned success=False: {result}"
        memories = (
            result.get("results")
            or result.get("memories")
            or result.get("result", {}).get("results")
            or []
        )
        assert (
            len(memories) > 0
        ), f"search_memory returned success=True but no results after add: {result}"

    async def test_ltm_search_memory_structure(self, e2e_session):
        """search_memory response has expected top-level keys."""
        base_url = e2e_session["base_url"]

        async with httpx.AsyncClient(base_url=base_url, timeout=_LTM_TIMEOUT) as client:
            resp = await client.post(
                "/v1/ltm/search_memory",
                json={
                    "user_id": USER_ID,
                    "agent_id": AGENT_ID,
                    "query": "test query",
                },
            )

        if resp.status_code == 503:
            pytest.skip(_LTM_UNAVAILABLE_MSG)

        assert resp.status_code == 200
        result = resp.json()
        assert (
            result.get("success") is True
        ), f"search_memory returned success != True: {result}"
