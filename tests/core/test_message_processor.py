"""Test cases for the MessageProcessor Core Orchestrator."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.models.websocket import TtsChunkMessage
from src.services.websocket_service.message_processor import (
    ConversationTurn,
    MessageProcessor,
    TurnStatus,
)


class TestConversationTurn:
    """Test cases for ConversationTurn dataclass."""

    def test_conversation_turn_creation(self):
        """Turn stores identifiers and defaults correctly."""

        turn = ConversationTurn(
            turn_id="test-turn",
            user_message="Hello",
            session_id="conv-1",
        )

        assert turn.turn_id == "test-turn"
        assert turn.user_message == "Hello"
        assert turn.session_id == "conv-1"
        assert turn.status == TurnStatus.PENDING
        assert turn.response_content == ""
        assert turn.error_message is None
        assert isinstance(turn.metadata, dict)
        assert turn.event_queue is None
        assert not turn.tasks

    def test_conversation_turn_update_status(self):
        """Status updates change timestamps and optional error message."""

        turn = ConversationTurn(
            turn_id="test-turn",
            user_message="Hello",
            session_id="conv-1",
        )
        initial_time = turn.updated_at

        turn.update_status(TurnStatus.PROCESSING)
        assert turn.status == TurnStatus.PROCESSING
        assert turn.updated_at > initial_time

        turn.update_status(TurnStatus.FAILED, "Test error")
        assert turn.status == TurnStatus.FAILED
        assert turn.error_message == "Test error"


@pytest.fixture
def processor() -> MessageProcessor:
    """Create a MessageProcessor instance for each test."""

    return MessageProcessor(
        connection_id=uuid4(),
        user_id="test_user",
        tts_service=MagicMock(),
        mapper=MagicMock(),
    )


def test_processor_initialization(processor: MessageProcessor):
    """Initial state is empty and statistics reset."""

    assert processor.user_id == "test_user"
    assert isinstance(processor.connection_id, type(uuid4()))
    assert processor.turns == {}
    assert processor.active_turns == set()
    assert processor.total_turns == 0
    assert processor.total_interrupted == 0
    assert processor.get_event_queue() is None


@pytest.mark.asyncio
async def test_start_turn_initializes_queue_and_status(processor: MessageProcessor):
    """start_turn sets up bookkeeping and queue."""

    turn_id = await processor.start_turn("conv-123", "Hello", metadata={"k": "v"})

    turn = processor.turns[turn_id]
    assert turn.session_id == "conv-123"
    assert turn.metadata == {"k": "v"}
    assert turn.status == TurnStatus.PROCESSING
    assert turn.event_queue is not None
    assert turn_id in processor.active_turns
    assert processor.get_event_queue(turn_id) is turn.event_queue


@pytest.mark.asyncio
async def test_start_conversation_turn_wrapper(processor: MessageProcessor):
    """Wrapper generates a conversation id when not provided."""

    turn_id = await processor.start_conversation_turn("Hi there")
    turn = processor.turns[turn_id]
    assert turn.session_id
    assert turn.status == TurnStatus.PROCESSING


@pytest.mark.asyncio
async def test_agent_stream_events_forwarded(processor: MessageProcessor):
    """Events emitted by the agent stream are forwarded via stream_events."""

    async def agent_stream():
        yield {"type": "stream_start"}
        await asyncio.sleep(0)
        yield {"type": "stream_token", "chunk": "Hello"}
        yield {"type": "stream_end"}

    fake_chunk = TtsChunkMessage(
        sequence=0,
        text="Hello",
        audio_base64=None,
        emotion=None,
        keyframes=[{"duration": 0.3, "targets": {"neutral": 1.0}}],
    )

    with patch(
        "src.services.websocket_service.message_processor.event_handlers.synthesize_chunk",
        new=AsyncMock(return_value=fake_chunk),
    ):
        turn_id = await processor.start_turn(
            "conv-321",
            "User input",
            agent_stream=agent_stream(),
        )

        events = []
        async for event in processor.stream_events(turn_id):
            events.append(event)

    assert [e["type"] for e in events] == [
        "stream_start",
        "tts_chunk",
        "stream_end",
    ]
    assert events[1]["text"] == "Hello"
    assert processor.get_event_queue(turn_id) is None
    assert processor.turns[turn_id].status == TurnStatus.COMPLETED


@pytest.mark.asyncio
async def test_handle_interrupt_cancels_tasks(processor: MessageProcessor):
    """handle_interrupt cancels tracked tasks and clears queue."""

    turn_id = await processor.start_turn("conv", "data")
    queue = processor.get_event_queue(turn_id)
    assert queue is not None

    async def sleeper():
        await asyncio.sleep(5)

    task = asyncio.create_task(sleeper())
    await processor.add_task_to_turn(turn_id, task)
    await queue.put({"type": "stream_token"})

    cancelled_turn_id = await processor.handle_interrupt("User stopped")
    assert cancelled_turn_id == turn_id
    assert processor.turns[turn_id].status == TurnStatus.INTERRUPTED
    assert processor.turns[turn_id].error_message == "User stopped"
    assert task.cancelled() or task.done()
    assert processor.get_event_queue(turn_id) is None


@pytest.mark.asyncio
async def test_cleanup_idempotent(processor: MessageProcessor):
    """Calling cleanup multiple times is safe."""

    turn_id = await processor.start_turn("conv", "hello")
    await processor.handle_interrupt("drop")

    # Second invocation should no-op
    await processor.cleanup(turn_id)
    await processor.cleanup()
    assert processor.get_event_queue() is None


@pytest.mark.asyncio
async def test_interrupt_all_active_turns(processor: MessageProcessor):
    """interrupt_all_active_turns calls handle_interrupt once."""

    turn_id = await processor.start_turn("conv", "hello")
    count = await processor.interrupt_all_active_turns("shutdown")
    assert count == 1
    assert processor.turns[turn_id].status == TurnStatus.INTERRUPTED


@pytest.mark.asyncio
async def test_shutdown_triggers_interrupt(processor: MessageProcessor):
    """shutdown sets flag and interrupts the active turn."""

    turn_id = await processor.start_turn("conv", "hello")
    await processor.shutdown(cleanup_delay=0)

    assert processor._shutdown_event.is_set()
    assert turn_id not in processor.active_turns
    assert turn_id not in processor.turns
    assert processor.total_interrupted == 1


@pytest.mark.asyncio
async def test_cleanup_completed_turns(processor: MessageProcessor):
    """Old completed turns are removed when exceeding max age."""

    turn_id = await processor.start_turn("conv", "hello")
    await processor.complete_turn(turn_id)
    processor.turns[turn_id].updated_at = time.time() - 4000

    cleaned = await processor.cleanup_completed_turns(max_age_seconds=3600)
    assert cleaned == 1
    assert turn_id not in processor.turns


def test_get_stats(processor: MessageProcessor):
    """Statistics expose current counters."""

    stats = processor.get_stats()
    assert stats["user_id"] == "test_user"
    assert stats["total_turns"] == 0
    assert stats["total_tasks_tracked"] == 0
    assert stats["active_turns_count"] == 0
    assert stats["is_shutdown"] is False


def test_imports():
    """Module exports remain accessible."""

    from src.services.websocket_service.message_processor import (
        ConversationTurn as ImportedConversationTurn,
    )
    from src.services.websocket_service.message_processor import (
        MessageProcessor as ImportedMessageProcessor,
    )
    from src.services.websocket_service.message_processor import (
        TurnStatus as ImportedTurnStatus,
    )

    assert ImportedConversationTurn is not None
    assert ImportedMessageProcessor is not None
    assert ImportedTurnStatus is not None


def test_processor_stores_tts_service_and_mapper():
    from unittest.mock import MagicMock

    tts_service = MagicMock()
    mapper = MagicMock()
    proc = MessageProcessor(
        connection_id=uuid4(), user_id="u", tts_service=tts_service, mapper=mapper
    )
    assert proc.tts_service is tts_service
    assert proc.mapper is mapper


def test_is_connection_closing_false_by_default():
    from unittest.mock import MagicMock

    proc = MessageProcessor(
        connection_id=uuid4(), user_id="u", tts_service=MagicMock(), mapper=MagicMock()
    )
    assert proc.is_connection_closing() is False


@pytest.mark.asyncio
async def test_is_connection_closing_true_after_shutdown():
    from unittest.mock import MagicMock

    proc = MessageProcessor(
        connection_id=uuid4(), user_id="u", tts_service=MagicMock(), mapper=MagicMock()
    )
    await proc.shutdown(cleanup_delay=0)
    assert proc.is_connection_closing() is True


def test_conversation_turn_tts_fields_defaults():
    turn = ConversationTurn(turn_id="t1", user_message="hi", session_id="s1")
    assert turn.tts_enabled is True
    assert turn.reference_id is None
    assert turn.tts_tasks == []
    assert turn.tts_sequence == 0


if __name__ == "__main__":  # pragma: no cover
    import pytest as _pytest

    _pytest.main([__file__])
