"""Tests for DelegateTaskTool."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.services.agent_service.tools.delegate import DelegateTaskTool
from src.services.stm_service.service import STMService


@pytest.fixture
def mock_stm_service():
    """Create a mock STM service with proper spec."""
    service = MagicMock(spec=STMService)
    service.get_session_metadata.return_value = {}
    service.update_session_metadata.return_value = True
    return service


@pytest.fixture
def delegate_tool(mock_stm_service):
    """Create a DelegateTaskTool instance with mock dependencies."""
    return DelegateTaskTool(stm_service=mock_stm_service, session_id="test-session")


class TestDelegateTaskTool:
    def test_run_records_pending_task_in_stm(self, delegate_tool, mock_stm_service):
        """Tool should record the task in STM metadata as 'running'."""
        with patch("src.services.agent_service.tools.delegate.delegate_task.httpx.Client"):
            delegate_tool._run("Review the code")

        mock_stm_service.get_session_metadata.assert_called_once_with("test-session")
        call_args = mock_stm_service.update_session_metadata.call_args
        assert call_args[0][0] == "test-session"
        pending = call_args[0][1]["pending_tasks"]
        assert len(pending) == 1
        assert pending[0]["status"] == "running"
        assert pending[0]["description"] == "Review the code"
        assert "task_id" in pending[0]

    def test_run_appends_to_existing_pending_tasks(self, delegate_tool, mock_stm_service):
        """Tool should append to existing pending tasks, not overwrite."""
        existing_task = {"task_id": "old-task", "status": "running", "description": "old"}
        mock_stm_service.get_session_metadata.return_value = {
            "pending_tasks": [existing_task]
        }

        with patch("src.services.agent_service.tools.delegate.delegate_task.httpx.Client"):
            delegate_tool._run("New task")

        pending = mock_stm_service.update_session_metadata.call_args[0][1]["pending_tasks"]
        assert len(pending) == 2
        assert pending[0]["task_id"] == "old-task"
        assert pending[1]["description"] == "New task"

    def test_run_posts_to_nanoclaw(self, delegate_tool):
        """Tool should fire POST to NanoClaw webhook."""
        with patch("src.services.agent_service.tools.delegate.delegate_task.httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            delegate_tool._run("Build feature X")

            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            assert payload["task"] == "Build feature X"
            assert payload["session_id"] == "test-session"
            assert "task_id" in payload
            assert "callback_url" in payload

    def test_run_returns_success_message(self, delegate_tool):
        """Tool should return Korean confirmation with task_id."""
        with patch("src.services.agent_service.tools.delegate.delegate_task.httpx.Client"):
            result = delegate_tool._run("Do something")

        assert "팀에 작업을 지시했습니다" in result
        assert "task_id:" in result

    def test_run_returns_error_message_on_http_failure(self, delegate_tool):
        """Tool should return error message when NanoClaw is unreachable."""
        with patch("src.services.agent_service.tools.delegate.delegate_task.httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            result = delegate_tool._run("Do something")

        assert "통신에 실패했습니다" in result
        assert "task_id:" in result

    def test_run_still_records_stm_metadata_on_http_failure(
        self, delegate_tool, mock_stm_service
    ):
        """Even if NanoClaw POST fails, STM metadata should be updated."""
        with patch("src.services.agent_service.tools.delegate.delegate_task.httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            delegate_tool._run("Do something")

        mock_stm_service.update_session_metadata.assert_called_once()
