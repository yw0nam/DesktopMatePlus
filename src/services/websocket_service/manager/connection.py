"""Connection state and lifecycle management."""

import time
from typing import Optional
from uuid import UUID

from fastapi import WebSocket

from src.services.websocket_service.message_processor import MessageProcessor


class ConnectionState:
    """State information for a WebSocket connection."""

    def __init__(self, websocket: WebSocket, connection_id: UUID):
        """Initialize connection state.

        Args:
            websocket: The WebSocket connection.
            connection_id: Unique identifier for this connection.
        """
        self.websocket = websocket
        self.connection_id = connection_id
        self.is_authenticated = False
        self.last_ping_time: Optional[float] = None
        self.last_pong_time: Optional[float] = None
        self.user_id: Optional[str] = None
        self.created_at = time.time()
        self.message_processor: Optional[MessageProcessor] = None
