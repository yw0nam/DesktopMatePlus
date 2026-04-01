"""BE-BUG-4: stream_token events must be forwarded to WS clients in addition to token queue."""

from unittest.mock import AsyncMock, MagicMock

from src.services.websocket_service.message_processor.event_handlers import EventHandler


async def _make_stream(events: list[dict]):
    """Async generator yielding given events."""
    for e in events:
        yield e


class TestStreamTokenForward:
    """BE-BUG-4: stream_token forwarded to processor._put_event after _put_token_event."""

    async def test_stream_token_is_forwarded_to_ws_client(self) -> None:
        """After _put_token_event, processor._put_event must also be called for stream_token."""
        processor = MagicMock()
        processor._normalize_event = lambda turn_id, raw: raw
        processor._put_event = AsyncMock()
        processor.update_turn_status = AsyncMock()
        processor.complete_turn = AsyncMock()
        processor.fail_turn = AsyncMock()
        processor._wait_for_tts_tasks = AsyncMock()
        processor.is_connection_closing = MagicMock(return_value=False)

        # Token queue mock
        token_queue = AsyncMock()
        token_queue.put = AsyncMock()
        token_queue.qsize = MagicMock(return_value=0)
        turn = MagicMock()
        turn.token_queue = token_queue
        turn.token_stream_closed = False
        processor.turns = {"turn-1": turn}

        handler = EventHandler(processor)
        handler._put_token_event = AsyncMock()
        handler._signal_token_stream_closed = AsyncMock()
        handler._wait_for_token_queue = AsyncMock()

        token_event = {"type": "stream_token", "turn_id": "turn-1", "chunk": "hello"}
        stream = _make_stream([token_event])

        await handler.produce_agent_events("turn-1", stream)

        # _put_token_event must have been called
        handler._put_token_event.assert_called_once_with("turn-1", token_event)

        # processor._put_event must ALSO have been called with the stream_token event
        forward_calls = [
            call
            for call in processor._put_event.call_args_list
            if call.args[1].get("type") == "stream_token"
        ]
        assert (
            forward_calls
        ), "stream_token event was NOT forwarded to WS client via _put_event"
