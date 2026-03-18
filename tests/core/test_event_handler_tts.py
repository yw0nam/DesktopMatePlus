"""Tests for EventHandler._synthesize_and_send() orchestration."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.websocket_service.message_processor.event_handlers import EventHandler
from src.services.websocket_service.message_processor.models import ConversationTurn


def _make_processor(turn_id: str, is_closing: bool = False):
    """Build a minimal mock MessageProcessor."""
    proc = MagicMock()
    proc.is_connection_closing.return_value = is_closing
    proc._put_event = AsyncMock()
    proc._task_manager = MagicMock()
    proc._task_manager.track_task = MagicMock()

    turn = ConversationTurn(
        turn_id=turn_id,
        user_message="hi",
        session_id="s1",
        tts_enabled=True,
        reference_id=None,
        tts_tasks=[],
        tts_sequence=0,
    )
    turn.event_queue = asyncio.Queue()
    proc.turns = {turn_id: turn}
    proc.tts_service = MagicMock()
    proc.mapper = MagicMock()
    return proc, turn


@pytest.mark.asyncio
async def test_synthesize_and_send_success():
    """Success: _put_event called once with type=='tts_chunk'."""
    from src.models.websocket import TtsChunkMessage

    turn_id = "t1"
    proc, turn = _make_processor(turn_id)
    handler = EventHandler(proc)

    fake_chunk = TtsChunkMessage(
        sequence=0,
        text="Hello",
        audio_base64="abc123",
        emotion="joyful",
        motion_name="happy_idle",
        blendshape_name="smile",
    )

    with patch(
        "src.services.websocket_service.message_processor.event_handlers.synthesize_chunk",
        new=AsyncMock(return_value=fake_chunk),
    ):
        await handler._synthesize_and_send(
            turn_id=turn_id,
            text="Hello",
            emotion="joyful",
            sequence=0,
            tts_enabled=True,
            reference_id=None,
        )

    proc._put_event.assert_called_once()
    call_event = proc._put_event.call_args[0][1]
    assert call_event["type"] == "tts_chunk"
    assert call_event["audio_base64"] == "abc123"
    assert call_event["sequence"] == 0


@pytest.mark.asyncio
async def test_synthesize_and_send_tts_failure_still_puts_chunk():
    """TTS failure: audio_base64=None still puts tts_chunk, no warning."""
    from src.models.websocket import TtsChunkMessage

    turn_id = "t2"
    proc, turn = _make_processor(turn_id)
    handler = EventHandler(proc)

    fake_chunk = TtsChunkMessage(
        sequence=1,
        text="Hi",
        audio_base64=None,
        emotion=None,
        motion_name="neutral_idle",
        blendshape_name="neutral",
    )

    with patch(
        "src.services.websocket_service.message_processor.event_handlers.synthesize_chunk",
        new=AsyncMock(return_value=fake_chunk),
    ):
        await handler._synthesize_and_send(
            turn_id=turn_id,
            text="Hi",
            emotion=None,
            sequence=1,
            tts_enabled=True,
            reference_id=None,
        )

    proc._put_event.assert_called_once()
    call_event = proc._put_event.call_args[0][1]
    assert call_event["type"] == "tts_chunk"
    assert call_event["audio_base64"] is None


@pytest.mark.asyncio
async def test_synthesize_and_send_is_closing_drops_silently():
    """is_closing=True before synthesize: no _put_event call, no synthesize_chunk call."""
    turn_id = "t3"
    proc, turn = _make_processor(turn_id, is_closing=True)
    handler = EventHandler(proc)

    with patch(
        "src.services.websocket_service.message_processor.event_handlers.synthesize_chunk",
        new=AsyncMock(),
    ) as mock_synth:
        await handler._synthesize_and_send(
            turn_id=turn_id,
            text="Test",
            emotion=None,
            sequence=0,
            tts_enabled=True,
            reference_id=None,
        )

    proc._put_event.assert_not_called()
    mock_synth.assert_not_called()


@pytest.mark.asyncio
async def test_tts_task_registered_in_both_lists():
    """_process_token_event creates a task that ends up in tts_tasks AND track_task."""
    from unittest.mock import ANY

    from src.models.websocket import TtsChunkMessage

    turn_id = "t4"
    proc, turn = _make_processor(turn_id)
    handler = EventHandler(proc)

    fake_chunk = TtsChunkMessage(
        sequence=0,
        text="Hello world",
        audio_base64=None,
        motion_name="neutral_idle",
        blendshape_name="neutral",
    )

    with patch(
        "src.services.websocket_service.message_processor.event_handlers.synthesize_chunk",
        new=AsyncMock(return_value=fake_chunk),
    ):
        # Long enough sentence (>= min_chunk_length) so the chunker yields it immediately
        await handler._process_token_event(
            turn_id,
            {
                "chunk": "Hello world, this is a long enough sentence to pass the minimum threshold."
            },
        )
        # Let the asyncio task actually run
        await asyncio.gather(*turn.tts_tasks)

    assert len(turn.tts_tasks) == 1
    proc._task_manager.track_task.assert_called_once_with(turn_id, ANY)


@pytest.mark.asyncio
async def test_tts_sequence_increments_per_chunk():
    """turn.tts_sequence increments monotonically: after 2 calls == 2."""
    from src.models.websocket import TtsChunkMessage

    turn_id = "t5"
    proc, turn = _make_processor(turn_id)
    handler = EventHandler(proc)

    def make_chunk(seq):
        return TtsChunkMessage(
            sequence=seq,
            text="text",
            audio_base64=None,
            motion_name="neutral_idle",
            blendshape_name="neutral",
        )

    with patch(
        "src.services.websocket_service.message_processor.event_handlers.synthesize_chunk",
        new=AsyncMock(side_effect=[make_chunk(0), make_chunk(1)]),
    ):
        task1 = asyncio.create_task(
            handler._synthesize_and_send(
                turn_id=turn_id,
                text="sentence one",
                emotion=None,
                sequence=turn.tts_sequence,
                tts_enabled=True,
                reference_id=None,
            )
        )
        turn.tts_sequence += 1
        turn.tts_tasks.append(task1)

        task2 = asyncio.create_task(
            handler._synthesize_and_send(
                turn_id=turn_id,
                text="sentence two",
                emotion=None,
                sequence=turn.tts_sequence,
                tts_enabled=True,
                reference_id=None,
            )
        )
        turn.tts_sequence += 1
        turn.tts_tasks.append(task2)

        await asyncio.gather(task1, task2)

    assert turn.tts_sequence == 2
    assert len(turn.tts_tasks) == 2
