"""Dedicated tests for the MessageProcessor token-to-TTS pipeline."""

import asyncio
from uuid import uuid4

import pytest

from src.services.websocket_service.message_processor import (
    MessageProcessor,
    TurnStatus,
)


@pytest.fixture
async def processor():
    message_processor = MessageProcessor(connection_id=uuid4(), user_id="test_user")
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
        yield {"type": "stream_token", "chunk": "Hello"}
        await asyncio.sleep(0)
        yield {"type": "stream_token", "chunk": "world"}
        yield {"type": "stream_end"}

    turn_id = await processor.start_turn(
        "conv-ordered",
        "Test input",
        agent_stream=agent_stream(),
    )

    events = [event async for event in processor.stream_events(turn_id)]

    assert [event["type"] for event in events] == [
        "stream_start",
        "tts_ready_chunk",
        "tts_ready_chunk",
        "stream_end",
    ]
    assert [
        event["chunk"] for event in events if event["type"] == "tts_ready_chunk"
    ] == [
        "Hello",
        "world",
    ]

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
        yield {"type": "stream_token", "chunk": "Partial"}
        yield {"type": "error", "error": "boom"}

    turn_id = await processor.start_turn(
        "conv-error",
        "Test input",
        agent_stream=agent_stream(),
    )

    events = [event async for event in processor.stream_events(turn_id)]

    assert [event["type"] for event in events] == [
        "stream_start",
        "tts_ready_chunk",
        "error",
    ]
    assert events[1]["chunk"] == "Partial"
    assert events[-1]["error"] == "boom"

    turn = await processor.get_turn(turn_id)
    assert turn is not None
    assert turn.status == TurnStatus.FAILED
    assert turn.token_queue is None
