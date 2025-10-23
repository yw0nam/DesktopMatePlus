"""Test cases for the MessageProcessor Core Orchestrator."""

import asyncio
import time
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from src.services.websocket_service.message_processor import (
    ConversationTurn,
    MessageProcessor,
    TurnStatus,
)


class TestConversationTurn:
    """Test cases for ConversationTurn dataclass."""

    def test_conversation_turn_creation(self):
        """Test creating a ConversationTurn."""
        turn = ConversationTurn(turn_id="test-turn", user_message="Hello")

        assert turn.turn_id == "test-turn"
        assert turn.user_message == "Hello"
        assert turn.status == TurnStatus.PENDING
        assert turn.response_content == ""
        assert turn.error_message is None
        assert len(turn.tasks) == 0
        assert isinstance(turn.metadata, dict)

    def test_conversation_turn_update_status(self):
        """Test updating turn status."""
        turn = ConversationTurn(turn_id="test-turn", user_message="Hello")
        initial_time = turn.updated_at

        # Update status
        turn.update_status(TurnStatus.PROCESSING)
        assert turn.status == TurnStatus.PROCESSING
        assert turn.updated_at > initial_time

        # Update with error
        turn.update_status(TurnStatus.FAILED, "Test error")
        assert turn.status == TurnStatus.FAILED
        assert turn.error_message == "Test error"


class TestMessageProcessor:
    """Test cases for MessageProcessor class."""

    @pytest.fixture
    def processor(self):
        """Create a MessageProcessor instance for testing."""
        connection_id = uuid4()
        user_id = "test_user"
        return MessageProcessor(connection_id, user_id)

    def test_processor_initialization(self, processor):
        """Test MessageProcessor initialization."""
        assert processor.user_id == "test_user"
        assert isinstance(processor.connection_id, type(uuid4()))
        assert len(processor.turns) == 0
        assert len(processor.active_turns) == 0
        assert processor.total_turns == 0
        assert processor.total_interrupted == 0

    @pytest.mark.asyncio
    async def test_start_conversation_turn(self, processor):
        """Test starting a new conversation turn."""
        metadata = {"test": "data"}
        turn_id = await processor.start_conversation_turn("Hello world", metadata)

        assert turn_id is not None
        assert turn_id in processor.turns
        assert turn_id in processor.active_turns
        assert processor.total_turns == 1

        turn = processor.turns[turn_id]
        assert turn.user_message == "Hello world"
        assert turn.metadata == metadata
        assert turn.status == TurnStatus.PENDING

    @pytest.mark.asyncio
    async def test_update_turn_status(self, processor):
        """Test updating turn status."""
        turn_id = await processor.start_conversation_turn("Test message")

        # Update to processing
        result = await processor.update_turn_status(turn_id, TurnStatus.PROCESSING)
        assert result is True
        assert processor.turns[turn_id].status == TurnStatus.PROCESSING
        assert turn_id in processor.active_turns

        # Update to completed (should remove from active)
        result = await processor.update_turn_status(turn_id, TurnStatus.COMPLETED)
        assert result is True
        assert processor.turns[turn_id].status == TurnStatus.COMPLETED
        assert turn_id not in processor.active_turns

        # Test updating non-existent turn
        result = await processor.update_turn_status("invalid-id", TurnStatus.FAILED)
        assert result is False

    @pytest.mark.asyncio
    async def test_add_task_to_turn(self, processor):
        """Test adding asyncio tasks to a turn."""
        turn_id = await processor.start_conversation_turn("Test message")

        # Create a mock task
        task = AsyncMock(spec=asyncio.Task)

        # Add task to turn
        result = await processor.add_task_to_turn(turn_id, task)
        assert result is True
        assert task in processor.turns[turn_id].tasks

        # Test adding task to non-existent turn
        result = await processor.add_task_to_turn("invalid-id", task)
        assert result is False

    @pytest.mark.asyncio
    async def test_complete_turn(self, processor):
        """Test completing a conversation turn."""
        turn_id = await processor.start_conversation_turn("Test message")

        response_content = "Test response"
        metadata = {"completion": "test"}

        result = await processor.complete_turn(turn_id, response_content, metadata)
        assert result is True

        turn = processor.turns[turn_id]
        assert turn.status == TurnStatus.COMPLETED
        assert turn.response_content == response_content
        assert turn.metadata["completion"] == "test"
        assert turn_id not in processor.active_turns

    @pytest.mark.asyncio
    async def test_fail_turn(self, processor):
        """Test failing a conversation turn."""
        turn_id = await processor.start_conversation_turn("Test message")

        error_message = "Test error"
        metadata = {"error": "test"}

        result = await processor.fail_turn(turn_id, error_message, metadata)
        assert result is True

        turn = processor.turns[turn_id]
        assert turn.status == TurnStatus.FAILED
        assert turn.error_message == error_message
        assert turn.metadata["error"] == "test"
        assert turn_id not in processor.active_turns

    @pytest.mark.asyncio
    async def test_interrupt_turn(self, processor):
        """Test interrupting a conversation turn."""
        turn_id = await processor.start_conversation_turn("Test message")

        # Add some mock tasks
        task1 = AsyncMock(spec=asyncio.Task)
        task1.done.return_value = False
        task2 = AsyncMock(spec=asyncio.Task)
        task2.done.return_value = True  # Already done

        await processor.add_task_to_turn(turn_id, task1)
        await processor.add_task_to_turn(turn_id, task2)

        # Interrupt turn
        result = await processor.interrupt_turn(turn_id, "Test interruption")
        assert result is True

        # Check that only the undone task was cancelled
        task1.cancel.assert_called_once()
        task2.cancel.assert_not_called()

        turn = processor.turns[turn_id]
        assert turn.status == TurnStatus.INTERRUPTED
        assert turn.error_message == "Test interruption"
        assert turn_id not in processor.active_turns
        assert processor.total_interrupted == 1

    @pytest.mark.asyncio
    async def test_interrupt_all_active_turns(self, processor):
        """Test interrupting all active turns."""
        # Start multiple turns
        turn_id1 = await processor.start_conversation_turn("Message 1")
        turn_id2 = await processor.start_conversation_turn("Message 2")
        turn_id3 = await processor.start_conversation_turn("Message 3")

        # Complete one turn (should not be interrupted)
        await processor.complete_turn(turn_id3, "Response 3")

        # Interrupt all active turns
        interrupted_count = await processor.interrupt_all_active_turns("Shutdown")
        assert interrupted_count == 2
        assert processor.total_interrupted == 2

        # Check status of turns
        assert processor.turns[turn_id1].status == TurnStatus.INTERRUPTED
        assert processor.turns[turn_id2].status == TurnStatus.INTERRUPTED
        assert processor.turns[turn_id3].status == TurnStatus.COMPLETED  # Unchanged

        # No turns should be active
        assert len(processor.active_turns) == 0

    @pytest.mark.asyncio
    async def test_get_turn(self, processor):
        """Test getting a specific turn."""
        turn_id = await processor.start_conversation_turn("Test message")

        # Get existing turn
        turn = await processor.get_turn(turn_id)
        assert turn is not None
        assert turn.turn_id == turn_id
        assert turn.user_message == "Test message"

        # Get non-existent turn
        turn = await processor.get_turn("invalid-id")
        assert turn is None

    @pytest.mark.asyncio
    async def test_get_active_turns(self, processor):
        """Test getting all active turns."""
        # Start multiple turns
        turn_id1 = await processor.start_conversation_turn("Message 1")
        turn_id2 = await processor.start_conversation_turn("Message 2")
        turn_id3 = await processor.start_conversation_turn("Message 3")

        # Complete one turn
        await processor.complete_turn(turn_id2, "Response 2")

        # Get active turns
        active_turns = await processor.get_active_turns()
        assert len(active_turns) == 2

        active_turn_ids = [turn.turn_id for turn in active_turns]
        assert turn_id1 in active_turn_ids
        assert turn_id3 in active_turn_ids
        assert turn_id2 not in active_turn_ids

    @pytest.mark.asyncio
    async def test_cleanup_completed_turns(self, processor):
        """Test cleaning up old completed turns."""
        # Start and complete multiple turns
        turn_id1 = await processor.start_conversation_turn("Message 1")
        turn_id2 = await processor.start_conversation_turn("Message 2")
        turn_id3 = await processor.start_conversation_turn("Message 3")

        await processor.complete_turn(turn_id1, "Response 1")
        await processor.fail_turn(turn_id2, "Error 2")
        # Leave turn_id3 active

        # Mock time to make turns appear old
        with patch(
            "time.time", return_value=time.time() + 3700
        ):  # 1 hour + 100 seconds
            cleaned_count = await processor.cleanup_completed_turns(
                3600
            )  # 1 hour max age

        assert cleaned_count == 2  # Two completed/failed turns cleaned
        assert turn_id1 not in processor.turns
        assert turn_id2 not in processor.turns
        assert turn_id3 in processor.turns  # Still active, so not cleaned

    def test_get_stats(self, processor):
        """Test getting processor statistics."""
        stats = processor.get_stats()

        assert "connection_id" in stats
        assert "user_id" in stats
        assert stats["user_id"] == "test_user"
        assert "created_at" in stats
        assert "total_turns" in stats
        assert "total_interrupted" in stats
        assert "active_turns_count" in stats
        assert "total_turns_stored" in stats
        assert "total_tasks_tracked" in stats
        assert "is_shutdown" in stats

    @pytest.mark.asyncio
    async def test_shutdown(self, processor):
        """Test shutting down the processor."""
        # Start multiple turns
        turn_id1 = await processor.start_conversation_turn("Message 1")
        turn_id2 = await processor.start_conversation_turn("Message 2")

        # Add mock tasks
        task1 = AsyncMock(spec=asyncio.Task)
        task1.done.return_value = False
        await processor.add_task_to_turn(turn_id1, task1)

        # Shutdown with delay to prevent immediate cleanup
        await processor.shutdown(
            cleanup_delay=10
        )  # Use delay to prevent immediate cleanup

        # Check that shutdown event is set
        assert processor._shutdown_event.is_set()

        # Check that all active turns were interrupted
        assert len(processor.active_turns) == 0
        assert processor.turns[turn_id1].status == TurnStatus.INTERRUPTED
        assert processor.turns[turn_id2].status == TurnStatus.INTERRUPTED

        # Check that task was cancelled
        task1.cancel.assert_called_once()

        # Cancel the cleanup task to avoid waiting
        if processor._cleanup_task:
            processor._cleanup_task.cancel()

    @pytest.mark.asyncio
    async def test_shutdown_with_delay(self, processor):
        """Test shutting down with cleanup delay."""
        # Start a turn and complete it
        turn_id = await processor.start_conversation_turn("Message")
        await processor.complete_turn(turn_id, "Response")

        # Shutdown with delay
        await processor.shutdown(cleanup_delay=0.1)

        # Should have created a cleanup task
        assert processor._cleanup_task is not None

        # Wait for cleanup to complete
        await asyncio.sleep(0.15)

        # Turn should be cleaned up
        assert len(processor.turns) == 0


# Import test to ensure the module structure is correct
def test_imports():
    """Test that all imports work correctly."""
    from src.services.websocket_service.message_processor import (
        ConversationTurn,
        MessageProcessor,
        TurnStatus,
    )

    assert MessageProcessor is not None
    assert TurnStatus is not None
    assert ConversationTurn is not None


if __name__ == "__main__":
    pytest.main([__file__])
