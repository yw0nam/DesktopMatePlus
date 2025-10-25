"""WebSocket manager module for connection and message handling.

This module provides WebSocket connection management, message routing,
authentication, and heartbeat monitoring.
"""

from .connection import ConnectionState
from .handlers import MessageHandler, forward_turn_events
from .heartbeat import HeartbeatMonitor
from .websocket_manager import WebSocketManager, websocket_manager

__all__ = [
    "WebSocketManager",
    "websocket_manager",
    "ConnectionState",
    "MessageHandler",
    "HeartbeatMonitor",
    "forward_turn_events",
]
