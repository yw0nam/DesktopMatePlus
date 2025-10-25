"""MessageProcessor Core Orchestrator.

This module implements the MessageProcessor class that supervises a single
conversational turn, tracks asyncio.Tasks, coordinates AgentService streaming
events, and guarantees deterministic cleanup.
"""

from __future__ import annotations

import asyncio
import time
from contextlib import suppress
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, AsyncIterator, Dict, List, Optional, Set
from uuid import UUID, uuid4

from loguru import logger

from .text_processors import TextChunkProcessor, TTSTextProcessor

_TOKEN_QUEUE_SENTINEL = object()
_INTERRUPT_WAIT_TIMEOUT = 1.0


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
    conversation_id: str
    status: TurnStatus = TurnStatus.PENDING
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tasks: Set[asyncio.Task] = field(default_factory=set)
    response_content: str = ""
    error_message: Optional[str] = None
    event_queue: Optional[asyncio.Queue] = None
    token_queue: Optional[asyncio.Queue] = None
    token_consumer_task: Optional[asyncio.Task] = None
    token_stream_closed: bool = False
    chunk_processor: Optional[TextChunkProcessor] = None
    tts_processor: Optional[TTSTextProcessor] = None

    def update_status(self, status: TurnStatus, error_message: Optional[str] = None):
        """Update turn status and timestamp."""
        self.status = status
        self.updated_at = time.time()
        if error_message:
            self.error_message = error_message
        logger.debug(f"Turn {self.turn_id} status updated to {status.value}")


class MessageProcessor:
    """Core orchestrator for managing conversation turns and async tasks."""

    def __init__(
        self,
        connection_id: UUID,
        user_id: str,
        *,
        queue_maxsize: int = 100,
    ):
        """Initialize MessageProcessor.

        Args:
            connection_id: WebSocket connection identifier.
            user_id: User identifier for this processor.
            queue_maxsize: Maximum size for the per-turn event queue.
        """
        self.connection_id = connection_id
        self.user_id = user_id
        self.queue_maxsize = max(1, queue_maxsize)
        self.turns: Dict[str, ConversationTurn] = {}
        self.active_turns: Set[str] = set()
        self.active_tasks: Set[asyncio.Task] = set()
        self.created_at = time.time()
        self.total_turns = 0
        self.total_interrupted = 0
        self._shutdown_event = asyncio.Event()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._turn_lock = asyncio.Lock()
        self._cleanup_lock = asyncio.Lock()
        self._current_turn_id: Optional[str] = None
        self._cleaned_turns: Set[str] = set()

        logger.info(
            "MessageProcessor initialized for connection %s, user %s",
            connection_id,
            user_id,
        )

    async def start_turn(
        self,
        conversation_id: str,
        user_input: str,
        *,
        agent_stream: Optional[AsyncIterator[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Start a new conversation turn.

        Args:
            conversation_id: Logical conversation identifier.
            user_input: Raw user input for the turn.
            agent_stream: Optional async iterator yielding AgentService events.
            metadata: Optional metadata for the turn.

        Returns:
            str: Newly generated turn identifier.
        """

        async with self._turn_lock:
            if self._current_turn_id is not None:
                raise RuntimeError("Another turn is already active")

            turn_id = str(uuid4())
            turn = ConversationTurn(
                turn_id=turn_id,
                user_message=user_input,
                conversation_id=conversation_id,
                metadata=metadata or {},
            )

            turn.event_queue = asyncio.Queue(maxsize=self.queue_maxsize)
            turn.token_queue = asyncio.Queue(maxsize=self.queue_maxsize)
            turn.token_stream_closed = False
            turn.chunk_processor = TextChunkProcessor()
            turn.tts_processor = TTSTextProcessor()
            self.turns[turn_id] = turn
            self.active_turns.add(turn_id)
            self.total_turns += 1
            self._current_turn_id = turn_id
            await self.update_turn_status(turn_id, TurnStatus.PROCESSING)
            logger.info(
                "Started conversation turn %s for connection %s (conversation %s)",
                turn_id,
                self.connection_id,
                conversation_id,
            )

        self._ensure_token_consumer(turn_id)

        if agent_stream is not None:
            producer_task = asyncio.create_task(
                self._produce_agent_events(turn_id, agent_stream),
                name=f"message-processor-producer-{turn_id}",
            )
            self._track_task(turn_id, producer_task)

        return turn_id

    async def start_conversation_turn(
        self, user_message: str, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Backward compatible wrapper that generates a conversation id."""

        conversation_id = metadata.get("conversation_id") if metadata else None
        conversation_id = conversation_id or str(uuid4())
        return await self.start_turn(
            conversation_id=conversation_id,
            user_input=user_message,
            metadata=metadata,
        )

    async def update_turn_status(
        self, turn_id: str, status: TurnStatus, error_message: Optional[str] = None
    ) -> bool:
        """Update status of a conversation turn."""

        turn = self.turns.get(turn_id)
        if not turn:
            logger.warning("Turn %s not found for status update", turn_id)
            return False

        turn.update_status(status, error_message)

        if status in {TurnStatus.COMPLETED, TurnStatus.INTERRUPTED, TurnStatus.FAILED}:
            self.active_turns.discard(turn_id)

        return True

    async def add_task_to_turn(self, turn_id: str, task: asyncio.Task) -> bool:
        """Add an asyncio task to a conversation turn for tracking."""

        turn = self.turns.get(turn_id)
        if not turn:
            logger.warning("Turn %s not found for task addition", turn_id)
            return False

        turn.tasks.add(task)
        self.active_tasks.add(task)
        task.add_done_callback(self._build_task_cleanup(turn_id))

        logger.debug(
            "Added task to turn %s, total tracked tasks: %d",
            turn_id,
            len(turn.tasks),
        )
        return True

    async def interrupt_turn(
        self, turn_id: str, reason: str = "Manual interruption"
    ) -> bool:
        """Interrupt a specific conversation turn."""

        turn = self.turns.get(turn_id)
        if not turn or turn.status in {
            TurnStatus.COMPLETED,
            TurnStatus.INTERRUPTED,
            TurnStatus.FAILED,
        }:
            logger.debug("Turn %s not found or already finished", turn_id)
            return False

        interrupted_id = await self.handle_interrupt(reason=reason, turn_id=turn_id)
        if not interrupted_id:
            logger.debug(
                "Failed to interrupt turn %s for connection %s",
                turn_id,
                self.connection_id,
            )
            return False

        logger.info(
            "Interrupted turn %s for connection %s. Reason: %s",
            turn_id,
            self.connection_id,
            reason,
        )
        return True

    async def interrupt_all_active_turns(
        self, reason: str = "Shutdown requested"
    ) -> int:
        """Interrupt all active conversation turns."""

        active_turn_ids = list(self.active_turns)
        interrupted_count = 0

        for turn_id in active_turn_ids:
            if await self.interrupt_turn(turn_id, reason):
                interrupted_count += 1

        logger.info(
            "Interrupted %d active turns for connection %s. Reason: %s",
            interrupted_count,
            self.connection_id,
            reason,
        )
        return interrupted_count

    async def complete_turn(
        self,
        turn_id: str,
        response_content: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Mark a conversation turn as completed."""

        turn = self.turns.get(turn_id)
        if not turn:
            logger.warning("Turn %s not found for completion", turn_id)
            return False

        turn.response_content = response_content
        if metadata:
            turn.metadata.update(metadata)

        await self.update_turn_status(turn_id, TurnStatus.COMPLETED)
        logger.info("Completed turn %s for connection %s", turn_id, self.connection_id)
        return True

    async def fail_turn(
        self,
        turn_id: str,
        error_message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Mark a conversation turn as failed."""

        turn = self.turns.get(turn_id)
        if not turn:
            logger.warning("Turn %s not found for failure marking", turn_id)
            return False

        if metadata:
            turn.metadata.update(metadata)

        await self.update_turn_status(turn_id, TurnStatus.FAILED, error_message)
        logger.error("Failed turn %s: %s", turn_id, error_message)
        return True

    async def handle_interrupt(
        self,
        reason: str = "Interrupt requested",
        turn_id: Optional[str] = None,
    ) -> Optional[str]:
        """Handle an interrupt for the specified (or current) turn."""

        target_turn_id = turn_id or self._current_turn_id
        if not target_turn_id:
            logger.debug(
                "handle_interrupt called with no active turn for connection %s",
                self.connection_id,
            )
            return None

        turn = self.turns.get(target_turn_id)
        if not turn or turn.status in {
            TurnStatus.COMPLETED,
            TurnStatus.INTERRUPTED,
            TurnStatus.FAILED,
        }:
            logger.debug(
                "handle_interrupt skipping turn %s (status=%s)",
                target_turn_id,
                turn.status if turn else "missing",
            )
            return None

        previous_status = turn.status
        await self.update_turn_status(target_turn_id, TurnStatus.INTERRUPTED, reason)
        if previous_status != TurnStatus.INTERRUPTED:
            self.total_interrupted += 1

        await self._signal_token_stream_closed(target_turn_id)
        await self._wait_for_token_queue(target_turn_id)
        await self._cancel_turn_tasks(target_turn_id)

        queue = self.get_event_queue(target_turn_id)
        if queue:
            drained = self._drain_event_queue(target_turn_id)
            if drained:
                logger.debug(
                    "Drained %d queued events before interrupting turn %s",
                    drained,
                    target_turn_id,
                )

            interrupt_event = self._normalize_event(
                target_turn_id,
                {
                    "type": "stream_end",
                    "reason": reason,
                    "status": TurnStatus.INTERRUPTED.value,
                },
            )

            try:
                await queue.put(interrupt_event)
            except asyncio.QueueFull:
                await queue.put(interrupt_event)

            try:
                await asyncio.wait_for(queue.join(), timeout=_INTERRUPT_WAIT_TIMEOUT)
            except asyncio.TimeoutError:
                logger.debug(
                    "Timed out waiting for interrupt event delivery for turn %s",
                    target_turn_id,
                )

        await self.cleanup(target_turn_id)
        return target_turn_id

    async def cleanup(self, turn_id: Optional[str] = None):
        """Cleanup resources associated with a conversation turn."""

        if turn_id is None:
            turn_id = self._current_turn_id

        if not turn_id:
            return

        async with self._cleanup_lock:
            if turn_id in self._cleaned_turns:
                return

            turn = self.turns.get(turn_id)
            if not turn:
                self._cleaned_turns.add(turn_id)
                return

            if turn.token_queue:
                await self._signal_token_stream_closed(turn_id)

            current_task = asyncio.current_task()
            tasks_to_cancel: List[asyncio.Task] = []
            token_consumer_task = turn.token_consumer_task

            if token_consumer_task and token_consumer_task.done():
                token_consumer_task = None

            for task in list(turn.tasks):
                if task is current_task:
                    continue
                if token_consumer_task and task is token_consumer_task:
                    continue
                if not task.done():
                    task.cancel()
                tasks_to_cancel.append(task)

            if token_consumer_task:
                await asyncio.gather(token_consumer_task, return_exceptions=True)

            if tasks_to_cancel:
                await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

            for task in tasks_to_cancel:
                self.active_tasks.discard(task)
                turn.tasks.discard(task)

            if token_consumer_task:
                self.active_tasks.discard(token_consumer_task)
                turn.tasks.discard(token_consumer_task)
                turn.token_consumer_task = None

            if turn.event_queue:
                while not turn.event_queue.empty():
                    try:
                        turn.event_queue.get_nowait()
                    except asyncio.QueueEmpty:  # pragma: no cover - safety guard
                        break
                turn.event_queue = None

            if turn.token_queue:
                while not turn.token_queue.empty():
                    try:
                        turn.token_queue.get_nowait()
                    except asyncio.QueueEmpty:  # pragma: no cover - safety guard
                        break
                turn.token_queue = None
                turn.token_stream_closed = True
            turn.chunk_processor = None
            turn.tts_processor = None

            self.active_turns.discard(turn_id)
            if self._current_turn_id == turn_id:
                self._current_turn_id = None

            self._cleaned_turns.add(turn_id)
            logger.info(
                "Cleaned up turn %s for connection %s",
                turn_id,
                self.connection_id,
            )

    async def attach_agent_stream(
        self, turn_id: str, agent_stream: AsyncIterator[Dict[str, Any]]
    ) -> None:
        """Attach an AgentService stream to an existing turn."""

        turn = self.turns.get(turn_id)
        if not turn:
            raise ValueError(f"Unknown turn: {turn_id}")

        self._ensure_token_consumer(turn_id)

        producer_task = asyncio.create_task(
            self._produce_agent_events(turn_id, agent_stream),
            name=f"message-processor-producer-{turn_id}",
        )
        self._track_task(turn_id, producer_task)

    async def get_turn(self, turn_id: str) -> Optional[ConversationTurn]:
        """Get a specific conversation turn."""

        return self.turns.get(turn_id)

    async def get_active_turns(self) -> List[ConversationTurn]:
        """Get all currently active conversation turns."""

        return [
            self.turns[turn_id]
            for turn_id in self.active_turns
            if turn_id in self.turns
        ]

    def get_event_queue(self, turn_id: Optional[str] = None) -> Optional[asyncio.Queue]:
        """Return the event queue for the requested turn (defaults to current)."""

        if turn_id is None:
            turn_id = self._current_turn_id

        if not turn_id:
            return None

        turn = self.turns.get(turn_id)
        if not turn:
            return None

        return turn.event_queue

    async def cleanup_completed_turns(self, max_age_seconds: float = 3600) -> int:
        """Clean up old completed turns to prevent memory leaks."""

        current_time = time.time()
        turns_to_remove = []

        for turn_id, turn in list(self.turns.items()):
            if (
                turn.status
                in {TurnStatus.COMPLETED, TurnStatus.FAILED, TurnStatus.INTERRUPTED}
                and current_time - turn.updated_at > max_age_seconds
            ):
                turns_to_remove.append(turn_id)

        for turn_id in turns_to_remove:
            self.turns.pop(turn_id, None)
            self.active_turns.discard(turn_id)
            self._cleaned_turns.discard(turn_id)

        if turns_to_remove:
            logger.info("Cleaned up %d old turns", len(turns_to_remove))

        return len(turns_to_remove)

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about this MessageProcessor."""

        active_turns = len(self.active_turns)
        total_tasks = len(self.active_tasks)

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
        """Shutdown the MessageProcessor and cleanup resources."""

        logger.info(
            "Shutting down MessageProcessor for connection %s",
            self.connection_id,
        )

        self._shutdown_event.set()

        await self.interrupt_all_active_turns("MessageProcessor shutdown")

        if cleanup_delay > 0:
            self._cleanup_task = asyncio.create_task(
                self._delayed_cleanup(cleanup_delay)
            )
        else:
            await self.cleanup_completed_turns(0)

    async def _produce_agent_events(
        self, turn_id: str, agent_stream: AsyncIterator[Dict[str, Any]]
    ) -> None:
        """Consume AgentService events and forward them to the queue."""

        try:
            async for raw_event in agent_stream:
                event = self._normalize_event(turn_id, raw_event)
                event_type = event.get("type")

                if event_type == "stream_token":
                    await self._put_token_event(turn_id, event)
                    continue

                if event_type == "stream_start":
                    await self._put_event(turn_id, event)
                    await self.update_turn_status(turn_id, TurnStatus.PROCESSING)
                    continue

                if event_type == "stream_end":
                    await self._signal_token_stream_closed(turn_id)
                    await self._wait_for_token_queue(turn_id)
                    await self._put_event(turn_id, event)
                    await self.complete_turn(turn_id)
                    continue

                if event_type == "error":
                    await self._signal_token_stream_closed(turn_id)
                    await self._wait_for_token_queue(turn_id)
                    await self._put_event(turn_id, event)
                    await self.fail_turn(turn_id, event.get("error", "Unknown error"))
                    continue

                logger.debug(
                    "Dropping agent event %s from client stream for turn %s",
                    event_type,
                    turn_id,
                )

        except asyncio.CancelledError:
            logger.debug("Producer cancelled for turn %s", turn_id)
            raise
        except Exception as exc:  # pragma: no cover - defensive  # noqa: BLE001
            await self.fail_turn(turn_id, str(exc))
            await self._signal_token_stream_closed(turn_id)
            await self._wait_for_token_queue(turn_id)
            await self._put_event(
                turn_id,
                {
                    "type": "error",
                    "error": str(exc),
                    "turn_id": turn_id,
                },
            )
        finally:
            await self._signal_token_stream_closed(turn_id)
            logger.debug("Producer finished for turn %s", turn_id)

    async def stream_events(
        self, turn_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield events for the active turn until terminal event and cleanup."""

        if turn_id is None:
            turn_id = self._current_turn_id

        if not turn_id:
            raise ValueError("No active turn to stream events for")

        queue = self.get_event_queue(turn_id)
        if queue is None:
            raise ValueError(f"Turn {turn_id} has no event queue")

        try:
            while True:
                event = await queue.get()
                queue.task_done()
                yield event

                if event.get("type") in {"stream_end", "error"}:
                    break
        finally:
            await self.cleanup(turn_id)

    async def _put_event(self, turn_id: str, event: Dict[str, Any]) -> None:
        """Put an event onto the turn's queue respecting backpressure."""

        queue = self.get_event_queue(turn_id)
        if not queue:
            logger.debug(
                "Dropping event for turn %s because queue is unavailable", turn_id
            )
            return

        await queue.put(event)
        logger.debug(
            "Queued event %s for turn %s (queue size=%d)",
            event.get("type"),
            turn_id,
            queue.qsize(),
        )

    async def _cancel_turn_tasks(
        self,
        turn_id: str,
        *,
        timeout: float = _INTERRUPT_WAIT_TIMEOUT,
    ) -> None:
        """Cancel background tasks associated with a turn and wait briefly."""

        turn = self.turns.get(turn_id)
        if not turn or not turn.tasks:
            return

        current_task = asyncio.current_task()
        tasks_to_cancel: List[asyncio.Task] = []

        for task in list(turn.tasks):
            if not isinstance(task, asyncio.Task):
                continue
            if task.done() or task is current_task:
                continue
            task.cancel()
            tasks_to_cancel.append(task)

        if not tasks_to_cancel:
            return

        done, pending = await asyncio.wait(
            tasks_to_cancel,
            timeout=timeout,
            return_when=asyncio.ALL_COMPLETED,
        )

        for task in done:
            with suppress(asyncio.CancelledError, Exception):
                task.result()

        if pending:
            logger.debug(
                "Timed out waiting for %d tasks to cancel for turn %s",
                len(pending),
                turn_id,
            )

    def _drain_event_queue(self, turn_id: str) -> int:
        """Remove any pending events from the client queue."""

        queue = self.get_event_queue(turn_id)
        if not queue:
            return 0

        drained = 0
        while True:
            try:
                queue.get_nowait()
                queue.task_done()
                drained += 1
            except asyncio.QueueEmpty:
                break

        return drained

    def _ensure_token_consumer(self, turn_id: str) -> None:
        """Ensure the token consumer task exists for the given turn."""

        turn = self.turns.get(turn_id)
        if not turn:
            return

        if turn.token_queue is None:
            turn.token_queue = asyncio.Queue(maxsize=self.queue_maxsize)
            turn.token_stream_closed = False

        existing_consumer = turn.token_consumer_task
        if existing_consumer and not existing_consumer.done():
            return

        consumer_task = asyncio.create_task(
            self._consume_token_events(turn_id),
            name=f"message-processor-consumer-{turn_id}",
        )
        turn.token_consumer_task = consumer_task
        self._track_task(turn_id, consumer_task)

    async def _put_token_event(self, turn_id: str, event: Dict[str, Any]) -> None:
        """Send a token event to the internal token queue."""

        turn = self.turns.get(turn_id)
        queue = turn.token_queue if turn else None
        if not queue:
            logger.debug(
                "Dropping token event for turn %s due to missing queue", turn_id
            )
            return

        await queue.put(event)
        logger.debug(
            "Queued token event for turn %s (queue size=%d)",
            turn_id,
            queue.qsize(),
        )

    async def _consume_token_events(self, turn_id: str) -> None:
        """Consume token events and emit TTS ready chunks."""

        turn = self.turns.get(turn_id)
        if not turn:
            return

        queue = turn.token_queue
        if queue is None:
            return

        try:
            while True:
                token_event = await queue.get()
                try:
                    if token_event is _TOKEN_QUEUE_SENTINEL:
                        await self._flush_tts_buffer(turn_id)
                        break

                    await self._process_token_event(turn_id, token_event)
                finally:
                    queue.task_done()
        except asyncio.CancelledError:
            logger.debug("Token consumer cancelled for turn %s", turn_id)
            raise
        except Exception as exc:  # pragma: no cover - defensive  # noqa: BLE001
            logger.error("Error consuming token events for turn %s: %s", turn_id, exc)
        finally:
            turn = self.turns.get(turn_id)
            if turn:
                turn.token_stream_closed = True

    async def _process_token_event(
        self,
        turn_id: str,
        token_event: Dict[str, Any],
    ) -> None:
        """Transform a single token event into zero or more TTS events."""

        turn = self.turns.get(turn_id)
        if not turn:
            logger.debug("Token event received for unknown turn %s", turn_id)
            return

        if not turn.chunk_processor:
            turn.chunk_processor = TextChunkProcessor()
        if not turn.tts_processor:
            turn.tts_processor = TTSTextProcessor()

        chunk = token_event.get("data") or token_event.get("chunk")
        if not chunk:
            logger.debug("Token event missing chunk data: %s", token_event)
            return

        for sentence in turn.chunk_processor.process(chunk):
            processed = turn.tts_processor.process(sentence)
            text = processed.filtered_text
            if not text or not any(char.isalnum() for char in text):
                continue
            tts_event = self._build_tts_event(
                turn_id,
                token_event,
                text,
                processed.emotion_tag,
            )
            await self._put_event(turn_id, tts_event)

    async def _flush_tts_buffer(self, turn_id: str) -> None:
        """Flush any remaining buffered text for a turn."""

        turn = self.turns.get(turn_id)
        if not turn or not turn.chunk_processor or not turn.tts_processor:
            return

        remainder = turn.chunk_processor.flush()
        if not remainder:
            return

        processed = turn.tts_processor.process(remainder)
        text = processed.filtered_text
        if not text or not any(char.isalnum() for char in text):
            return

        tts_event = self._build_tts_event(
            turn_id,
            {},
            text,
            processed.emotion_tag,
        )
        await self._put_event(turn_id, tts_event)

    def _build_tts_event(
        self,
        turn_id: str,
        base_event: Dict[str, Any],
        chunk: str,
        emotion: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Construct a tts_ready_chunk event with optional emotion metadata."""

        event = self._normalize_event(turn_id, base_event)
        tts_event = {
            key: value
            for key, value in event.items()
            if key not in {"type", "data", "chunk"}
        }
        tts_event["type"] = "tts_ready_chunk"
        tts_event["chunk"] = chunk
        if emotion:
            tts_event["emotion"] = emotion
        return tts_event

    async def _signal_token_stream_closed(self, turn_id: str) -> None:
        """Notify the token consumer that no more tokens will arrive."""

        turn = self.turns.get(turn_id)
        queue = turn.token_queue if turn else None
        if not queue or turn.token_stream_closed:
            return

        try:
            queue.put_nowait(_TOKEN_QUEUE_SENTINEL)
        except asyncio.QueueFull:
            await queue.put(_TOKEN_QUEUE_SENTINEL)

        turn.token_stream_closed = True

    async def _wait_for_token_queue(self, turn_id: str) -> None:
        """Wait for the token queue to drain pending items."""

        turn = self.turns.get(turn_id)
        queue = turn.token_queue if turn else None
        if not queue:
            return

        try:
            await asyncio.wait_for(queue.join(), timeout=_INTERRUPT_WAIT_TIMEOUT)
        except asyncio.TimeoutError:
            logger.debug(
                "Timed out waiting for token queue join for turn %s",
                turn_id,
            )
        except asyncio.CancelledError:  # pragma: no cover - defensive
            raise
        except Exception as exc:  # pragma: no cover - defensive  # noqa: BLE001
            logger.debug(
                "Error waiting for token queue for turn %s: %s",
                turn_id,
                exc,
            )

    async def _delayed_cleanup(self, delay: float):
        """Delayed cleanup of resources."""

        try:
            await asyncio.sleep(delay)
            await self.cleanup_completed_turns(0)
            logger.info(
                "Completed delayed cleanup for connection %s",
                self.connection_id,
            )
        except asyncio.CancelledError:  # pragma: no cover - defensive
            logger.debug("Cleanup task cancelled for connection %s", self.connection_id)
        except Exception as exc:  # pragma: no cover - defensive  # noqa: BLE001
            logger.error(
                "Error during delayed cleanup for connection %s: %s",
                self.connection_id,
                exc,
            )

    def _normalize_event(self, turn_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure every event contains basic identifiers."""

        normalized = dict(event)
        normalized.setdefault("turn_id", turn_id)
        normalized.setdefault("connection_id", str(self.connection_id))
        normalized.setdefault("user_id", self.user_id)
        return normalized

    def _track_task(self, turn_id: str, task: asyncio.Task) -> None:
        """Track lifecycle of a background task."""

        turn = self.turns.get(turn_id)
        if not turn:
            return

        turn.tasks.add(task)
        self.active_tasks.add(task)
        task.add_done_callback(self._build_task_cleanup(turn_id))

    def _build_task_cleanup(self, turn_id: str):
        """Create a callback that removes completed tasks from tracking."""

        def _callback(task: asyncio.Task) -> None:
            self.active_tasks.discard(task)
            turn = self.turns.get(turn_id)
            if turn:
                turn.tasks.discard(task)

        return _callback

    async def _default_agent_stream(
        self, turn_id: str, conversation_id: str, user_input: str
    ) -> AsyncIterator[Dict[str, Any]]:
        """Synthetic stream used when no agent is provided."""

        yield {
            "type": "stream_start",
            "turn_id": turn_id,
            "conversation_id": conversation_id,
            "content": user_input,
        }
        yield {
            "type": "stream_end",
            "turn_id": turn_id,
            "conversation_id": conversation_id,
        }

    def __del__(self):
        """Destructor to ensure cleanup."""

        if (
            hasattr(self, "_cleanup_task")
            and self._cleanup_task
            and not self._cleanup_task.done()
        ):
            self._cleanup_task.cancel()
