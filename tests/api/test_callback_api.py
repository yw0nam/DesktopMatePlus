"""Tests for NanoClaw callback endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch


def _mock_agent_svc(task_id="t1", task_status="running", reply_channel=None):
    """Create a mock agent service with configurable checkpoint state."""
    svc = MagicMock()
    state = {
        "pending_tasks": [
            {
                "task_id": task_id,
                "status": task_status,
                "reply_channel": reply_channel,
            }
        ],
        "user_id": "u1",
        "agent_id": "yuri",
    }
    checkpoint = MagicMock()
    checkpoint.values = state
    svc.agent.aget_state = AsyncMock(return_value=checkpoint)
    svc.agent.aupdate_state = AsyncMock()
    return svc


class TestNanoClawCallback:
    """Tests for POST /v1/callback/nanoclaw/{session_id} endpoint."""

    def test_callback_returns_503_when_agent_not_initialized(self, client):
        """Should return 503 when agent service is unavailable."""
        with patch("src.api.routes.callback.get_agent_service", return_value=None):
            response = client.post(
                "/v1/callback/nanoclaw/session-123",
                json={
                    "task_id": "task-123",
                    "status": "done",
                    "summary": "Completed successfully",
                },
            )
        assert response.status_code == 503

    def test_callback_returns_404_for_unknown_task(self, client):
        """Should return 404 when task_id is not found in agent state."""
        svc = _mock_agent_svc()
        # Override with empty pending_tasks
        svc.agent.aget_state.return_value.values = {
            "pending_tasks": [],
            "user_id": "u1",
            "agent_id": "yuri",
        }

        with patch("src.api.routes.callback.get_agent_service", return_value=svc):
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

    def test_callback_updates_task_status_on_success(self, client):
        """Should update task status to 'done' and inject synthetic message."""
        task_id = "task-abc"
        session_id = "session-xyz"
        svc = _mock_agent_svc(task_id=task_id, task_status="running")

        with patch("src.api.routes.callback.get_agent_service", return_value=svc):
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

        # Verify aupdate_state was called with updated pending_tasks + synthetic msg
        svc.agent.aupdate_state.assert_called_once()
        call_args = svc.agent.aupdate_state.call_args
        config = call_args[0][0]
        assert config["configurable"]["thread_id"] == session_id
        update_values = call_args[0][1]
        assert update_values["pending_tasks"][0]["status"] == "done"
        msgs = update_values["messages"]
        assert len(msgs) == 1
        assert f"[TaskResult:{task_id}]" in msgs[0].content
        assert "Code review complete" in msgs[0].content

    def test_callback_handles_failed_status(self, client):
        """Should inject TaskFailed synthetic message for failed tasks."""
        task_id = "task-fail"
        session_id = "session-fail"
        svc = _mock_agent_svc(task_id=task_id, task_status="running")

        with patch("src.api.routes.callback.get_agent_service", return_value=svc):
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
        update_values = svc.agent.aupdate_state.call_args[0][1]
        msgs = update_values["messages"]
        assert f"[TaskFailed:{task_id}]" in msgs[0].content

    def test_callback_returns_503_on_state_update_failure(self, client):
        """Should return 503 when aupdate_state raises an exception."""
        svc = _mock_agent_svc(task_id="task-err", task_status="running")
        svc.agent.aupdate_state = AsyncMock(side_effect=RuntimeError("DB down"))

        with patch("src.api.routes.callback.get_agent_service", return_value=svc):
            response = client.post(
                "/v1/callback/nanoclaw/session-err",
                json={
                    "task_id": "task-err",
                    "status": "done",
                    "summary": "Result",
                },
            )
        assert response.status_code == 503
        assert "State update failed" in response.json()["detail"]

    def test_callback_rejects_invalid_status(self, client):
        """Should reject payload with invalid status value."""
        with patch(
            "src.api.routes.callback.get_agent_service",
            return_value=_mock_agent_svc(),
        ):
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
        with patch(
            "src.api.routes.callback.get_agent_service",
            return_value=_mock_agent_svc(),
        ):
            response = client.post(
                "/v1/callback/nanoclaw/session-123",
                json={"task_id": "task-123"},
            )
        assert response.status_code == 422


class TestCallbackSlackRouting:
    """reply_channel이 있는 Slack 세션에서 콜백이 process_message를 호출하는지 검증."""

    def test_slack_session_triggers_process_message(self, client):
        """Task-level reply_channel triggers process_message for Slack routing."""
        task_id = "task-slack-1"
        session_id = "slack:T1:C1:default"
        reply_channel = {"provider": "slack", "channel_id": "C1"}
        svc = _mock_agent_svc(
            task_id=task_id, task_status="running", reply_channel=reply_channel
        )

        with (
            patch("src.api.routes.callback.get_agent_service", return_value=svc),
            patch(
                "src.services.channel_service.process_message", new=AsyncMock()
            ) as mock_pm,
        ):
            response = client.post(
                f"/v1/callback/nanoclaw/{session_id}",
                json={
                    "task_id": task_id,
                    "status": "done",
                    "summary": "Task complete",
                },
            )

        assert response.status_code == 200
        mock_pm.assert_called_once()
        call_kwargs = mock_pm.call_args[1]
        assert call_kwargs["text"] == ""
        assert call_kwargs["provider"] == "slack"
        assert call_kwargs["channel_id"] == "C1"
        # Verify no stm= kwarg
        assert "stm" not in call_kwargs

    def test_unity_session_skips_process_message(self, client):
        """reply_channel 없는 Unity 세션은 process_message를 호출하지 않는다."""
        task_id = "task-unity-1"
        session_id = "unity-session-xyz"
        svc = _mock_agent_svc(task_id=task_id, task_status="running")

        with (
            patch("src.api.routes.callback.get_agent_service", return_value=svc),
            patch(
                "src.services.channel_service.process_message", new=AsyncMock()
            ) as mock_pm,
        ):
            response = client.post(
                f"/v1/callback/nanoclaw/{session_id}",
                json={
                    "task_id": task_id,
                    "status": "done",
                    "summary": "Done",
                },
            )

        assert response.status_code == 200
        mock_pm.assert_not_called()
