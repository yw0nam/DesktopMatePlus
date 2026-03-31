"""Data models for MessageProcessor."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger

from src.services.websocket_service.text_processors import (
    TextChunkProcessor,
    TTSTextProcessor,
)


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
    session_id: str
    status: TurnStatus = TurnStatus.PENDING
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    tasks: set[asyncio.Task] = field(default_factory=set)
    response_content: str = ""
    error_message: str | None = None
    event_queue: asyncio.Queue | None = None
    token_queue: asyncio.Queue | None = None
    token_consumer_task: asyncio.Task | None = None
    token_stream_closed: bool = False
    chunk_processor: TextChunkProcessor | None = None
    tts_processor: TTSTextProcessor | None = None
    tts_enabled: bool = True
    reference_id: str | None = None
    tts_tasks: list[asyncio.Task] = field(default_factory=list)
    tts_sequence: int = 0

    def update_status(self, status: TurnStatus, error_message: str | None = None):
        """Update turn status and timestamp."""
        self.status = status
        self.updated_at = time.time()
        if error_message:
            self.error_message = error_message
        logger.debug(f"Turn {self.turn_id} status updated to {status.value}")
