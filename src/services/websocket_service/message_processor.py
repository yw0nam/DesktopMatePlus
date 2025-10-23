"""MessageProcessor Core Orchestrator.

This module implements the MessageProcessor class that supervises a single
conversational turn, tracks asyncio.Tasks, and provides cleanup and
interruption logic.
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import UUID, uuid4

from loguru import logger


class TurnStatus(Enum):
    """Status of a conversation turn."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    FAILED = "failed"


@dataclass
class ConversationTurn:
    """Represents a single conversation turn."""

    turn_id: str
    user_message: str
    status: TurnStatus = TurnStatus.PENDING
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tasks: Set[asyncio.Task] = field(default_factory=set)
    response_content: str = ""
    error_message: Optional[str] = None

    def update_status(self, status: TurnStatus, error_message: Optional[str] = None):
        """Update turn status and timestamp."""
        self.status = status
        self.updated_at = time.time()
        if error_message:
            self.error_message = error_message
        logger.debug(f"Turn {self.turn_id} status updated to {status.value}")


class MessageProcessor:
    """Core orchestrator for managing conversation turns and async tasks."""

    def __init__(self, connection_id: UUID, user_id: str):
        """Initialize MessageProcessor.

        Args:
            connection_id: WebSocket connection identifier
            user_id: User identifier for this processor
        """
        self.connection_id = connection_id
        self.user_id = user_id
        self.turns: Dict[str, ConversationTurn] = {}
        self.active_turns: Set[str] = set()
        self.created_at = time.time()
        self.total_turns = 0
        self.total_interrupted = 0
        self._shutdown_event = asyncio.Event()
        self._cleanup_task: Optional[asyncio.Task] = None

        logger.info(
            f"MessageProcessor initialized for connection {connection_id}, user {user_id}"
        )

    async def start_conversation_turn(
        self, user_message: str, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Start a new conversation turn.

        Args:
            user_message: User's input message
            metadata: Optional metadata for the turn

        Returns:
            str: Unique turn identifier
        """
        turn_id = str(uuid4())
        turn = ConversationTurn(
            turn_id=turn_id, user_message=user_message, metadata=metadata or {}
        )

        self.turns[turn_id] = turn
        self.active_turns.add(turn_id)
        self.total_turns += 1

        logger.info(
            f"Started conversation turn {turn_id} for connection {self.connection_id}"
        )
        return turn_id

    async def update_turn_status(
        self, turn_id: str, status: TurnStatus, error_message: Optional[str] = None
    ) -> bool:
        """Update status of a conversation turn.

        Args:
            turn_id: Turn identifier
            status: New status
            error_message: Optional error message

        Returns:
            bool: True if turn was found and updated, False otherwise
        """
        turn = self.turns.get(turn_id)
        if not turn:
            logger.warning(f"Turn {turn_id} not found for status update")
            return False

        turn.update_status(status, error_message)

        # Remove from active turns if terminal status
        if status in [TurnStatus.COMPLETED, TurnStatus.INTERRUPTED, TurnStatus.FAILED]:
            self.active_turns.discard(turn_id)

        return True

    async def add_task_to_turn(self, turn_id: str, task: asyncio.Task) -> bool:
        """Add an asyncio task to a conversation turn for tracking.

        Args:
            turn_id: Turn identifier
            task: AsyncIO task to track

        Returns:
            bool: True if task was added, False if turn not found
        """
        turn = self.turns.get(turn_id)
        if not turn:
            logger.warning(f"Turn {turn_id} not found for task addition")
            return False

        turn.tasks.add(task)
        logger.debug(f"Added task to turn {turn_id}, total tasks: {len(turn.tasks)}")
        return True

    async def interrupt_turn(
        self, turn_id: str, reason: str = "Manual interruption"
    ) -> bool:
        """Interrupt a specific conversation turn and cancel all its tasks.

        Args:
            turn_id: Turn identifier to interrupt
            reason: Reason for interruption

        Returns:
            bool: True if turn was interrupted, False if not found or already finished
        """
        turn = self.turns.get(turn_id)
        if not turn or turn.status in [
            TurnStatus.COMPLETED,
            TurnStatus.INTERRUPTED,
            TurnStatus.FAILED,
        ]:
            logger.debug(f"Turn {turn_id} not found or already finished")
            return False

        # Cancel all tasks associated with this turn
        cancelled_count = 0
        for task in turn.tasks.copy():
            if not task.done():
                task.cancel()
                cancelled_count += 1

        # Update turn status
        await self.update_turn_status(turn_id, TurnStatus.INTERRUPTED, reason)
        self.total_interrupted += 1

        logger.info(
            f"Interrupted turn {turn_id}, cancelled {cancelled_count} tasks. Reason: {reason}"
        )
        return True

    async def interrupt_all_active_turns(
        self, reason: str = "Shutdown requested"
    ) -> int:
        """Interrupt all active conversation turns.

        Args:
            reason: Reason for interruption

        Returns:
            int: Number of turns that were interrupted
        """
        active_turn_ids = list(self.active_turns)
        interrupted_count = 0

        for turn_id in active_turn_ids:
            if await self.interrupt_turn(turn_id, reason):
                interrupted_count += 1

        logger.info(f"Interrupted {interrupted_count} active turns. Reason: {reason}")
        return interrupted_count

    async def complete_turn(
        self,
        turn_id: str,
        response_content: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Mark a conversation turn as completed.

        Args:
            turn_id: Turn identifier
            response_content: Generated response content
            metadata: Optional completion metadata

        Returns:
            bool: True if turn was completed, False if not found
        """
        turn = self.turns.get(turn_id)
        if not turn:
            logger.warning(f"Turn {turn_id} not found for completion")
            return False

        turn.response_content = response_content
        if metadata:
            turn.metadata.update(metadata)

        await self.update_turn_status(turn_id, TurnStatus.COMPLETED)
        logger.info(f"Completed turn {turn_id}")
        return True

    async def fail_turn(
        self,
        turn_id: str,
        error_message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Mark a conversation turn as failed.

        Args:
            turn_id: Turn identifier
            error_message: Error description
            metadata: Optional failure metadata

        Returns:
            bool: True if turn was marked as failed, False if not found
        """
        turn = self.turns.get(turn_id)
        if not turn:
            logger.warning(f"Turn {turn_id} not found for failure marking")
            return False

        if metadata:
            turn.metadata.update(metadata)

        await self.update_turn_status(turn_id, TurnStatus.FAILED, error_message)
        logger.error(f"Failed turn {turn_id}: {error_message}")
        return True

    async def get_turn(self, turn_id: str) -> Optional[ConversationTurn]:
        """Get a specific conversation turn.

        Args:
            turn_id: Turn identifier

        Returns:
            ConversationTurn or None if not found
        """
        return self.turns.get(turn_id)

    async def get_active_turns(self) -> List[ConversationTurn]:
        """Get all currently active conversation turns.

        Returns:
            List of active ConversationTurn objects
        """
        return [
            self.turns[turn_id]
            for turn_id in self.active_turns
            if turn_id in self.turns
        ]

    async def cleanup_completed_turns(self, max_age_seconds: float = 3600) -> int:
        """Clean up old completed turns to prevent memory leaks.

        Args:
            max_age_seconds: Maximum age for keeping completed turns

        Returns:
            int: Number of turns cleaned up
        """
        current_time = time.time()
        turns_to_remove = []

        for turn_id, turn in self.turns.items():
            if (
                turn.status
                in [TurnStatus.COMPLETED, TurnStatus.FAILED, TurnStatus.INTERRUPTED]
                and current_time - turn.updated_at > max_age_seconds
            ):
                turns_to_remove.append(turn_id)

        for turn_id in turns_to_remove:
            del self.turns[turn_id]
            self.active_turns.discard(turn_id)

        if turns_to_remove:
            logger.info(f"Cleaned up {len(turns_to_remove)} old turns")

        return len(turns_to_remove)

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about this MessageProcessor.

        Returns:
            Dictionary with processor statistics
        """
        active_turns = len(self.active_turns)
        total_tasks = sum(len(turn.tasks) for turn in self.turns.values())

        return {
            "connection_id": str(self.connection_id),
            "user_id": self.user_id,
            "created_at": self.created_at,
            "total_turns": self.total_turns,
            "total_interrupted": self.total_interrupted,
            "active_turns_count": active_turns,
            "total_turns_stored": len(self.turns),
            "total_tasks_tracked": total_tasks,
            "is_shutdown": self._shutdown_event.is_set(),
        }

    async def shutdown(self, cleanup_delay: float = 30.0):
        """Shutdown the MessageProcessor and cleanup resources.

        Args:
            cleanup_delay: Seconds to wait before cleaning up old turns
        """
        logger.info(
            f"Shutting down MessageProcessor for connection {self.connection_id}"
        )

        # Set shutdown event
        self._shutdown_event.set()

        # Interrupt all active turns
        await self.interrupt_all_active_turns("MessageProcessor shutdown")

        # Schedule cleanup task
        if cleanup_delay > 0:
            self._cleanup_task = asyncio.create_task(
                self._delayed_cleanup(cleanup_delay)
            )
        else:
            await self.cleanup_completed_turns(0)  # Immediate cleanup

    async def _delayed_cleanup(self, delay: float):
        """Delayed cleanup of resources.

        Args:
            delay: Seconds to wait before cleanup
        """
        try:
            await asyncio.sleep(delay)
            await self.cleanup_completed_turns(0)
            logger.info(
                f"Completed delayed cleanup for connection {self.connection_id}"
            )
        except asyncio.CancelledError:
            logger.debug(f"Cleanup task cancelled for connection {self.connection_id}")
        except Exception as e:
            logger.error(
                f"Error during delayed cleanup for connection {self.connection_id}: {e}"
            )

    def __del__(self):
        """Destructor to ensure cleanup."""
        if (
            hasattr(self, "_cleanup_task")
            and self._cleanup_task
            and not self._cleanup_task.done()
        ):
            self._cleanup_task.cancel()
