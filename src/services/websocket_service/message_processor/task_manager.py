"""Task management utilities for MessageProcessor."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import TYPE_CHECKING, List

from loguru import logger

from .constants import INTERRUPT_WAIT_TIMEOUT

if TYPE_CHECKING:
    from .processor import MessageProcessor


class TaskManager:
    """Manages task lifecycle for MessageProcessor."""

    def __init__(self, processor: MessageProcessor):
        """Initialize TaskManager.

        Args:
            processor: The parent MessageProcessor instance.
        """
        self.processor = processor

    def track_task(self, turn_id: str, task: asyncio.Task) -> None:
        """Track lifecycle of a background task."""
        turn = self.processor.turns.get(turn_id)
        if not turn:
            return

        turn.tasks.add(task)
        self.processor.active_tasks.add(task)
        task.add_done_callback(self._build_task_cleanup(turn_id))

    def _build_task_cleanup(self, turn_id: str):
        """Create a callback that removes completed tasks from tracking."""

        def _callback(task: asyncio.Task) -> None:
            self.processor.active_tasks.discard(task)
            turn = self.processor.turns.get(turn_id)
            if turn:
                turn.tasks.discard(task)

        return _callback

    async def cancel_turn_tasks(
        self,
        turn_id: str,
        *,
        timeout: float = INTERRUPT_WAIT_TIMEOUT,
    ) -> None:
        """Cancel background tasks associated with a turn and wait briefly."""
        turn = self.processor.turns.get(turn_id)
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

    def drain_event_queue(self, turn_id: str) -> int:
        """Remove any pending events from the client queue."""
        queue = self.processor.get_event_queue(turn_id)
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

    def ensure_token_consumer(self, turn_id: str) -> None:
        """Ensure the token consumer task exists for the given turn."""
        turn = self.processor.turns.get(turn_id)
        if not turn:
            return

        if turn.token_queue is None:
            turn.token_queue = asyncio.Queue(maxsize=self.processor.queue_maxsize)
            turn.token_stream_closed = False

        existing_consumer = turn.token_consumer_task
        if existing_consumer and not existing_consumer.done():
            return

        consumer_task = asyncio.create_task(
            self.processor._event_handler.consume_token_events(turn_id),
            name=f"message-processor-consumer-{turn_id}",
        )
        turn.token_consumer_task = consumer_task
        self.track_task(turn_id, consumer_task)
