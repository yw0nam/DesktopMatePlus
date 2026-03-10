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
import time
import uuid

import httpx
import pytest

# ── Service endpoints ─────────────────────────────────────────────────────────

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:5500")
NANOCLAW_HTTP_PORT = int(os.getenv("NANOCLAW_HTTP_PORT", "3001"))
NANOCLAW_WEBHOOK_URL = f"http://127.0.0.1:{NANOCLAW_HTTP_PORT}/api/webhooks/fastapi"
CALLBACK_PATH = "/v1/callback/nanoclaw"

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
def stm_session(backend: httpx.Client, session_id: str) -> dict:
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
    return {"session_id": session_id, "user_id": USER_ID, "agent_id": AGENT_ID}


@pytest.fixture
def stm_session_with_task(backend: httpx.Client, stm_session: dict) -> dict:
    """Add a pending task to an STM session metadata."""
    sid = stm_session["session_id"]
    task_id = f"task-{uuid.uuid4().hex[:8]}"
    pending_task = {
        "task_id": task_id,
        "description": "E2E test task",
        "status": "running",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    resp = backend.patch(
        f"/v1/stm/sessions/{sid}/metadata",
        json={
            "session_id": sid,
            "metadata": {
                "pending_tasks": [pending_task],
                "user_id": USER_ID,
                "agent_id": AGENT_ID,
            },
        },
    )
    assert resp.status_code == 200, f"Failed to set STM metadata: {resp.text}"
    return {**stm_session, "task_id": task_id}


# ── Tests: Backend health ─────────────────────────────────────────────────────


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


# ── Tests: Backend callback endpoint (direct, no NanoClaw) ───────────────────


@requires_backend
class TestBackendCallbackDirect:
    def test_callback_done_updates_stm(
        self, backend: httpx.Client, stm_session_with_task: dict
    ):
        """POST callback with status=done updates STM and injects TaskResult message."""
        sid = stm_session_with_task["session_id"]
        task_id = stm_session_with_task["task_id"]

        resp = backend.post(
            f"{CALLBACK_PATH}/{sid}",
            json={
                "task_id": task_id,
                "status": "done",
                "summary": "E2E verified: auth module has no vulnerabilities.",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == task_id
        assert body["status"] == "done"

        # Verify synthetic message in chat history
        history = backend.get(
            "/v1/stm/get-chat-history",
            params={"user_id": USER_ID, "agent_id": AGENT_ID, "session_id": sid},
        )
        assert history.status_code == 200
        messages = history.json()["messages"]
        contents = [m["content"] for m in messages if isinstance(m["content"], str)]
        assert any(f"[TaskResult:{task_id}]" in c for c in contents), (
            f"TaskResult message not found. Messages: {messages}"
        )

    def test_callback_failed_injects_task_failed_message(
        self, backend: httpx.Client, stm_session_with_task: dict
    ):
        """POST callback with status=failed injects TaskFailed message."""
        sid = stm_session_with_task["session_id"]
        task_id = stm_session_with_task["task_id"]

        resp = backend.post(
            f"{CALLBACK_PATH}/{sid}",
            json={
                "task_id": task_id,
                "status": "failed",
                "summary": "Container timed out after 300s.",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"

        history = backend.get(
            "/v1/stm/get-chat-history",
            params={"user_id": USER_ID, "agent_id": AGENT_ID, "session_id": sid},
        )
        contents = [
            m["content"]
            for m in history.json()["messages"]
            if isinstance(m["content"], str)
        ]
        assert any(f"[TaskFailed:{task_id}]" in c for c in contents)

    def test_callback_unknown_task_returns_404(
        self, backend: httpx.Client, stm_session: dict
    ):
        """Callback for an unknown task_id returns 404."""
        sid = stm_session["session_id"]
        resp = backend.post(
            f"{CALLBACK_PATH}/{sid}",
            json={
                "task_id": "nonexistent-task-id",
                "status": "done",
                "summary": "Should not appear.",
            },
        )
        assert resp.status_code == 404

    def test_callback_unknown_session_returns_404(self, backend: httpx.Client):
        """Callback for an unknown session_id returns 404."""
        resp = backend.post(
            f"{CALLBACK_PATH}/nonexistent-session-xyz",
            json={
                "task_id": "some-task",
                "status": "done",
                "summary": "Should not appear.",
            },
        )
        # Session has no pending tasks → 404
        assert resp.status_code == 404


# ── Tests: Full round-trip (NanoClaw processes → callbacks backend) ───────────


@requires_both
@pytest.mark.slow
class TestFullDelegationRoundtrip:
    """Full round-trip: backend STM → NanoClaw webhook → Claude processes → backend callback.

    These tests require both services running AND NanoClaw's Claude agent to respond.
    May take 30-120s depending on Claude processing time.
    """

    POLL_INTERVAL = 5  # seconds
    MAX_WAIT = 120  # seconds

    def _wait_for_callback(
        self, backend: httpx.Client, session_id: str, task_id: str
    ) -> dict | None:
        """Poll STM chat history until TaskResult/TaskFailed appears or timeout."""
        deadline = time.time() + self.MAX_WAIT
        while time.time() < deadline:
            resp = backend.get(
                "/v1/stm/get-chat-history",
                params={
                    "user_id": USER_ID,
                    "agent_id": AGENT_ID,
                    "session_id": session_id,
                },
            )
            if resp.status_code == 200:
                messages = resp.json().get("messages", [])
                for msg in messages:
                    content = msg.get("content", "")
                    if isinstance(content, str) and task_id in content:
                        return msg
            time.sleep(self.POLL_INTERVAL)
        return None

    def test_nanoclaw_processes_and_callbacks_backend(
        self, backend: httpx.Client, stm_session: dict
    ):
        """Full round-trip: POST to NanoClaw → wait for callback → verify STM message.

        Flow:
          1. Create STM session in backend (via fixture)
          2. POST task to NanoClaw webhook (callback_url → backend)
          3. NanoClaw's Claude agent processes and POSTs callback
          4. Backend injects TaskResult synthetic message
          5. Poll STM chat history until the message appears
        """
        sid = stm_session["session_id"]
        task_id = f"task-roundtrip-{uuid.uuid4().hex[:8]}"

        # Pre-register the pending task in STM so the callback endpoint won't 404
        backend.patch(
            f"/v1/stm/sessions/{sid}/metadata",
            json={
                "session_id": sid,
                "metadata": {
                    "pending_tasks": [
                        {
                            "task_id": task_id,
                            "description": "Round-trip E2E test task",
                            "status": "running",
                            "created_at": "2026-01-01T00:00:00+00:00",
                        }
                    ],
                    "user_id": USER_ID,
                    "agent_id": AGENT_ID,
                }
            },
        )

        # Send task to NanoClaw with backend callback URL
        callback_url = f"{BACKEND_URL}{CALLBACK_PATH}/{sid}"
        r = httpx.post(
            NANOCLAW_WEBHOOK_URL,
            json={
                "task": (
                    "This is an automated E2E test. "
                    "Reply with exactly: 'E2E test complete.' and nothing else."
                ),
                "task_id": task_id,
                "session_id": sid,
                "callback_url": callback_url,
                "context": {"test": True},
            },
            timeout=10.0,
        )
        assert r.status_code == 202, f"NanoClaw rejected task: {r.text}"

        # Wait for NanoClaw to process and callback
        result_msg = self._wait_for_callback(backend, sid, task_id)

        assert result_msg is not None, (
            f"No callback received within {self.MAX_WAIT}s. "
            "Check NanoClaw logs: npm run dev (with HTTP_PORT=3001)"
        )
        content = result_msg["content"]
        assert task_id in content, f"task_id not found in synthetic message: {content}"
        # TaskResult or TaskFailed — either means the round-trip completed
        assert "[TaskResult:" in content or "[TaskFailed:" in content, (
            f"Unexpected message format: {content}"
        )
