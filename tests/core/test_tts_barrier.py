"""Unit tests for _wait_for_tts_tasks() TTS barrier logic."""

from __future__ import annotations

import asyncio
from unittest.mock import patch
from uuid import uuid4

import pytest

from src.services.websocket_service.message_processor import MessageProcessor


@pytest.fixture
async def processor():
    from unittest.mock import MagicMock

    mp = MessageProcessor(
        connection_id=uuid4(),
        user_id="test_user",
        tts_service=MagicMock(),
        mapper=MagicMock(),
    )
    try:
        yield mp
    finally:
        await mp.shutdown(cleanup_delay=0)


async def test_wait_for_tts_tasks_no_turn(processor: MessageProcessor):
    """Unknown turn_id: returns immediately without error."""
    await processor._wait_for_tts_tasks("nonexistent-turn-id")  # must not raise


async def test_wait_for_tts_tasks_empty_list(processor: MessageProcessor):
    """turn.tts_tasks is empty: returns immediately."""
    turn_id = await processor.start_turn("sess-1", "hi")
    turn = processor.turns.get(turn_id)
    assert turn is not None
    turn.tts_tasks = []
    await processor._wait_for_tts_tasks(turn_id)  # must not raise


async def test_barrier_waits_for_all_tts_tasks(processor: MessageProcessor):
    """All tts_tasks complete before _wait_for_tts_tasks returns."""
    turn_id = await processor.start_turn("sess-2", "hi")
    turn = processor.turns.get(turn_id)
    assert turn is not None

    task1_done = asyncio.Event()
    task2_done = asyncio.Event()

    async def slow_task(event: asyncio.Event) -> None:
        await asyncio.sleep(0.05)
        event.set()

    turn.tts_tasks = [
        asyncio.create_task(slow_task(task1_done)),
        asyncio.create_task(slow_task(task2_done)),
    ]

    await processor._wait_for_tts_tasks(turn_id)

    assert task1_done.is_set()
    assert task2_done.is_set()


async def test_barrier_timeout_logs_and_continues(processor: MessageProcessor):
    """Timeout: logger.warning called, no deadlock, no warning event queued."""
    turn_id = await processor.start_turn("sess-3", "hi")
    turn = processor.turns.get(turn_id)
    assert turn is not None

    async def hanging_task() -> None:
        await asyncio.sleep(9999)

    hanging = asyncio.create_task(hanging_task())
    turn.tts_tasks = [hanging]

    # Override timeout to a tiny value
    from src.configs.settings import get_settings

    original_timeout = get_settings().websocket.tts_barrier_timeout_seconds
    get_settings().websocket.__dict__["tts_barrier_timeout_seconds"] = 0.05

    try:
        with patch(
            "src.services.websocket_service.message_processor.processor.logger"
        ) as mock_logger:
            await processor._wait_for_tts_tasks(turn_id)
            mock_logger.warning.assert_called_once()
    finally:
        get_settings().websocket.__dict__[
            "tts_barrier_timeout_seconds"
        ] = original_timeout
        hanging.cancel()
        try:
            await hanging
        except (asyncio.CancelledError, Exception):
            pass


async def test_stream_end_arrives_after_last_tts_chunk(processor: MessageProcessor):
    """stream_end is always after the last tts_chunk in collected events."""

    async def fake_tts_task(p: MessageProcessor, tid: str, seq: int) -> None:
        await asyncio.sleep(0.02)
        await p._put_event(
            tid,
            {
                "type": "tts_chunk",
                "sequence": seq,
                "audio_base64": "abc",
                "text": f"s{seq}",
                "motion_name": "idle",
                "blendshape_name": "neutral",
                "emotion": None,
            },
        )

    async def agent_stream():
        yield {"type": "stream_start"}
        yield {"type": "stream_token", "chunk": "Hello world! "}
        yield {"type": "stream_end"}

    turn_id = await processor.start_turn(
        "sess-order",
        "hi",
        agent_stream=agent_stream(),
    )
    turn = processor.turns.get(turn_id)
    assert turn is not None
    turn.tts_tasks = [
        asyncio.create_task(fake_tts_task(processor, turn_id, 0)),
        asyncio.create_task(fake_tts_task(processor, turn_id, 1)),
    ]

    events = [e async for e in processor.stream_events(turn_id)]
    types = [e["type"] for e in events]

    assert "stream_end" in types
    tts_chunk_indices = [i for i, t in enumerate(types) if t == "tts_chunk"]
    stream_end_index = types.index("stream_end")

    if tts_chunk_indices:
        assert stream_end_index > max(tts_chunk_indices), (
            f"stream_end at {stream_end_index} must be after "
            f"last tts_chunk at {max(tts_chunk_indices)}"
        )
