"""Unit tests for MessageHandler.handle_hitl_response (built-in HITL)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.services.websocket_service.message_processor.models import TurnStatus


def _make_handler_with_active_turn(pending_count: int):
    """Build a MessageHandler with a stub connection in AWAITING_APPROVAL state."""
    from src.services.websocket_service.manager.handlers import MessageHandler

    turn = MagicMock()
    turn.session_id = "sess-1"
    turn.status = TurnStatus.AWAITING_APPROVAL
    turn.metadata = {"pending_action_count": pending_count}

    processor = MagicMock()
    processor._current_turn_id = "turn-1"
    processor.turns = {"turn-1": turn}
    processor.update_turn_status = AsyncMock()
    processor.attach_agent_stream = AsyncMock()
    processor.add_task_to_turn = AsyncMock()

    conn_state = MagicMock()
    conn_state.message_processor = processor

    handler = MessageHandler(
        get_connection_fn=MagicMock(return_value=conn_state),
        send_message_fn=AsyncMock(),
        close_connection_fn=AsyncMock(),
    )

    return handler, processor, turn


@pytest.mark.asyncio
async def test_hitl_response_validation_error_sends_4004():
    handler, processor, _ = _make_handler_with_active_turn(pending_count=1)

    cid = uuid4()
    bad_payload = {"decisions": [{"type": "nope"}]}  # invalid decision type

    await handler.handle_hitl_response(cid, bad_payload, forward_events_fn=AsyncMock())

    args, _ = handler.send_message.call_args
    assert args[0] == cid
    err = args[1]
    assert err.code == 4004
    assert "Invalid hitl_response payload" in err.error
    # status NOT mutated on validation failure
    processor.update_turn_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_hitl_response_count_mismatch_sends_4004():
    handler, processor, _ = _make_handler_with_active_turn(pending_count=2)

    cid = uuid4()
    payload = {"decisions": [{"type": "approve"}]}  # count=1, expected=2

    await handler.handle_hitl_response(cid, payload, forward_events_fn=AsyncMock())

    args, _ = handler.send_message.call_args
    err = args[1]
    assert err.code == 4004
    assert "decisions count mismatch" in err.error
    # AWAITING_APPROVAL status NOT mutated on mismatch
    processor.update_turn_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_hitl_response_happy_path_forwards_decisions(monkeypatch):
    from src.services.websocket_service.manager import handlers as handlers_mod

    handler, processor, _ = _make_handler_with_active_turn(pending_count=2)

    # Stub agent service
    agent_service = MagicMock()
    captured: dict = {}

    def fake_resume(session_id, decisions):
        captured["session_id"] = session_id
        captured["decisions"] = decisions

        async def _gen():
            if False:
                yield

        return _gen()

    agent_service.resume_after_approval = fake_resume
    monkeypatch.setattr(handlers_mod, "get_agent_service", lambda: agent_service)

    cid = uuid4()
    payload = {
        "decisions": [
            {"type": "approve"},
            {"type": "reject", "message": "nope"},
        ],
    }

    await handler.handle_hitl_response(cid, payload, forward_events_fn=AsyncMock())

    processor.update_turn_status.assert_awaited_with("turn-1", TurnStatus.PROCESSING)
    assert captured["session_id"] == "sess-1"
    assert captured["decisions"][0] == {"type": "approve"}
    assert captured["decisions"][1] == {"type": "reject", "message": "nope"}
    processor.attach_agent_stream.assert_awaited()
