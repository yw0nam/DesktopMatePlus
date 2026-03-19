from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.task_sweep_service.sweep import BackgroundSweepService, SweepConfig


def _expired_task(task_id: str) -> dict:
    return {
        "task_id": task_id,
        "status": "running",
        "created_at": (datetime.now(timezone.utc) - timedelta(seconds=999)).isoformat(),
    }


class TestSweepSlackNotification:
    @pytest.mark.asyncio
    async def test_expired_task_triggers_slack_send(self):
        stm = MagicMock()
        stm.list_all_sessions.return_value = [{"session_id": "slack:T1:C1:default"}]
        stm.get_session_metadata.return_value = {
            "pending_tasks": [_expired_task("task-1")],
            "reply_channel": {"provider": "slack", "channel_id": "C1"},
        }
        stm.update_session_metadata.return_value = True

        mock_slack = AsyncMock()
        slack_svc_fn = lambda: mock_slack  # noqa: E731

        svc = BackgroundSweepService(
            stm_service=stm,
            config=SweepConfig(sweep_interval_seconds=60, task_ttl_seconds=300),
            slack_service_fn=slack_svc_fn,
        )
        await svc._sweep_once()

        mock_slack.send_message.assert_called_once_with(
            "C1", "태스크가 시간 초과됐어. 다시 시도해줘"
        )

    @pytest.mark.asyncio
    async def test_expired_unity_task_no_slack_call(self):
        """reply_channel 없는 Unity 세션은 Slack 알림 없이 상태만 변경."""
        stm = MagicMock()
        stm.list_all_sessions.return_value = [{"session_id": "unity-session"}]
        stm.get_session_metadata.return_value = {
            "pending_tasks": [_expired_task("task-u")],
            # reply_channel 없음
        }
        stm.update_session_metadata.return_value = True

        mock_slack = AsyncMock()
        svc = BackgroundSweepService(
            stm_service=stm,
            config=SweepConfig(),
            slack_service_fn=lambda: mock_slack,
        )
        await svc._sweep_once()
        mock_slack.send_message.assert_not_called()
