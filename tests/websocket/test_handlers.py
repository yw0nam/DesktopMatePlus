"""Tests for WebSocket message handlers."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.services.websocket_service.manager.handlers import MessageHandler


class TestHandlerPersonaId:
    @pytest.mark.asyncio
    async def test_chat_message_uses_persona_id_not_persona(self):
        """Handler passes persona_id to agent_service.stream, not persona."""
        mock_send = AsyncMock()
        mock_close = AsyncMock()

        captured_kwargs = {}

        def mock_get_conn(conn_id):
            state = Mock()
            state.is_authenticated = True
            state.message_processor = AsyncMock()
            state.message_processor.start_turn = AsyncMock(return_value="turn-1")
            state.message_processor.add_task_to_turn = AsyncMock(return_value=True)
            return state

        handler = MessageHandler(mock_get_conn, mock_send, mock_close)

        mock_agent = MagicMock()
        mock_agent.support_image = False

        def fake_stream(**kwargs):
            captured_kwargs.update(kwargs)

            async def _gen():
                yield {"type": "stream_start", "turn_id": "t", "session_id": "s"}

            return _gen()

        mock_agent.stream = fake_stream

        mock_stm = MagicMock()
        mock_stm.get_chat_history = MagicMock(return_value=[])

        msg = MagicMock()
        msg.get = lambda k, d=None: {
            "content": "hello",
            "agent_id": "agent1",
            "user_id": "user1",
            "persona_id": "yuri",
            "session_id": None,
            "limit": 10,
            "images": None,
            "metadata": {},
            "tts_enabled": True,
            "reference_id": None,
        }.get(k, d)

        import uuid

        with (
            patch(
                "src.services.websocket_service.manager.handlers.get_agent_service",
                return_value=mock_agent,
            ),
            patch(
                "src.services.websocket_service.manager.handlers.get_stm_service",
                return_value=mock_stm,
            ),
            patch(
                "src.services.websocket_service.manager.handlers.get_ltm_service",
                return_value=None,
            ),
        ):
            await handler.handle_chat_message(uuid.uuid4(), msg, AsyncMock())

        assert (
            "persona_id" in captured_kwargs
        ), f"persona_id must be passed; got keys: {list(captured_kwargs.keys())}"
        assert (
            "persona" not in captured_kwargs
        ), f"persona must NOT be passed; got keys: {list(captured_kwargs.keys())}"
        assert (
            "tools" not in captured_kwargs
        ), f"tools must NOT be passed; got keys: {list(captured_kwargs.keys())}"
        assert captured_kwargs["persona_id"] == "yuri"
