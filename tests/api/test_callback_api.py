"""Tests for NanoClaw callback endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch


def _mock_repo(
    task_id="t1",
    session_id="test-session",
    user_id="test-user",
    agent_id="yuri",
    task_status="running",
    reply_channel=None,
):
    """Create a mock PendingTaskRepository with configurable task record."""
    repo = MagicMock()
    task_record = {
        "task_id": task_id,
        "session_id": session_id,
        "user_id": user_id,
        "agent_id": agent_id,
        "description": "test task",
        "status": task_status,
        "reply_channel": reply_channel,
    }
    repo.find_by_task_id.return_value = task_record
    repo.update_status.return_value = None
    return repo


class TestNanoClawCallback:
    """Tests for POST /v1/callback/nanoclaw/{task_id} endpoint."""

    def test_callback_returns_503_when_repo_not_initialized(self, client):
        """Should return 503 when task repository is unavailable."""
        with patch("src.api.routes.callback.get_pending_task_repo", return_value=None):
            response = client.post(
                "/v1/callback/nanoclaw/task-123",
                json={
                    "task_id": "task-123",
                    "status": "done",
                    "summary": "Completed successfully",
                },
            )
        assert response.status_code == 503

    def test_callback_returns_404_for_unknown_task(self, client):
        """Should return 404 when task_id is not found in repository."""
        repo = _mock_repo()
        repo.find_by_task_id.return_value = None

        with patch("src.api.routes.callback.get_pending_task_repo", return_value=repo):
            response = client.post(
                "/v1/callback/nanoclaw/task-123",
                json={
                    "task_id": "nonexistent-task",
                    "status": "done",
                    "summary": "Some result",
                },
            )
        assert response.status_code == 404
        assert "nonexistent-task" in response.json()["detail"]

    def test_callback_updates_task_status_on_success(self, client):
        """Should update task status to 'done' and return 200."""
        task_id = "task-abc"
        repo = _mock_repo(task_id=task_id, task_status="running")

        with patch("src.api.routes.callback.get_pending_task_repo", return_value=repo):
            response = client.post(
                f"/v1/callback/nanoclaw/{task_id}",
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

        # Verify update_status was called with correct args
        repo.update_status.assert_called_once_with(
            task_id, "done", "Code review complete - no issues found"
        )

    def test_callback_handles_failed_status(self, client):
        """Should accept 'failed' status and return 200."""
        task_id = "task-fail"
        repo = _mock_repo(task_id=task_id, task_status="running")

        with patch("src.api.routes.callback.get_pending_task_repo", return_value=repo):
            response = client.post(
                f"/v1/callback/nanoclaw/{task_id}",
                json={
                    "task_id": task_id,
                    "status": "failed",
                    "summary": "Container timeout",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        repo.update_status.assert_called_once_with(
            task_id, "failed", "Container timeout"
        )

    def test_callback_rejects_invalid_status(self, client):
        """Should reject payload with invalid status value."""
        repo = _mock_repo()
        with patch("src.api.routes.callback.get_pending_task_repo", return_value=repo):
            response = client.post(
                "/v1/callback/nanoclaw/task-123",
                json={
                    "task_id": "task-123",
                    "status": "invalid",
                    "summary": "Something",
                },
            )
        assert response.status_code == 422

    def test_callback_rejects_missing_fields(self, client):
        """Should reject payload with missing required fields."""
        repo = _mock_repo()
        with patch("src.api.routes.callback.get_pending_task_repo", return_value=repo):
            response = client.post(
                "/v1/callback/nanoclaw/task-123",
                json={"task_id": "task-123"},
            )
        assert response.status_code == 422


class TestCallbackSlackRouting:
    """reply_channel이 있는 Slack 세션에서 콜백이 process_message를 호출하는지 검증."""

    def test_slack_session_triggers_process_message(self, client):
        """Task-level reply_channel triggers process_message for Slack routing."""
        task_id = "task-slack-1"
        reply_channel = {"provider": "slack", "channel_id": "C1"}
        repo = _mock_repo(
            task_id=task_id,
            session_id="slack:T1:C1:default",
            user_id="U1",
            agent_id="yuri",
            task_status="running",
            reply_channel=reply_channel,
        )
        mock_agent_svc = MagicMock()
        captured_coros = []

        def capture_coro(coro):
            captured_coros.append(coro)
            coro.close()  # prevent "never awaited" warning

        with (
            patch("src.api.routes.callback.get_pending_task_repo", return_value=repo),
            patch(
                "src.services.get_agent_service",
                return_value=mock_agent_svc,
            ),
            patch(
                "src.api.routes.callback.asyncio.create_task",
                side_effect=capture_coro,
            ),
        ):
            response = client.post(
                f"/v1/callback/nanoclaw/{task_id}",
                json={
                    "task_id": task_id,
                    "status": "done",
                    "summary": "Task complete",
                },
            )

        assert response.status_code == 200
        # Verify process_message coroutine was scheduled via create_task
        assert len(captured_coros) == 1
        assert "process_message" in captured_coros[0].__qualname__

    def test_unity_session_skips_process_message(self, client):
        """reply_channel 없는 Unity 세션은 process_message를 호출하지 않는다."""
        task_id = "task-unity-1"
        repo = _mock_repo(
            task_id=task_id,
            session_id="unity-session-xyz",
            task_status="running",
            reply_channel=None,
        )

        with (
            patch("src.api.routes.callback.get_pending_task_repo", return_value=repo),
            patch(
                "src.services.channel_service.process_message", new=AsyncMock()
            ) as mock_pm,
        ):
            response = client.post(
                f"/v1/callback/nanoclaw/{task_id}",
                json={
                    "task_id": task_id,
                    "status": "done",
                    "summary": "Done",
                },
            )

        assert response.status_code == 200
        mock_pm.assert_not_called()
