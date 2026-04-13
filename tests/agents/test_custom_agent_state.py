import pytest
from pydantic import ValidationError

from src.services.agent_service.state import CustomAgentState
from src.services.pending_task_repository import PendingTaskDocument


def test_custom_agent_state_fields():
    state = CustomAgentState(
        messages=[],
        user_id="u1",
        agent_id="yuri",
        ltm_last_consolidated_at_turn=0,
        knowledge_saved=False,
    )
    assert state["user_id"] == "u1"
    assert state["knowledge_saved"] is False


def test_pending_task_with_reply_channel():
    task = PendingTaskDocument(
        task_id="t1",
        session_id="sess1",
        user_id="u1",
        agent_id="yuri",
        description="do something",
        status="running",
        reply_channel={"provider": "slack", "channel_id": "C123"},
    )
    assert task.reply_channel is not None
    assert task.reply_channel["provider"] == "slack"


def test_pending_task_reply_channel_none():
    task = PendingTaskDocument(
        task_id="t2",
        session_id="sess1",
        user_id="u1",
        agent_id="yuri",
        description="ws task",
        status="running",
        reply_channel=None,
    )
    assert task.reply_channel is None


def test_pending_task_invalid_status_rejected():
    with pytest.raises(ValidationError):
        PendingTaskDocument(
            task_id="t3",
            session_id="sess1",
            user_id="u1",
            agent_id="yuri",
            description="bad status",
            status="pending",  # type: ignore[arg-type]
        )
