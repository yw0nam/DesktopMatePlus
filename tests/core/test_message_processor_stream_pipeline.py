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
        keyframes=[{"duration": 0.3, "targets": {"neutral": 1.0}}],
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
    # Each sentence is long enough (>= min_chunk_length=50) to be emitted individually
    long_sentence_1 = "Hello world, this is indeed a long enough sentence to emit."
    long_sentence_2 = "How are you doing today on this fine and wonderful afternoon?"
    long_sentence_3 = (
        "Everything is going well, and I am quite satisfied with the results."
    )

    async def agent_stream():
        yield {"type": "stream_start"}
        await asyncio.sleep(0)
        yield {"type": "stream_token", "chunk": long_sentence_1 + " "}
        await asyncio.sleep(0)
        yield {"type": "stream_token", "chunk": long_sentence_2 + " "}
        await asyncio.sleep(0)
        yield {"type": "stream_token", "chunk": long_sentence_3}
        yield {"type": "stream_end"}

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
        long_sentence_1,
        long_sentence_2,
        long_sentence_3,
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
    # "Partial sentence um... still going" is below min_chunk_length (40), so it stays
    # buffered and is flushed as one chunk. TTSTextProcessor strips the filler "um..."
    # leaving a single cleaned chunk.
    assert len(tts_events) == 1
    chunks = [e["text"] for e in tts_events]
    assert chunks == ["Partial sentence still going"]
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
