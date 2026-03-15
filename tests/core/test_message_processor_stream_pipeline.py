"""Dedicated tests for the MessageProcessor token-to-TTS pipeline."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.models.websocket import TtsChunkMessage
from src.services.websocket_service.message_processor import (
    MessageProcessor,
    TurnStatus,
)


def _make_chunk(text: str, emotion: str | None = None, seq: int = 0) -> TtsChunkMessage:
    return TtsChunkMessage(
        sequence=seq,
        text=text,
        audio_base64=None,
        emotion=emotion,
        motion_name="neutral_idle",
        blendshape_name="neutral",
    )


@pytest.fixture
async def processor():
    message_processor = MessageProcessor(
        connection_id=uuid4(),
        user_id="test_user",
        tts_service=MagicMock(),
        mapper=MagicMock(),
    )
    try:
        yield message_processor
    finally:
        await message_processor.shutdown(cleanup_delay=0)


@pytest.mark.asyncio
async def test_stream_tokens_emit_tts_chunks_before_stream_end(
    processor: MessageProcessor,
):
    async def agent_stream():
        yield {"type": "stream_start"}
        await asyncio.sleep(0)
        yield {"type": "stream_token", "chunk": "Hello world! "}
        await asyncio.sleep(0)
        yield {"type": "stream_token", "chunk": "How are you"}
        await asyncio.sleep(0)
        yield {"type": "stream_token", "chunk": " doing today? This is fine."}
        yield {"type": "stream_end"}

    chunks_by_seq: dict[int, TtsChunkMessage] = {}

    def make_chunk_for_text(text, **kwargs):
        seq = len(chunks_by_seq)
        chunk = _make_chunk(text, seq=seq)
        chunks_by_seq[seq] = chunk
        return chunk

    with patch(
        "src.services.websocket_service.message_processor.event_handlers.synthesize_chunk",
        new=AsyncMock(
            side_effect=lambda **kw: _make_chunk(kw["text"], seq=kw["sequence"])
        ),
    ):
        turn_id = await processor.start_turn(
            "conv-ordered",
            "Test input",
            agent_stream=agent_stream(),
        )

        events = [event async for event in processor.stream_events(turn_id)]

    tts_events = [e for e in events if e["type"] == "tts_chunk"]
    types = [e["type"] for e in events]
    assert types[0] == "stream_start"
    assert types[-1] == "stream_end"
    assert len(tts_events) == 3

    assert [e["text"] for e in tts_events] == [
        "Hello world!",
        "How are you doing today?",
        "This is fine.",
    ]
    assert all("emotion" in e for e in tts_events)

    turn = await processor.get_turn(turn_id)
    assert turn is not None
    assert turn.status == TurnStatus.COMPLETED
    assert turn.token_queue is None
    assert processor.get_event_queue(turn_id) is None


@pytest.mark.asyncio
async def test_error_event_flushes_tokens_before_emitting_error(
    processor: MessageProcessor,
):
    async def agent_stream():
        yield {"type": "stream_start"}
        yield {
            "type": "stream_token",
            "chunk": "Partial sentence um... still going",
        }
        yield {"type": "error", "error": "boom"}

    with patch(
        "src.services.websocket_service.message_processor.event_handlers.synthesize_chunk",
        new=AsyncMock(
            side_effect=lambda **kw: _make_chunk(kw["text"], seq=kw["sequence"])
        ),
    ):
        turn_id = await processor.start_turn(
            "conv-error",
            "Test input",
            agent_stream=agent_stream(),
        )

        events = [event async for event in processor.stream_events(turn_id)]

    tts_events = [e for e in events if e["type"] == "tts_chunk"]
    types = [e["type"] for e in events]
    assert types[0] == "stream_start"
    assert types[-1] == "error"
    assert len(tts_events) == 2
    chunks = [e["text"] for e in tts_events]
    assert chunks == ["Partial sentence", "still going"]
    assert events[-1]["error"] == "boom"

    turn = await processor.get_turn(turn_id)
    assert turn is not None
    assert turn.status == TurnStatus.FAILED
    assert turn.token_queue is None


@pytest.mark.asyncio
async def test_stream_tokens_propagate_emotion(processor: MessageProcessor):
    async def agent_stream():
        yield {"type": "stream_start"}
        yield {"type": "stream_token", "chunk": "(laughing) That is fun."}
        yield {"type": "stream_end"}

    with patch(
        "src.services.websocket_service.message_processor.event_handlers.synthesize_chunk",
        new=AsyncMock(
            side_effect=lambda **kw: _make_chunk(
                kw["text"], emotion=kw["emotion"], seq=kw["sequence"]
            )
        ),
    ):
        turn_id = await processor.start_turn(
            "conv-emotion",
            "Test input",
            agent_stream=agent_stream(),
        )

        events = [event async for event in processor.stream_events(turn_id)]

    emotion_events = [event for event in events if event["type"] == "tts_chunk"]
    assert emotion_events and emotion_events[0]["emotion"] == "laughing"
    assert emotion_events[0]["text"] == "That is fun."
