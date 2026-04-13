from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.task_sweep_service.sweep import BackgroundSweepService, SweepConfig


def _expired_task(reply_channel=None):
    task = {
        "task_id": "t1",
        "status": "running",
    }
    if reply_channel is not None:
        task["reply_channel"] = reply_channel
    return task


def _make_sweep(expired_tasks, slack_fn=None):
    mock_repo = MagicMock()
    mock_repo.find_expirable.return_value = expired_tasks
    mock_repo.update_status.return_value = True

    svc = BackgroundSweepService(
        pending_task_repo=mock_repo,
        config=SweepConfig(sweep_interval_seconds=60, task_ttl_seconds=300),
        slack_service_fn=slack_fn,
    )
    return svc, mock_repo


class TestSweepSlackNotification:
    @pytest.mark.asyncio
    async def test_expired_task_triggers_slack_send(self):
        task = _expired_task(reply_channel={"provider": "slack", "channel_id": "C1"})
        mock_slack = AsyncMock()
        svc, mock_repo = _make_sweep(
            expired_tasks=[task],
            slack_fn=lambda: mock_slack,
        )
        await svc._sweep_once()

        mock_repo.update_status.assert_called_once_with("t1", "failed")
        mock_slack.send_message.assert_called_once_with(
            "C1", "태스크가 시간 초과됐어. 다시 시도해줘"
        )

    @pytest.mark.asyncio
    async def test_expired_unity_task_no_slack_call(self):
        """reply_channel 없는 Unity 세션은 Slack 알림 없이 상태만 변경."""
        task = _expired_task(reply_channel=None)
        mock_slack = AsyncMock()
        svc, mock_repo = _make_sweep(
            expired_tasks=[task],
            slack_fn=lambda: mock_slack,
        )
        await svc._sweep_once()

        mock_repo.update_status.assert_called_once_with("t1", "failed")
        mock_slack.send_message.assert_not_called()
