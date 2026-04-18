"""Unit tests for HitL event handling in WebSocket service layer (Phase 4)."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.models.websocket import ErrorMessage
from src.services.websocket_service.message_processor.models import TurnStatus


class TestHitLRequestInProduceAgentEvents:
    """Tests for hitl_request handling in EventHandler.produce_agent_events."""

    async def test_hitl_request_updates_turn_status_to_awaiting_approval(self):
        """produce_agent_events with hitl_request event sets turn status to AWAITING_APPROVAL."""
        from src.services.websocket_service.message_processor.processor import (
            MessageProcessor,
        )

        connection_id = uuid4()
        processor = MessageProcessor(connection_id=connection_id, user_id="test_user")

        async def fake_agent_stream():
            yield {
                "type": "hitl_request",
                "request_id": "req-1",
                "tool_name": "dangerous_tool",
                "tool_args": {"x": "1"},
                "session_id": "sess-1",
            }

        turn_id = await processor.start_turn(
            session_id="sess-1",
            user_input="test",
            agent_stream=fake_agent_stream(),
        )

        # Wait for producer to finish processing
        await asyncio.sleep(0.1)

        turn = processor.turns.get(turn_id)
        assert turn is not None
        assert turn.status == TurnStatus.AWAITING_APPROVAL

        await processor.shutdown(cleanup_delay=0)

    async def test_hitl_request_terminates_stream_events(self):
        """stream_events breaks on hitl_request and does not hang."""
        from src.services.websocket_service.message_processor.processor import (
            MessageProcessor,
        )

        connection_id = uuid4()
        processor = MessageProcessor(connection_id=connection_id, user_id="test_user")

        async def fake_agent_stream():
            yield {"type": "stream_start"}
            yield {
                "type": "hitl_request",
                "request_id": "req-1",
                "tool_name": "tool",
                "tool_args": {},
                "session_id": "sess-1",
            }

        turn_id = await processor.start_turn(
            session_id="sess-1",
            user_input="test",
            agent_stream=fake_agent_stream(),
        )

        events = []
        async for event in processor.stream_events(turn_id):
            events.append(event)

        event_types = [e.get("type") for e in events]
        assert "hitl_request" in event_types
        # stream_events should have exited without hanging
        assert "stream_end" not in event_types

        await processor.shutdown(cleanup_delay=0)

    async def test_hitl_request_no_cleanup_on_stream_events(self):
        """cleanup is NOT called after hitl_request -- turn stays alive for resume."""
        from src.services.websocket_service.message_processor.processor import (
            MessageProcessor,
        )

        connection_id = uuid4()
        processor = MessageProcessor(connection_id=connection_id, user_id="test_user")

        async def fake_agent_stream():
            yield {
                "type": "hitl_request",
                "request_id": "req-1",
                "tool_name": "tool",
                "tool_args": {},
                "session_id": "sess-1",
            }

        turn_id = await processor.start_turn(
            session_id="sess-1",
            user_input="test",
            agent_stream=fake_agent_stream(),
        )

        events = []
        async for event in processor.stream_events(turn_id):
            events.append(event)

        # Turn should still exist and not be cleaned up
        turn = processor.turns.get(turn_id)
        assert turn is not None
        assert turn_id not in processor._cleaned_turns
        # Current turn ID should still be set (not cleared by cleanup)
        assert processor._current_turn_id == turn_id

        await processor.shutdown(cleanup_delay=0)


class TestTokenStreamClosedResetOnAttach:
    """Tests for token_stream_closed reset in attach_agent_stream."""

    async def test_token_stream_closed_reset_on_attach_agent_stream(self):
        """token_stream_closed is reset to False when attaching a new agent stream."""
        from src.services.websocket_service.message_processor.processor import (
            MessageProcessor,
        )

        connection_id = uuid4()
        processor = MessageProcessor(connection_id=connection_id, user_id="test_user")

        async def fake_hitl_stream():
            yield {
                "type": "hitl_request",
                "request_id": "req-1",
                "tool_name": "tool",
                "tool_args": {},
                "session_id": "sess-1",
            }

        turn_id = await processor.start_turn(
            session_id="sess-1",
            user_input="test",
            agent_stream=fake_hitl_stream(),
        )

        # Wait for producer to process hitl_request and signal token stream closed
        await asyncio.sleep(0.1)

        turn = processor.turns.get(turn_id)
        assert turn is not None
        # After hitl_request, token_stream_closed should be True
        assert turn.token_stream_closed is True

        # Now attach a new stream (simulating resume)
        async def fake_resume_stream():
            yield {"type": "stream_start"}
            yield {"type": "stream_end"}

        await processor.attach_agent_stream(turn_id, fake_resume_stream())

        # token_stream_closed should be reset to False
        assert turn.token_stream_closed is False

        await processor.shutdown(cleanup_delay=0)


class TestHitLResponseHandler:
    """Tests for handle_hitl_response in MessageHandler."""

    async def test_hitl_response_resumes_agent_stream(self):
        """handle_hitl_response calls resume_after_approval and attach_agent_stream."""
        from src.services.websocket_service.manager.handlers import MessageHandler

        # Set up mocks
        mock_processor = MagicMock()
        mock_processor._current_turn_id = "turn-1"
        mock_turn = MagicMock()
        mock_turn.status = TurnStatus.AWAITING_APPROVAL
        mock_turn.session_id = "sess-1"
        mock_turn.metadata = {"interrupt_id": "iid-1"}
        mock_processor.turns = {"turn-1": mock_turn}
        mock_processor.update_turn_status = AsyncMock()
        mock_processor.attach_agent_stream = AsyncMock()
        mock_processor.add_task_to_turn = AsyncMock(return_value=True)

        mock_connection = MagicMock()
        mock_connection.is_authenticated = True
        mock_connection.message_processor = mock_processor

        get_connection_fn = MagicMock(return_value=mock_connection)
        send_message_fn = AsyncMock()
        close_connection_fn = AsyncMock()

        handler = MessageHandler(
            get_connection_fn, send_message_fn, close_connection_fn
        )

        mock_agent_service = MagicMock()

        async def fake_resume_stream():
            yield {"type": "stream_end"}

        mock_agent_service.resume_after_approval = MagicMock(
            return_value=fake_resume_stream()
        )

        forward_events_fn = AsyncMock()

        with patch(
            "src.services.websocket_service.manager.handlers.get_agent_service",
            return_value=mock_agent_service,
        ):
            await handler.handle_hitl_response(
                connection_id=uuid4(),
                message_data={"request_id": "req-1", "approved": True},
                forward_events_fn=forward_events_fn,
            )

        # Verify status was updated to PROCESSING
        mock_processor.update_turn_status.assert_called_with(
            "turn-1", TurnStatus.PROCESSING
        )
        # Verify agent stream was attached
        mock_processor.attach_agent_stream.assert_called_once()
        # Verify resume_after_approval was called with correct args
        mock_agent_service.resume_after_approval.assert_called_once_with(
            session_id="sess-1",
            approved=True,
            request_id="req-1",
            interrupt_id="iid-1",
        )

    async def test_hitl_response_rejects_when_no_pending_approval(self):
        """Returns error when turn is not in AWAITING_APPROVAL status."""
        from src.services.websocket_service.manager.handlers import MessageHandler

        mock_processor = MagicMock()
        mock_processor._current_turn_id = "turn-1"
        mock_turn = MagicMock()
        mock_turn.status = TurnStatus.PROCESSING  # Not AWAITING_APPROVAL
        mock_processor.turns = {"turn-1": mock_turn}

        mock_connection = MagicMock()
        mock_connection.is_authenticated = True
        mock_connection.message_processor = mock_processor

        get_connection_fn = MagicMock(return_value=mock_connection)
        send_message_fn = AsyncMock()
        close_connection_fn = AsyncMock()

        handler = MessageHandler(
            get_connection_fn, send_message_fn, close_connection_fn
        )

        await handler.handle_hitl_response(
            connection_id=uuid4(),
            message_data={"request_id": "req-1", "approved": True},
            forward_events_fn=AsyncMock(),
        )

        # Should have sent an error message
        send_message_fn.assert_called_once()
        sent_msg = send_message_fn.call_args[0][1]
        assert isinstance(sent_msg, ErrorMessage)
        assert "pending approval" in sent_msg.error.lower()

    async def test_hitl_response_rejects_when_no_active_session(self):
        """Returns error when no message processor exists."""
        from src.services.websocket_service.manager.handlers import MessageHandler

        mock_connection = MagicMock()
        mock_connection.is_authenticated = True
        mock_connection.message_processor = None

        get_connection_fn = MagicMock(return_value=mock_connection)
        send_message_fn = AsyncMock()
        close_connection_fn = AsyncMock()

        handler = MessageHandler(
            get_connection_fn, send_message_fn, close_connection_fn
        )

        await handler.handle_hitl_response(
            connection_id=uuid4(),
            message_data={"request_id": "req-1", "approved": True},
            forward_events_fn=AsyncMock(),
        )

        send_message_fn.assert_called_once()
        sent_msg = send_message_fn.call_args[0][1]
        assert isinstance(sent_msg, ErrorMessage)


class TestWSRoutingHitLResponse:
    """Tests for HITL_RESPONSE routing in WebSocketManager.handle_message."""

    async def test_ws_routing_hitl_response(self):
        """websocket_manager routes HITL_RESPONSE to handler."""
        from src.services.websocket_service.manager.websocket_manager import (
            WebSocketManager,
        )

        manager = WebSocketManager()

        # Create a mock connection state
        connection_id = uuid4()
        mock_connection = MagicMock()
        mock_connection.is_authenticated = True
        mock_connection.message_processor = MagicMock()
        manager.connections[connection_id] = mock_connection

        # Mock the handler
        manager._message_handler.handle_hitl_response = AsyncMock()

        raw_message = json.dumps(
            {
                "type": "hitl_response",
                "request_id": "req-1",
                "approved": True,
            }
        )

        await manager.handle_message(connection_id, raw_message)

        # Verify handler was called with correct connection_id
        manager._message_handler.handle_hitl_response.assert_called_once()
        call_args = manager._message_handler.handle_hitl_response.call_args
        assert call_args[0][0] == connection_id

    async def test_ws_routing_hitl_response_requires_auth(self):
        """HITL_RESPONSE should require authentication."""
        from src.services.websocket_service.manager.websocket_manager import (
            WebSocketManager,
        )

        manager = WebSocketManager()

        connection_id = uuid4()
        mock_connection = MagicMock()
        mock_connection.is_authenticated = False
        mock_connection.message_processor = None
        manager.connections[connection_id] = mock_connection

        # Mock send_message to capture the error
        manager.send_message = AsyncMock()

        raw_message = json.dumps(
            {
                "type": "hitl_response",
                "request_id": "req-1",
                "approved": True,
            }
        )

        await manager.handle_message(connection_id, raw_message)

        # Should send auth error, not call handler
        manager.send_message.assert_called_once()
        sent_msg = manager.send_message.call_args[0][1]
        assert isinstance(sent_msg, ErrorMessage)
        assert "authentication" in sent_msg.error.lower()
