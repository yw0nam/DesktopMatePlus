from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.agent_service.session_registry import SessionRegistry
from src.services.task_sweep_service.sweep import BackgroundSweepService, SweepConfig


def _expired_task(reply_channel=None):
    task = {
        "task_id": "t1",
        "status": "running",
        "created_at": (datetime.now(timezone.utc) - timedelta(seconds=999)).isoformat(),
    }
    if reply_channel is not None:
        task["reply_channel"] = reply_channel
    return task


def _make_sweep(pending_tasks, slack_fn=None):
    registry = MagicMock(spec=SessionRegistry)
    registry.find_all.return_value = [{"thread_id": "thread-1"}]

    agent_svc = MagicMock()
    checkpoint = MagicMock()
    checkpoint.values = {"pending_tasks": pending_tasks}
    agent_svc.agent.aget_state = AsyncMock(return_value=checkpoint)
    agent_svc.agent.aupdate_state = AsyncMock()

    svc = BackgroundSweepService(
        agent_service=agent_svc,
        session_registry=registry,
        config=SweepConfig(sweep_interval_seconds=60, task_ttl_seconds=300),
        slack_service_fn=slack_fn,
    )
    return svc, agent_svc


class TestSweepSlackNotification:
    @pytest.mark.asyncio
    async def test_expired_task_triggers_slack_send(self):
        task = _expired_task(reply_channel={"provider": "slack", "channel_id": "C1"})
        mock_slack = AsyncMock()
        svc, agent_svc = _make_sweep(
            pending_tasks=[task],
            slack_fn=lambda: mock_slack,
        )
        await svc._sweep_once()

        agent_svc.agent.aupdate_state.assert_called_once()
        mock_slack.send_message.assert_called_once_with(
            "C1", "태스크가 시간 초과됐어. 다시 시도해줘"
        )

    @pytest.mark.asyncio
    async def test_expired_unity_task_no_slack_call(self):
        """reply_channel 없는 Unity 세션은 Slack 알림 없이 상태만 변경."""
        task = _expired_task(reply_channel=None)
        mock_slack = AsyncMock()
        svc, agent_svc = _make_sweep(
            pending_tasks=[task],
            slack_fn=lambda: mock_slack,
        )
        await svc._sweep_once()

        agent_svc.agent.aupdate_state.assert_called_once()
        mock_slack.send_message.assert_not_called()
