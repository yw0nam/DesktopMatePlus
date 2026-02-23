"""Test cases for WebSocket service integration."""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from src.models.websocket import (
    AuthorizeMessage,
    InterruptStreamMessage,
    MessageType,
    PongMessage,
)
from src.services.websocket_service.manager import ConnectionState, WebSocketManager
from src.services.websocket_service.message_processor import (
    MessageProcessor,
)


class TestWebSocketManager:
    """Test cases for WebSocketManager class."""

    @pytest.fixture
    def manager(self):
        """Create a WebSocketManager instance for testing."""
        return WebSocketManager(ping_interval=10, pong_timeout=5)

    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket for testing."""
        websocket = AsyncMock()
        websocket.accept = AsyncMock()
        websocket.send_text = AsyncMock()
        websocket.close = AsyncMock()
        return websocket

    def test_manager_initialization(self, manager):
        """Test WebSocketManager initialization."""
        assert manager.ping_interval == 10
        assert manager.pong_timeout == 5
        assert len(manager.connections) == 0

    @pytest.mark.asyncio
    async def test_connect(self, manager, mock_websocket):
        """Test WebSocket connection."""
        connection_id = await manager.connect(mock_websocket)

        # Check that websocket was accepted
        mock_websocket.accept.assert_called_once()

        # Check that connection was stored
        assert connection_id in manager.connections
        connection_state = manager.connections[connection_id]
        assert connection_state.websocket == mock_websocket
        assert connection_state.connection_id == connection_id
        assert not connection_state.is_authenticated
        assert connection_state.message_processor is None

    @pytest.mark.asyncio
    async def test_disconnect(self, manager, mock_websocket):
        """Test WebSocket disconnection."""
        # Create a connection with a message processor
        connection_id = uuid4()
        connection_state = ConnectionState(mock_websocket, connection_id)
        connection_state.message_processor = Mock(spec=MessageProcessor)
        connection_state.message_processor.shutdown = AsyncMock()

        manager.connections[connection_id] = connection_state

        # Disconnect
        manager.disconnect(connection_id)

        # Check that connection was removed
        assert connection_id not in manager.connections

        # Allow some time for the async shutdown task to be scheduled
        await asyncio.sleep(0.01)

    @pytest.mark.asyncio
    async def test_send_message(self, manager, mock_websocket):
        """Test sending message to connection."""
        # Setup connection
        connection_id = uuid4()
        connection_state = ConnectionState(mock_websocket, connection_id)
        manager.connections[connection_id] = connection_state

        # Send a message
        from src.models.websocket import PingMessage

        message = PingMessage()
        await manager.send_message(connection_id, message)

        # Check that message was sent
        mock_websocket.send_text.assert_called_once()
        sent_data = mock_websocket.send_text.call_args[0][0]
        parsed_data = json.loads(sent_data)
        assert parsed_data["type"] == MessageType.PING

    @pytest.mark.asyncio
    async def test_send_message_unknown_connection(self, manager):
        """Test sending message to unknown connection."""
        from src.models.websocket import PingMessage

        message = PingMessage()

        # Should handle gracefully without raising exception
        await manager.send_message(uuid4(), message)

    def test_validate_token(self, manager):
        """Test token validation."""
        # For now, all tokens are valid (NOT FOR PRODUCTION)
        user_id = manager.validate_token("valid_token")
        assert user_id is not None
        assert user_id == "valid_token"

        # Even empty tokens return valid (NOT FOR PRODUCTION)
        assert manager.validate_token("") == "valid_token"
        assert manager.validate_token("   ") == "valid_token"
        assert manager.validate_token(None) == "valid_token"

    @pytest.mark.asyncio
    async def test_handle_authorize_success(self, manager, mock_websocket):
        """Test successful authorization."""
        # Setup connection
        connection_id = uuid4()
        connection_state = ConnectionState(mock_websocket, connection_id)
        manager.connections[connection_id] = connection_state

        # Handle authorization
        auth_message = AuthorizeMessage(token="valid_token")
        await manager.handle_authorize(connection_id, auth_message)

        # Check that connection is authenticated
        assert connection_state.is_authenticated
        assert connection_state.user_id is not None
        assert connection_state.message_processor is not None
        assert isinstance(connection_state.message_processor, MessageProcessor)

        # Check that success message was sent
        mock_websocket.send_text.assert_called_once()
        sent_data = mock_websocket.send_text.call_args[0][0]
        parsed_data = json.loads(sent_data)
        assert parsed_data["type"] == MessageType.AUTHORIZE_SUCCESS

    @pytest.mark.asyncio
    async def test_handle_authorize_failure(self, manager, mock_websocket):
        """Test authorization with empty token (currently always succeeds - NOT FOR PRODUCTION)."""
        # Setup connection
        connection_id = uuid4()
        connection_state = ConnectionState(mock_websocket, connection_id)
        manager.connections[connection_id] = connection_state

        # Handle authorization with empty token (still succeeds for now)
        auth_message = AuthorizeMessage(token="")
        await manager.handle_authorize(connection_id, auth_message)

        # Check that connection IS authenticated (NOT FOR PRODUCTION behavior)
        assert connection_state.is_authenticated
        assert connection_state.user_id == "valid_token"
        assert connection_state.message_processor is not None

        # Check that success message was sent
        mock_websocket.send_text.assert_called_once()
        sent_data = mock_websocket.send_text.call_args[0][0]
        parsed_data = json.loads(sent_data)
        assert parsed_data["type"] == MessageType.AUTHORIZE_SUCCESS

    @pytest.mark.asyncio
    async def test_handle_pong(self, manager, mock_websocket):
        """Test handling pong message."""
        # Setup connection
        connection_id = uuid4()
        connection_state = ConnectionState(mock_websocket, connection_id)
        manager.connections[connection_id] = connection_state

        # Handle pong
        pong_message = PongMessage()
        await manager.handle_pong(connection_id, pong_message)

        # Check that pong time was updated
        assert connection_state.last_pong_time is not None

    @pytest.mark.asyncio
    async def test_handle_chat_message(self, manager, mock_websocket):
        """Test handling chat message."""
        # Setup authenticated connection with message processor
        connection_id = uuid4()
        connection_state = ConnectionState(mock_websocket, connection_id)
        connection_state.is_authenticated = True
        connection_state.user_id = "test_user"
        connection_state.message_processor = MessageProcessor(
            connection_id=connection_id,
            user_id="test_user",
        )

        manager.connections[connection_id] = connection_state

        class FakeAgentService:
            async def stream(
                self,
                messages,
                session_id,
                tools=None,
                persona="",
                user_id="default_user",
                agent_id="default_agent",
                stm_service=None,
                ltm_service=None,
            ):
                yield {"type": "stream_start"}
                yield {"type": "stream_token", "chunk": "Hello, world!"}
                yield {"type": "stream_end"}

        class FakeSTMService:
            def get_chat_history(self, user_id, agent_id, session_id, limit=None):
                return []  # Return empty history for test

        class FakeLTMService:
            def search_memory(self, query, user_id, agent_id):
                return {"results": []}  # Return empty search results for test

        with (
            patch(
                "src.services.websocket_service.manager.handlers.get_agent_service",
                return_value=FakeAgentService(),
            ),
            patch(
                "src.services.websocket_service.manager.handlers.get_stm_service",
                return_value=FakeSTMService(),
            ),
            patch(
                "src.services.websocket_service.manager.handlers.get_ltm_service",
                return_value=FakeLTMService(),
            ),
        ):
            message_data = {
                "content": "Hello, world!",
                "agent_id": "test-agent",
                "user_id": "test-user",
                "persona": "test-persona",
                "limit": 10,
                "metadata": {"test": "data"},
            }
            await manager.handle_chat_message(connection_id, message_data)

            # Allow background tasks to process
            await asyncio.sleep(0.05)

        # Gather streamed events
        sent_events = [
            json.loads(call.args[0]) for call in mock_websocket.send_text.call_args_list
        ]
        event_types = [event.get("type") for event in sent_events]

        assert "stream_start" in event_types
        assert "tts_ready_chunk" in event_types
        assert "stream_end" in event_types

        # Verify TTS chunk reflects processed agent output
        tts_events = [
            event for event in sent_events if event.get("type") == "tts_ready_chunk"
        ]
        assert tts_events, "Expected at least one tts_ready_chunk event"
        assert any("Hello, world" in evt.get("chunk", "") for evt in tts_events)

        await connection_state.message_processor.shutdown()

    @pytest.mark.asyncio
    async def test_handle_chat_message_no_processor(self, manager, mock_websocket):
        """Test handling chat message without message processor."""
        # Setup connection without message processor
        connection_id = uuid4()
        connection_state = ConnectionState(mock_websocket, connection_id)
        manager.connections[connection_id] = connection_state

        # Handle chat message
        message_data = {"content": "Hello, world!"}
        await manager.handle_chat_message(connection_id, message_data)

        # Check that error message was sent
        mock_websocket.send_text.assert_called_once()
        sent_data = mock_websocket.send_text.call_args[0][0]
        parsed_data = json.loads(sent_data)
        assert parsed_data["type"] == MessageType.ERROR

    @pytest.mark.asyncio
    async def test_interrupt_active_turn(self, manager, mock_websocket):
        """Test interrupting active turn."""
        # Setup authenticated connection with message processor
        connection_id = uuid4()
        connection_state = ConnectionState(mock_websocket, connection_id)
        connection_state.is_authenticated = True
        connection_state.message_processor = Mock(spec=MessageProcessor)
        connection_state.message_processor.interrupt_turn = AsyncMock(return_value=True)

        manager.connections[connection_id] = connection_state

        # Interrupt specific turn
        result = await manager.interrupt_active_turn(connection_id, "turn_123")

        assert result is True
        connection_state.message_processor.interrupt_turn.assert_called_once_with(
            "turn_123", "Client requested interruption"
        )

        # Check that error message was sent
        mock_websocket.send_text.assert_called_once()
        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_data["type"] == MessageType.ERROR
        assert sent_data["code"] == 4003
        assert "interrupted" in sent_data["error"]

    @pytest.mark.asyncio
    async def test_interrupt_active_turn_no_active_turns(self, manager, mock_websocket):
        """Interrupt all turns responds with informative error when nothing to cancel."""

        connection_id = uuid4()
        connection_state = ConnectionState(mock_websocket, connection_id)
        connection_state.is_authenticated = True
        connection_state.message_processor = Mock(spec=MessageProcessor)
        connection_state.message_processor.get_active_turns = AsyncMock(return_value=[])
        connection_state.message_processor.interrupt_turn = AsyncMock(
            return_value=False
        )

        manager.connections[connection_id] = connection_state

        result = await manager.interrupt_active_turn(connection_id)

        assert result is False
        mock_websocket.send_text.assert_called_once()
        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_data["type"] == MessageType.ERROR
        assert sent_data["code"] == 4004
        assert "No active turns" in sent_data["error"]

    @pytest.mark.asyncio
    async def test_get_connection_stats(self, manager, mock_websocket):
        """Test getting connection statistics."""
        # Setup connection with message processor
        connection_id = uuid4()
        connection_state = ConnectionState(mock_websocket, connection_id)
        connection_state.is_authenticated = True
        connection_state.user_id = "test_user"
        connection_state.message_processor = Mock(spec=MessageProcessor)
        connection_state.message_processor.get_stats = Mock(
            return_value={"test": "stats"}
        )

        manager.connections[connection_id] = connection_state

        # Get stats
        stats = await manager.get_connection_stats(connection_id)

        assert stats is not None
        assert stats["connection_id"] == str(connection_id)
        assert stats["user_id"] == "test_user"
        assert stats["is_authenticated"] is True
        assert "created_at" in stats
        assert "test" in stats  # From message processor stats

    @pytest.mark.asyncio
    async def test_get_connection_stats_not_found(self, manager):
        """Test getting stats for non-existent connection."""
        stats = await manager.get_connection_stats(uuid4())
        assert stats is None

    @pytest.mark.asyncio
    async def test_handle_message_invalid_json(self, manager, mock_websocket):
        """Test handling invalid JSON message."""
        # Setup connection
        connection_id = uuid4()
        connection_state = ConnectionState(mock_websocket, connection_id)
        manager.connections[connection_id] = connection_state

        # Handle invalid JSON
        await manager.handle_message(connection_id, "invalid json")

        # Check that error message was sent
        mock_websocket.send_text.assert_called_once()
        sent_data = mock_websocket.send_text.call_args[0][0]
        parsed_data = json.loads(sent_data)
        assert parsed_data["type"] == MessageType.ERROR
        assert "JSON" in parsed_data["error"]

    @pytest.mark.asyncio
    async def test_handle_message_missing_type(self, manager, mock_websocket):
        """Test handling message without type."""
        # Setup connection
        connection_id = uuid4()
        connection_state = ConnectionState(mock_websocket, connection_id)
        manager.connections[connection_id] = connection_state

        # Handle message without type
        await manager.handle_message(connection_id, '{"data": "test"}')

        # Check that error message was sent
        mock_websocket.send_text.assert_called_once()
        sent_data = mock_websocket.send_text.call_args[0][0]
        parsed_data = json.loads(sent_data)
        assert parsed_data["type"] == MessageType.ERROR
        assert "type" in parsed_data["error"]

    @pytest.mark.asyncio
    async def test_handle_message_interrupt_stream(self, manager, mock_websocket):
        """interrupt_stream messages trigger MessageProcessor interruption."""

        connection_id = uuid4()
        connection_state = ConnectionState(mock_websocket, connection_id)
        connection_state.is_authenticated = True
        connection_state.message_processor = Mock(spec=MessageProcessor)
        connection_state.message_processor.interrupt_turn = AsyncMock(return_value=True)

        manager.connections[connection_id] = connection_state

        message = InterruptStreamMessage(turn_id="turn_abc")
        await manager.handle_message(connection_id, message.model_dump_json())

        connection_state.message_processor.interrupt_turn.assert_called_once_with(
            "turn_abc", "Client requested interruption"
        )
        mock_websocket.send_text.assert_called_once()
        payload = json.loads(mock_websocket.send_text.call_args[0][0])
        assert payload["type"] == MessageType.ERROR
        assert payload["code"] == 4003

    @pytest.mark.asyncio
    async def test_handle_message_interrupt_stream_requires_auth(
        self, manager, mock_websocket
    ):
        """Unauthenticated connections cannot interrupt streams."""

        connection_id = uuid4()
        connection_state = ConnectionState(mock_websocket, connection_id)
        manager.connections[connection_id] = connection_state

        message = InterruptStreamMessage(turn_id=None)
        await manager.handle_message(connection_id, message.model_dump_json())

        mock_websocket.send_text.assert_called_once()
        payload = json.loads(mock_websocket.send_text.call_args[0][0])
        assert payload["type"] == MessageType.ERROR
        assert "Authentication" in payload["error"]


def test_websocket_service_imports():
    """Test that websocket service imports work correctly."""
    from src.services.websocket_service import MessageProcessor, websocket_manager

    assert websocket_manager is not None
    assert MessageProcessor is not None


if __name__ == "__main__":
    pytest.main([__file__])
