"""WebSocket service for real-time communication."""

from .manager import websocket_manager
from .message_processor import MessageProcessor

__all__ = ["websocket_manager", "MessageProcessor"]
