"""Tests for NanoClaw callback endpoint."""

from unittest.mock import MagicMock, patch

import pytest

from src.services.stm_service.service import STMService


@pytest.fixture
def mock_stm_service():
    """Create a mock STM service for callback tests."""
    service = MagicMock(spec=STMService)
    return service


class TestNanoClawCallback:
    """Tests for POST /v1/callback/nanoclaw/{session_id} endpoint."""

    def test_callback_returns_503_when_stm_not_initialized(self, client):
        """Should return 503 when STM service is unavailable."""
        with patch("src.api.routes.callback.get_stm_service", return_value=None):
            response = client.post(
                "/v1/callback/nanoclaw/session-123",
                json={
                    "task_id": "task-123",
                    "status": "done",
                    "summary": "Completed successfully",
                },
            )
        assert response.status_code == 503

    def test_callback_returns_404_for_unknown_task(self, client, mock_stm_service):
        """Should return 404 when task_id is not found in session metadata."""
        mock_stm_service.get_session_metadata.return_value = {"pending_tasks": []}

        with patch(
            "src.api.routes.callback.get_stm_service", return_value=mock_stm_service
        ):
            response = client.post(
                "/v1/callback/nanoclaw/session-123",
                json={
                    "task_id": "nonexistent-task",
                    "status": "done",
                    "summary": "Some result",
                },
            )
        assert response.status_code == 404
        assert "nonexistent-task" in response.json()["detail"]

    def test_callback_updates_task_status_on_success(self, client, mock_stm_service):
        """Should update task status to 'done' and inject synthetic message."""
        task_id = "task-abc"
        session_id = "session-xyz"
        pending_tasks = [
            {"task_id": task_id, "status": "running", "description": "Review code"}
        ]

        mock_stm_service.get_session_metadata.return_value = {
            "pending_tasks": pending_tasks,
            "user_id": "user-1",
            "agent_id": "agent-1",
        }
        mock_stm_service.update_session_metadata.return_value = True
        mock_stm_service.add_chat_history.return_value = session_id

        with patch(
            "src.api.routes.callback.get_stm_service", return_value=mock_stm_service
        ):
            response = client.post(
                f"/v1/callback/nanoclaw/{session_id}",
                json={
                    "task_id": task_id,
                    "status": "done",
                    "summary": "Code review complete - no issues found",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "done"

        # Verify STM metadata was updated
        mock_stm_service.update_session_metadata.assert_called_once()
        call_args = mock_stm_service.update_session_metadata.call_args
        assert call_args[0][0] == session_id
        updated_pending = call_args[0][1]["pending_tasks"]
        assert updated_pending[0]["status"] == "done"

        # Verify synthetic message was injected
        mock_stm_service.add_chat_history.assert_called_once()
        add_kwargs = mock_stm_service.add_chat_history.call_args[1]
        assert add_kwargs["session_id"] == session_id
        assert add_kwargs["user_id"] == "user-1"
        assert add_kwargs["agent_id"] == "agent-1"
        msgs = add_kwargs["messages"]
        assert len(msgs) == 1
        assert f"[TaskResult:{task_id}]" in msgs[0].content
        assert "Code review complete" in msgs[0].content

    def test_callback_handles_failed_status(self, client, mock_stm_service):
        """Should inject TaskFailed synthetic message for failed tasks."""
        task_id = "task-fail"
        session_id = "session-fail"
        pending_tasks = [
            {"task_id": task_id, "status": "running", "description": "Build feature"}
        ]

        mock_stm_service.get_session_metadata.return_value = {
            "pending_tasks": pending_tasks,
        }
        mock_stm_service.update_session_metadata.return_value = True
        mock_stm_service.add_chat_history.return_value = session_id

        with patch(
            "src.api.routes.callback.get_stm_service", return_value=mock_stm_service
        ):
            response = client.post(
                f"/v1/callback/nanoclaw/{session_id}",
                json={
                    "task_id": task_id,
                    "status": "failed",
                    "summary": "Container timeout",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"

        # Verify synthetic message uses TaskFailed prefix
        add_kwargs = mock_stm_service.add_chat_history.call_args[1]
        msgs = add_kwargs["messages"]
        assert f"[TaskFailed:{task_id}]" in msgs[0].content

    def test_callback_rejects_invalid_status(self, client):
        """Should reject payload with invalid status value."""
        with patch("src.api.routes.callback.get_stm_service", return_value=MagicMock()):
            response = client.post(
                "/v1/callback/nanoclaw/session-123",
                json={
                    "task_id": "task-123",
                    "status": "invalid",
                    "summary": "Something",
                },
            )
        assert response.status_code == 422

    def test_callback_rejects_missing_fields(self, client):
        """Should reject payload with missing required fields."""
        with patch("src.api.routes.callback.get_stm_service", return_value=MagicMock()):
            response = client.post(
                "/v1/callback/nanoclaw/session-123",
                json={"task_id": "task-123"},
            )
        assert response.status_code == 422
