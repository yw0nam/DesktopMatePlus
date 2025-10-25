"""Event handling for MessageProcessor."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, Optional

from loguru import logger

from ..text_processors import TextChunkProcessor, TTSTextProcessor
from .constants import INTERRUPT_WAIT_TIMEOUT, TOKEN_QUEUE_SENTINEL
from .models import TurnStatus

if TYPE_CHECKING:
    from .processor import MessageProcessor


class EventHandler:
    """Handles event processing for MessageProcessor."""

    def __init__(self, processor: MessageProcessor):
        """Initialize EventHandler.

        Args:
            processor: The parent MessageProcessor instance.
        """
        self.processor = processor

    async def produce_agent_events(
        self, turn_id: str, agent_stream: AsyncIterator[Dict[str, Any]]
    ) -> None:
        """Consume AgentService events and forward them to the queue."""
        try:
            async for raw_event in agent_stream:
                event = self.processor._normalize_event(turn_id, raw_event)
                event_type = event.get("type")

                if event_type == "stream_token":
                    await self._put_token_event(turn_id, event)
                    continue

                if event_type == "stream_start":
                    await self.processor._put_event(turn_id, event)
                    await self.processor.update_turn_status(
                        turn_id, TurnStatus.PROCESSING
                    )
                    continue

                if event_type == "stream_end":
                    await self._signal_token_stream_closed(turn_id)
                    await self._wait_for_token_queue(turn_id)
                    await self.processor._put_event(turn_id, event)
                    await self.processor.complete_turn(turn_id)
                    continue

                if event_type == "error":
                    await self._signal_token_stream_closed(turn_id)
                    await self._wait_for_token_queue(turn_id)
                    await self.processor._put_event(turn_id, event)
                    await self.processor.fail_turn(
                        turn_id, event.get("error", "Unknown error")
                    )
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
            await self.processor.fail_turn(turn_id, str(exc))
            await self._signal_token_stream_closed(turn_id)
            await self._wait_for_token_queue(turn_id)
            await self.processor._put_event(
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

    async def consume_token_events(self, turn_id: str) -> None:
        """Consume token events and emit TTS ready chunks."""
        turn = self.processor.turns.get(turn_id)
        if not turn:
            return

        queue = turn.token_queue
        if queue is None:
            return

        try:
            while True:
                token_event = await queue.get()
                try:
                    if token_event is TOKEN_QUEUE_SENTINEL:
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
            turn = self.processor.turns.get(turn_id)
            if turn:
                turn.token_stream_closed = True

    async def _process_token_event(
        self,
        turn_id: str,
        token_event: Dict[str, Any],
    ) -> None:
        """Transform a single token event into zero or more TTS events."""
        turn = self.processor.turns.get(turn_id)
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
            await self.processor._put_event(turn_id, tts_event)

    async def _flush_tts_buffer(self, turn_id: str) -> None:
        """Flush any remaining buffered text for a turn."""
        turn = self.processor.turns.get(turn_id)
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
        await self.processor._put_event(turn_id, tts_event)

    def _build_tts_event(
        self,
        turn_id: str,
        base_event: Dict[str, Any],
        chunk: str,
        emotion: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Construct a tts_ready_chunk event with optional emotion metadata."""
        event = self.processor._normalize_event(turn_id, base_event)
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

    async def _put_token_event(self, turn_id: str, event: Dict[str, Any]) -> None:
        """Send a token event to the internal token queue."""
        turn = self.processor.turns.get(turn_id)
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

    async def _signal_token_stream_closed(self, turn_id: str) -> None:
        """Notify the token consumer that no more tokens will arrive."""
        turn = self.processor.turns.get(turn_id)
        queue = turn.token_queue if turn else None
        if not queue or turn.token_stream_closed:
            return

        try:
            queue.put_nowait(TOKEN_QUEUE_SENTINEL)
        except asyncio.QueueFull:
            await queue.put(TOKEN_QUEUE_SENTINEL)

        turn.token_stream_closed = True

    async def _wait_for_token_queue(self, turn_id: str) -> None:
        """Wait for the token queue to drain pending items."""
        turn = self.processor.turns.get(turn_id)
        queue = turn.token_queue if turn else None
        if not queue:
            return

        try:
            await asyncio.wait_for(queue.join(), timeout=INTERRUPT_WAIT_TIMEOUT)
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
