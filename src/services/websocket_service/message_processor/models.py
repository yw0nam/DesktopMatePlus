"""Data models for MessageProcessor."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Set

from loguru import logger

from ..text_processors import TextChunkProcessor, TTSTextProcessor


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
