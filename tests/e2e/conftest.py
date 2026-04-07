"""E2E test configuration and fixtures.

Set FASTAPI_URL env var to enable e2e tests:
    FASTAPI_URL=http://127.0.0.1:7123 uv run pytest -m e2e
"""

import os

import pytest


@pytest.fixture(scope="session")
def require_backend():
    """Skip all e2e tests if FASTAPI_URL is not set."""
    url = os.environ.get("FASTAPI_URL")
    if not url:
        pytest.skip("FASTAPI_URL env var not set — skipping e2e tests")
    return url


@pytest.fixture(scope="session")
def e2e_session(require_backend):
    """Return base_url and ws_url for e2e tests."""
    base_url = require_backend.rstrip("/")
    # Convert http(s):// to ws(s)://
    ws_base = base_url.replace("https://", "wss://").replace("http://", "ws://")
    return {
        "base_url": base_url,
        "ws_url": f"{ws_base}/v1/chat/stream",
    }
