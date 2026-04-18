"""Tests for EventHandler.hitl_request handling (built-in shape)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.websocket_service.message_processor.models import TurnStatus


@pytest.mark.asyncio
async def test_hitl_request_sets_awaiting_approval_and_stores_count():
    from src.services.websocket_service.message_processor.event_handlers import (
        EventHandler,
    )

    processor = MagicMock()
    processor.update_turn_status = AsyncMock()
    processor._put_event = AsyncMock()
    processor._normalize_event = MagicMock(side_effect=lambda _tid, ev: ev)
    turn = MagicMock()
    turn.metadata = {}
    processor.turns = {"t1": turn}

    handler = EventHandler(processor)
    handler._signal_token_stream_closed = AsyncMock()
    handler._wait_for_token_queue = AsyncMock()

    async def stream():
        yield {
            "type": "hitl_request",
            "session_id": "s1",
            "action_requests": [
                {"name": "write_file", "arguments": {}, "description": "d"},
            ],
            "review_configs": [
                {
                    "action_name": "write_file",
                    "allowed_decisions": ["approve", "reject"],
                },
            ],
        }

    await handler.produce_agent_events("t1", stream())

    processor.update_turn_status.assert_awaited_with("t1", TurnStatus.AWAITING_APPROVAL)
    # 서버는 count 를 저장해 handle_hitl_response 의 decisions-count-mismatch 검증에 사용
    assert turn.metadata["pending_action_count"] == 1
    processor._put_event.assert_awaited()


@pytest.mark.asyncio
async def test_hitl_request_stores_multi_action_count():
    from src.services.websocket_service.message_processor.event_handlers import (
        EventHandler,
    )

    processor = MagicMock()
    processor.update_turn_status = AsyncMock()
    processor._put_event = AsyncMock()
    processor._normalize_event = MagicMock(side_effect=lambda _tid, ev: ev)
    turn = MagicMock()
    turn.metadata = {}
    processor.turns = {"t1": turn}

    handler = EventHandler(processor)
    handler._signal_token_stream_closed = AsyncMock()
    handler._wait_for_token_queue = AsyncMock()

    async def stream():
        yield {
            "type": "hitl_request",
            "session_id": "s1",
            "action_requests": [
                {"name": "write_file", "arguments": {}, "description": "d1"},
                {"name": "file_delete", "arguments": {}, "description": "d2"},
                {"name": "edit_file", "arguments": {}, "description": "d3"},
            ],
            "review_configs": [
                {
                    "action_name": "write_file",
                    "allowed_decisions": ["approve", "reject"],
                },
                {
                    "action_name": "file_delete",
                    "allowed_decisions": ["approve", "reject"],
                },
                {
                    "action_name": "edit_file",
                    "allowed_decisions": ["approve", "reject"],
                },
            ],
        }

    await handler.produce_agent_events("t1", stream())

    assert turn.metadata["pending_action_count"] == 3
