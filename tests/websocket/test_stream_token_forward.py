"""BE-BUG-4: stream_token events must be forwarded to WS clients in addition to token queue.

KI-23: Emotion emoji tags must be stripped from stream_token chunks sent to FE.
"""

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


class TestStreamTokenEmotionTagStrip:
    """KI-23: Emotion emoji tags stripped from stream_token before forwarding to FE."""

    async def test_emotion_emoji_stripped_from_fe_chunk(self) -> None:
        """stream_token forwarded to FE must have emotion emojis stripped from chunk."""
        processor = MagicMock()
        processor._normalize_event = lambda turn_id, raw: raw
        processor._put_event = AsyncMock()
        processor.update_turn_status = AsyncMock()
        processor.complete_turn = AsyncMock()
        processor.fail_turn = AsyncMock()
        processor._wait_for_tts_tasks = AsyncMock()
        processor.is_connection_closing = MagicMock(return_value=False)

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

        token_event = {
            "type": "stream_token",
            "turn_id": "turn-1",
            "chunk": "😊 안녕하세요!",
        }
        stream = _make_stream([token_event])

        await handler.produce_agent_events("turn-1", stream)

        fe_calls = [
            call
            for call in processor._put_event.call_args_list
            if call.args[1].get("type") == "stream_token"
        ]
        assert fe_calls, "stream_token not forwarded to FE"
        forwarded_chunk = fe_calls[0].args[1]["chunk"]
        assert "😊" not in forwarded_chunk, "Emotion emoji must be stripped for FE"
        assert "안녕하세요" in forwarded_chunk, "Text content must be preserved"

    async def test_token_queue_receives_original_chunk_with_emoji(self) -> None:
        """TTS pipeline (_put_token_event) must receive the original chunk with emoji intact."""
        processor = MagicMock()
        processor._normalize_event = lambda turn_id, raw: raw
        processor._put_event = AsyncMock()
        processor.update_turn_status = AsyncMock()
        processor.complete_turn = AsyncMock()
        processor.fail_turn = AsyncMock()
        processor._wait_for_tts_tasks = AsyncMock()
        processor.is_connection_closing = MagicMock(return_value=False)

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

        token_event = {
            "type": "stream_token",
            "turn_id": "turn-1",
            "chunk": "😊 hello",
        }
        stream = _make_stream([token_event])

        await handler.produce_agent_events("turn-1", stream)

        # TTS pipeline must receive original event with emoji
        handler._put_token_event.assert_called_once_with("turn-1", token_event)
        original_chunk = handler._put_token_event.call_args.args[1]["chunk"]
        assert (
            "😊" in original_chunk
        ), "TTS pipeline must receive emoji for emotion detection"

    async def test_chunk_without_emoji_forwarded_unchanged(self) -> None:
        """Chunks without emotion emojis are forwarded to FE unchanged."""
        processor = MagicMock()
        processor._normalize_event = lambda turn_id, raw: raw
        processor._put_event = AsyncMock()
        processor.update_turn_status = AsyncMock()
        processor.complete_turn = AsyncMock()
        processor.fail_turn = AsyncMock()
        processor._wait_for_tts_tasks = AsyncMock()
        processor.is_connection_closing = MagicMock(return_value=False)

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

        token_event = {
            "type": "stream_token",
            "turn_id": "turn-1",
            "chunk": "안녕하세요!",
        }
        stream = _make_stream([token_event])

        await handler.produce_agent_events("turn-1", stream)

        fe_calls = [
            call
            for call in processor._put_event.call_args_list
            if call.args[1].get("type") == "stream_token"
        ]
        assert fe_calls
        forwarded_chunk = fe_calls[0].args[1]["chunk"]
        assert forwarded_chunk == "안녕하세요!"
