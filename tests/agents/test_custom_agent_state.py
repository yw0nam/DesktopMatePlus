from src.services.agent_service.state import CustomAgentState


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
    task: dict = {
        "task_id": "t1",
        "description": "do something",
        "status": "running",
        "created_at": "2026-03-25T00:00:00Z",
        "reply_channel": {"provider": "slack", "channel_id": "C123"},
    }
    assert task["reply_channel"]["provider"] == "slack"


def test_pending_task_reply_channel_none():
    task: dict = {
        "task_id": "t2",
        "description": "ws task",
        "status": "running",
        "created_at": "2026-03-25T00:00:00Z",
        "reply_channel": None,
    }
    assert task["reply_channel"] is None
