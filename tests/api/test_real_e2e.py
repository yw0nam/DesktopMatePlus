"""Real E2E integration tests for delegation flow.

Tests the actual FastAPI backend and NanoClaw HTTP channel without mocks.

Prerequisites:
  1. Backend running: uvicorn src.main:app --port 5500
  2. NanoClaw running with HTTP_PORT=3001:
       HTTP_PORT=3001 npm run dev   (in nanoclaw/)

Environment variables (with defaults):
  BACKEND_URL=http://127.0.0.1:5500
  NANOCLAW_HTTP_PORT=3001
"""

import os
import uuid

import httpx
import pytest

# ── Service endpoints ─────────────────────────────────────────────────────────

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:5500")
NANOCLAW_HTTP_PORT = int(os.getenv("NANOCLAW_HTTP_PORT", "3001"))
NANOCLAW_WEBHOOK_URL = f"http://127.0.0.1:{NANOCLAW_HTTP_PORT}/api/webhooks/fastapi"

# Test identifiers
USER_ID = "e2e-test-user"
AGENT_ID = "e2e-test-agent"


# ── Availability helpers ──────────────────────────────────────────────────────


def _is_backend_up() -> bool:
    try:
        r = httpx.get(f"{BACKEND_URL}/", timeout=5.0)
        return r.status_code == 200
    except (httpx.TransportError, httpx.TimeoutException):
        return False


def _is_nanoclaw_up() -> bool:
    """NanoClaw has no health endpoint; probe the webhook path with an empty POST."""
    try:
        r = httpx.post(
            NANOCLAW_WEBHOOK_URL,
            json={},
            timeout=3.0,
        )
        # 400 (bad payload) means the server is up and responding
        return r.status_code in (200, 202, 400, 404)
    except httpx.TransportError:
        return False


requires_backend = pytest.mark.skipif(
    not _is_backend_up(),
    reason=f"Backend not reachable at {BACKEND_URL}",
)

requires_nanoclaw = pytest.mark.skipif(
    not _is_nanoclaw_up(),
    reason=(
        f"NanoClaw HTTP channel not reachable at port {NANOCLAW_HTTP_PORT}. "
        "Start NanoClaw with: HTTP_PORT=3001 npm run dev"
    ),
)

requires_both = pytest.mark.skipif(
    not (_is_backend_up() and _is_nanoclaw_up()),
    reason="Both backend and NanoClaw must be running for this test.",
)


# ── Config helpers ────────────────────────────────────────────────────────────


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def backend() -> httpx.Client:
    """HTTP client pointed at the live backend."""
    with httpx.Client(base_url=BACKEND_URL, timeout=10.0) as client:
        yield client


@pytest.fixture
def session_id() -> str:
    """Unique session ID per test to avoid cross-test pollution."""
    return f"e2e-real-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def stm_session(backend: httpx.Client, session_id: str):
    """Create a real STM session in the live backend and return session info."""
    resp = backend.post(
        "/v1/stm/add-chat-history",
        json={
            "user_id": USER_ID,
            "agent_id": AGENT_ID,
            "session_id": session_id,
            "messages": [{"role": "user", "content": "Hello, start session"}],
        },
    )
    assert resp.status_code == 201, f"Failed to create STM session: {resp.text}"
    yield {"session_id": session_id, "user_id": USER_ID, "agent_id": AGENT_ID}
    # teardown: delete session to avoid MongoDB accumulation and task_sweep ERRORs
    backend.delete(
        f"/v1/stm/sessions/{session_id}",
        params={"user_id": USER_ID, "agent_id": AGENT_ID},
    )


# ── Tests: Backend health ─────────────────────────────────────────────────────


@pytest.mark.e2e
@requires_backend
class TestBackendConnectivity:
    def test_health_endpoint_reachable(self):
        """Backend /health endpoint returns a response (allow extra time for service checks)."""
        resp = httpx.get(f"{BACKEND_URL}/health", timeout=60.0)
        assert resp.status_code in (200, 503)
        body = resp.json()
        assert "status" in body

    def test_root_endpoint(self, backend: httpx.Client):
        """Backend root returns API info."""
        resp = backend.get("/")
        assert resp.status_code == 200
        assert "DesktopMate+" in resp.json().get("message", "")


# ── Tests: NanoClaw HTTP ingress ──────────────────────────────────────────────


@requires_nanoclaw
class TestNanoClawHttpIngress:
    def test_webhook_rejects_empty_payload(self):
        """NanoClaw webhook returns 400 for missing required fields."""
        r = httpx.post(NANOCLAW_WEBHOOK_URL, json={}, timeout=5.0)
        assert r.status_code == 400
        assert "required fields" in r.json().get("error", "").lower()

    def test_webhook_rejects_invalid_json(self):
        """NanoClaw webhook returns 400 for invalid JSON body."""
        r = httpx.post(
            NANOCLAW_WEBHOOK_URL,
            content=b"not-json",
            headers={"Content-Type": "application/json"},
            timeout=5.0,
        )
        assert r.status_code == 400
        assert "JSON" in r.json().get("error", "")

    def test_webhook_accepts_valid_task(self):
        """NanoClaw webhook returns 202 for a valid delegation payload."""
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        r = httpx.post(
            NANOCLAW_WEBHOOK_URL,
            json={
                "task": "E2E test: summarise the project README",
                "task_id": task_id,
                "session_id": "e2e-nc-session",
                "callback_url": "http://127.0.0.1:5500/v1/callback/nanoclaw/e2e-nc-session",
                "context": {"source": "e2e_test"},
            },
            timeout=5.0,
        )
        assert r.status_code == 202
        body = r.json()
        assert body["status"] == "accepted"
        assert body["task_id"] == task_id

    def test_webhook_unknown_path_returns_404(self):
        """NanoClaw HTTP channel returns 404 for unknown paths."""
        r = httpx.post(
            f"http://127.0.0.1:{NANOCLAW_HTTP_PORT}/unknown/path",
            json={},
            timeout=5.0,
        )
        assert r.status_code == 404
