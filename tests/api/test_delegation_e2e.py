"""E2E integration test for delegation flow.

Tests: DelegateTaskTool → (mock NanoClaw) → Callback endpoint → STM update.
Validates the complete fire-and-forget delegation round-trip.
"""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import MagicMock, patch

import pytest

from src.services.agent_service.tools.delegate import DelegateTaskTool
from src.services.stm_service.service import STMService


class MockNanoClawHandler(BaseHTTPRequestHandler):
    """Mock NanoClaw server that captures received payloads."""

    received_payloads = []

    def do_POST(self):
        import json

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        MockNanoClawHandler.received_payloads.append(body)
        self.send_response(202)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "accepted"}')

    def log_message(self, format, *args):
        pass  # Suppress server logs


@pytest.fixture
def mock_nanoclaw_server():
    """Start a mock NanoClaw HTTP server on a random port."""
    MockNanoClawHandler.received_payloads = []
    server = HTTPServer(("127.0.0.1", 0), MockNanoClawHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield port
    server.shutdown()


@pytest.fixture
def mock_stm():
    """Create a mock STM with in-memory metadata store."""
    service = MagicMock(spec=STMService)
    metadata_store = {}

    def get_metadata(session_id):
        return dict(metadata_store.get(session_id, {}))

    def update_metadata(session_id, metadata):
        if session_id not in metadata_store:
            metadata_store[session_id] = {}
        metadata_store[session_id].update(metadata)
        return True

    service.get_session_metadata.side_effect = get_metadata
    service.update_session_metadata.side_effect = update_metadata
    service.add_chat_history.return_value = "session-e2e"
    service._metadata_store = metadata_store
    return service


class TestDelegationFlowE2E:
    """End-to-end test: DelegateTaskTool → NanoClaw → Callback → STM."""

    def test_full_delegation_round_trip(self, client, mock_stm, mock_nanoclaw_server):
        """Complete delegation flow: tool fires task, callback updates STM."""
        session_id = "session-e2e-001"
        nanoclaw_url = f"http://127.0.0.1:{mock_nanoclaw_server}"

        # 1. DelegateTaskTool fires task to mock NanoClaw
        with patch(
            "src.services.agent_service.tools.delegate.delegate_task.NANOCLAW_URL",
            nanoclaw_url,
        ):
            tool = DelegateTaskTool(stm_service=mock_stm, session_id=session_id)
            result = tool._run("Review the authentication module for security issues")

        assert "팀에 작업을 지시했습니다" in result

        # 2. Verify NanoClaw received the payload
        assert len(MockNanoClawHandler.received_payloads) == 1
        nc_payload = MockNanoClawHandler.received_payloads[0]
        assert (
            nc_payload["task"] == "Review the authentication module for security issues"
        )
        assert nc_payload["session_id"] == session_id
        assert "task_id" in nc_payload
        assert "callback_url" in nc_payload
        task_id = nc_payload["task_id"]

        # 3. Verify STM metadata has pending task
        metadata = mock_stm._metadata_store[session_id]
        assert len(metadata["pending_tasks"]) == 1
        assert metadata["pending_tasks"][0]["status"] == "running"
        assert metadata["pending_tasks"][0]["task_id"] == task_id

        # 4. Simulate NanoClaw callback (POST to callback endpoint)
        with patch("src.api.routes.callback.get_stm_service", return_value=mock_stm):
            callback_response = client.post(
                f"/v1/callback/nanoclaw/{session_id}",
                json={
                    "task_id": task_id,
                    "status": "done",
                    "summary": "Auth module reviewed: 1 SQL injection vulnerability found at line 45",
                },
            )

        assert callback_response.status_code == 200
        data = callback_response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "done"

        # 5. Verify STM metadata updated to 'done'
        updated_metadata = mock_stm._metadata_store[session_id]
        assert updated_metadata["pending_tasks"][0]["status"] == "done"

        # 6. Verify synthetic message was injected
        mock_stm.add_chat_history.assert_called_once()
        call_kwargs = mock_stm.add_chat_history.call_args[1]
        assert call_kwargs["session_id"] == session_id
        msg = call_kwargs["messages"][0]
        assert f"[TaskResult:{task_id}]" in msg.content
        assert "SQL injection" in msg.content

    def test_delegation_with_nanoclaw_failure(self, client, mock_stm):
        """Delegation should record task even if NanoClaw is unreachable."""
        session_id = "session-e2e-002"

        # Point to non-existent NanoClaw
        with patch(
            "src.services.agent_service.tools.delegate.delegate_task.NANOCLAW_URL",
            "http://127.0.0.1:1",
        ):
            tool = DelegateTaskTool(stm_service=mock_stm, session_id=session_id)
            result = tool._run("Generate API documentation")

        # Tool degrades gracefully
        assert "통신에 실패했습니다" in result

        # But task is still recorded in STM
        metadata = mock_stm._metadata_store[session_id]
        assert len(metadata["pending_tasks"]) == 1
        assert metadata["pending_tasks"][0]["status"] == "running"

    def test_callback_for_failed_task(self, client, mock_stm, mock_nanoclaw_server):
        """Callback with status='failed' should inject TaskFailed message."""
        session_id = "session-e2e-003"
        nanoclaw_url = f"http://127.0.0.1:{mock_nanoclaw_server}"

        with patch(
            "src.services.agent_service.tools.delegate.delegate_task.NANOCLAW_URL",
            nanoclaw_url,
        ):
            tool = DelegateTaskTool(stm_service=mock_stm, session_id=session_id)
            tool._run("Build the payment module")

        task_id = MockNanoClawHandler.received_payloads[-1]["task_id"]

        # Simulate NanoClaw reporting failure
        with patch("src.api.routes.callback.get_stm_service", return_value=mock_stm):
            response = client.post(
                f"/v1/callback/nanoclaw/{session_id}",
                json={
                    "task_id": task_id,
                    "status": "failed",
                    "summary": "Container timeout after 300s",
                },
            )

        assert response.status_code == 200

        # Verify failed status in metadata
        metadata = mock_stm._metadata_store[session_id]
        assert metadata["pending_tasks"][0]["status"] == "failed"

        # Verify TaskFailed synthetic message
        call_kwargs = mock_stm.add_chat_history.call_args[1]
        msg = call_kwargs["messages"][0]
        assert f"[TaskFailed:{task_id}]" in msg.content
