"""Integration tests for TTS flow refactor (T1~T5).

All scenarios run with mocked TTS engine — no real TTS server required.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from src.services.websocket_service.message_processor import MessageProcessor


@pytest.fixture
async def processor():
    mp = MessageProcessor(
        connection_id=uuid4(),
        user_id="integration_user",
        tts_service=MagicMock(),
        mapper=MagicMock(),
    )
    try:
        yield mp
    finally:
        await mp.shutdown(cleanup_delay=0)


async def _fake_synthesize_and_send(
    processor: MessageProcessor,
    turn_id: str,
    sequence: int,
    audio_base64: str | None = "fakeaudio==",
    delay: float = 0.01,
) -> None:
    await asyncio.sleep(delay)
    await processor._put_event(
        turn_id,
        {
            "type": "tts_chunk",
            "sequence": sequence,
            "text": f"sentence {sequence}",
            "audio_base64": audio_base64,
            "motion_name": "idle",
            "blendshape_name": "neutral",
            "emotion": None,
        },
    )


async def test_tts_enabled_normal_flow(processor: MessageProcessor):
    """tts_chunk received, audio non-null, sequence order, stream_end last."""

    async def agent_stream() -> AsyncIterator[dict[str, Any]]:
        yield {"type": "stream_start"}
        yield {"type": "stream_token", "chunk": "Hello world!"}
        yield {"type": "stream_end"}

    turn_id = await processor.start_turn(
        "sess-normal", "hi", agent_stream=agent_stream()
    )
    turn = processor.turns.get(turn_id)
    assert turn is not None
    turn.tts_tasks = [
        asyncio.create_task(
            _fake_synthesize_and_send(processor, turn_id, 0, "audiobase64==")
        )
    ]

    events = [e async for e in processor.stream_events(turn_id)]
    types = [e["type"] for e in events]
    tts_chunks = [e for e in events if e["type"] == "tts_chunk"]

    assert len(tts_chunks) >= 1
    assert all(c["audio_base64"] is not None for c in tts_chunks)
    sequences = [c["sequence"] for c in tts_chunks]
    assert sequences == sorted(sequences)
    assert types[-1] == "stream_end"


async def test_tts_disabled_sends_null_audio(processor: MessageProcessor):
    """tts_chunk with audio_base64=null, motion/blendshape present."""

    async def agent_stream() -> AsyncIterator[dict[str, Any]]:
        yield {"type": "stream_start"}
        yield {"type": "stream_token", "chunk": "Hello!"}
        yield {"type": "stream_end"}

    turn_id = await processor.start_turn(
        "sess-disabled", "hi", agent_stream=agent_stream()
    )
    turn = processor.turns.get(turn_id)
    assert turn is not None
    turn.tts_tasks = [
        asyncio.create_task(
            _fake_synthesize_and_send(processor, turn_id, 0, audio_base64=None)
        )
    ]

    events = [e async for e in processor.stream_events(turn_id)]
    tts_chunks = [e for e in events if e["type"] == "tts_chunk"]
    types = [e["type"] for e in events]

    assert len(tts_chunks) >= 1
    assert all(c["audio_base64"] is None for c in tts_chunks)
    assert all(c.get("motion_name") is not None for c in tts_chunks)
    assert all(c.get("blendshape_name") is not None for c in tts_chunks)
    assert types[-1] == "stream_end"


async def test_tts_failure_sends_null_audio_no_warning(processor: MessageProcessor):
    """TTS failure: tts_chunk(null audio), no warning event to client."""

    async def agent_stream() -> AsyncIterator[dict[str, Any]]:
        yield {"type": "stream_start"}
        yield {"type": "stream_end"}

    turn_id = await processor.start_turn("sess-fail", "hi", agent_stream=agent_stream())
    turn = processor.turns.get(turn_id)
    assert turn is not None
    turn.tts_tasks = [
        asyncio.create_task(
            _fake_synthesize_and_send(processor, turn_id, 0, audio_base64=None)
        )
    ]

    events = [e async for e in processor.stream_events(turn_id)]
    types = [e["type"] for e in events]

    assert "warning" not in types
    tts_chunks = [e for e in events if e["type"] == "tts_chunk"]
    assert all(c["audio_base64"] is None for c in tts_chunks)
    assert types[-1] == "stream_end"


async def test_barrier_timeout_no_deadlock_no_warning_event(
    processor: MessageProcessor,
):
    """barrier timeout: stream_end arrives normally, no warning event to client."""

    async def agent_stream() -> AsyncIterator[dict[str, Any]]:
        yield {"type": "stream_start"}
        yield {"type": "stream_end"}

    turn_id = await processor.start_turn(
        "sess-timeout", "hi", agent_stream=agent_stream()
    )
    turn = processor.turns.get(turn_id)
    assert turn is not None

    async def hanging_task() -> None:
        await asyncio.sleep(9999)

    hanging = asyncio.create_task(hanging_task())
    turn.tts_tasks = [hanging]

    mock_settings = MagicMock()
    mock_settings.websocket.tts_barrier_timeout_seconds = 0.05

    try:
        with (
            patch(
                "src.configs.settings.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "src.services.websocket_service.message_processor.processor.logger"
            ) as mock_logger,
        ):
            events = [e async for e in processor.stream_events(turn_id)]
            mock_logger.warning.assert_called()
    finally:
        hanging.cancel()
        try:
            await hanging
        except (asyncio.CancelledError, Exception):
            pass

    types = [e["type"] for e in events]
    assert "stream_end" in types
    assert "warning" not in types


async def test_stream_token_and_tts_chunk_coexist(processor: MessageProcessor):
    """Both stream_token and tts_chunk event types received, stream_end last."""

    async def agent_stream() -> AsyncIterator[dict[str, Any]]:
        yield {"type": "stream_start"}
        yield {"type": "stream_token", "chunk": "Hello! "}
        yield {"type": "stream_token", "chunk": "World."}
        yield {"type": "stream_end"}

    turn_id = await processor.start_turn(
        "sess-coexist", "hi", agent_stream=agent_stream()
    )
    turn = processor.turns.get(turn_id)
    assert turn is not None
    turn.tts_tasks = [
        asyncio.create_task(_fake_synthesize_and_send(processor, turn_id, 0))
    ]

    events = [e async for e in processor.stream_events(turn_id)]
    types = [e["type"] for e in events]

    assert "tts_chunk" in types
    assert "stream_end" in types
    assert types[-1] == "stream_end"


class TestTTSVoicesEndpoint:
    """Tests for GET /v1/tts/voices endpoint."""

    def test_get_tts_voices_returns_200_and_voices_list(self, client):
        """GET /v1/tts/voices: 200 + voices list."""
        with patch("src.api.routes.tts.get_tts_service") as mock_get_svc:
            mock_svc = MagicMock()
            mock_svc.list_voices.return_value = ["aria", "alice"]
            mock_get_svc.return_value = mock_svc

            response = client.get("/v1/tts/voices")

        assert response.status_code == 200
        data = response.json()
        assert "voices" in data
        assert len(data["voices"]) >= 1

    def test_get_tts_voices_service_unavailable(self, client):
        """GET /v1/tts/voices: 503 when service not initialized."""
        with patch("src.api.routes.tts.get_tts_service") as mock_get_svc:
            mock_get_svc.return_value = None
            response = client.get("/v1/tts/voices")

        assert response.status_code == 503
