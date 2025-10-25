"""WebSocket connection manager orchestrator."""

import asyncio
import json
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from weakref import WeakSet

from fastapi import WebSocket
from loguru import logger
from pydantic import ValidationError

from src.models.websocket import (
    AuthorizeMessage,
    ErrorMessage,
    InterruptStreamMessage,
    MessageType,
    PongMessage,
    ServerMessage,
)

from .connection import ConnectionState
from .handlers import MessageHandler, forward_turn_events
from .heartbeat import HeartbeatMonitor


class WebSocketManager:
    """Manages WebSocket connections, authentication, and message routing."""

    def __init__(self, ping_interval: int = 30, pong_timeout: int = 10):
        """Initialize WebSocket manager.

        Args:
            ping_interval: Interval between ping messages in seconds.
            pong_timeout: Timeout for pong response in seconds.
        """
        self.connections: Dict[UUID, ConnectionState] = {}
        self.ping_interval = ping_interval
        self.pong_timeout = pong_timeout
        self._heartbeat_tasks: WeakSet = WeakSet()

        # Initialize components
        self._message_handler = MessageHandler(
            get_connection_fn=self._get_connection,
            send_message_fn=self.send_message,
            disconnect_fn=self.disconnect,
        )
        self._heartbeat_monitor = HeartbeatMonitor(
            ping_interval=ping_interval,
            pong_timeout=pong_timeout,
            get_connection_fn=self._get_connection,
            send_message_fn=self.send_message,
            disconnect_fn=self.disconnect,
        )

    def _get_connection(self, connection_id: UUID) -> Optional[ConnectionState]:
        """Get connection state by ID.

        Args:
            connection_id: Connection identifier.

        Returns:
            Connection state or None if not found.
        """
        return self.connections.get(connection_id)

    async def connect(self, websocket: WebSocket) -> UUID:
        """Accept a new WebSocket connection.

        Args:
            websocket: The WebSocket connection.

        Returns:
            Unique connection identifier.
        """
        await websocket.accept()
        connection_id = uuid4()
        connection_state = ConnectionState(websocket, connection_id)
        self.connections[connection_id] = connection_state

        logger.info(f"WebSocket connection established: {connection_id}")

        # Start heartbeat task for this connection
        heartbeat_task = asyncio.create_task(
            self._heartbeat_monitor.heartbeat_loop(connection_state)
        )
        self._heartbeat_tasks.add(heartbeat_task)

        return connection_id

    def disconnect(self, connection_id: UUID):
        """Disconnect and cleanup a WebSocket connection.

        Args:
            connection_id: The connection identifier to disconnect.
        """
        if connection_id in self.connections:
            connection_state = self.connections[connection_id]

            # Shutdown MessageProcessor if it exists
            if connection_state.message_processor:
                # Create a task to shutdown the message processor
                asyncio.create_task(connection_state.message_processor.shutdown())

            logger.info(f"WebSocket connection disconnected: {connection_id}")
            del self.connections[connection_id]

    async def send_message(self, connection_id: UUID, message: ServerMessage):
        """Send a message to a specific connection.

        Args:
            connection_id: Target connection identifier.
            message: Message to send.
        """
        if connection_id not in self.connections:
            logger.warning(
                f"Attempted to send message to unknown connection: {connection_id}"
            )
            return

        connection_state = self.connections[connection_id]
        try:
            message_dict = message.model_dump()
            # Convert any UUID objects to strings for JSON serialization
            message_json = json.dumps(message_dict, default=str)
            await connection_state.websocket.send_text(message_json)
            logger.debug(f"Sent message to {connection_id}: {message.type}")
        except Exception as e:
            logger.error(f"Failed to send message to {connection_id}: {e}")
            self.disconnect(connection_id)

    async def broadcast_message(
        self, message: ServerMessage, authenticated_only: bool = True
    ):
        """Broadcast a message to all connected clients.

        Args:
            message: Message to broadcast.
            authenticated_only: If True, only send to authenticated connections.
        """
        connections_to_send = []
        for connection_state in self.connections.values():
            if not authenticated_only or connection_state.is_authenticated:
                connections_to_send.append(connection_state.connection_id)

        for connection_id in connections_to_send:
            await self.send_message(connection_id, message)

    def validate_token(self, token: str) -> Optional[str]:
        """Validate authentication token.

        Args:
            token: Authentication token to validate.

        Returns:
            User ID if token is valid, None otherwise.
        """
        return self._message_handler.validate_token(token)

    async def handle_authorize(self, connection_id: UUID, message: AuthorizeMessage):
        """Handle client authorization request.

        Args:
            connection_id: Connection identifier.
            message: Authorization message.
        """
        await self._message_handler.handle_authorize(connection_id, message)

    async def handle_pong(self, connection_id: UUID, message: PongMessage):
        """Handle client pong response.

        Args:
            connection_id: Connection identifier.
            message: Pong message.
        """
        await self._message_handler.handle_pong(connection_id, message)

    async def handle_chat_message(self, connection_id: UUID, message_data: dict):
        """Handle incoming chat message.

        Args:
            connection_id: Connection identifier.
            message_data: Chat message data.
        """
        await self._message_handler.handle_chat_message(
            connection_id, message_data, self._forward_turn_events
        )

    async def interrupt_active_turn(
        self, connection_id: UUID, turn_id: Optional[str] = None
    ) -> bool:
        """Interrupt an active conversation turn for a connection.

        Args:
            connection_id: Connection identifier.
            turn_id: Specific turn to interrupt, or None to interrupt all active turns.

        Returns:
            True if any turns were interrupted.
        """
        return await self._message_handler.handle_interrupt(connection_id, turn_id)

    async def get_connection_stats(
        self, connection_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific connection.

        Args:
            connection_id: Connection identifier.

        Returns:
            Dictionary with connection statistics or None if not found.
        """
        connection_state = self.connections.get(connection_id)
        if not connection_state:
            return None

        stats = {
            "connection_id": str(connection_id),
            "user_id": connection_state.user_id,
            "is_authenticated": connection_state.is_authenticated,
            "created_at": connection_state.created_at,
            "last_ping_time": connection_state.last_ping_time,
            "last_pong_time": connection_state.last_pong_time,
        }

        if connection_state.message_processor:
            stats.update(connection_state.message_processor.get_stats())

        return stats

    async def _forward_turn_events(self, connection_id: UUID, turn_id: str) -> None:
        """Forward MessageProcessor events to the WebSocket client.

        Args:
            connection_id: Connection identifier.
            turn_id: Turn identifier.
        """
        await forward_turn_events(connection_id, turn_id, self._get_connection)

    async def handle_message(self, connection_id: UUID, raw_message: str):
        """Handle incoming WebSocket message.

        Args:
            connection_id: Connection identifier.
            raw_message: Raw JSON message string.
        """
        connection_state = self.connections.get(connection_id)
        if not connection_state:
            logger.warning(f"Received message from unknown connection: {connection_id}")
            return

        try:
            # Parse JSON message
            message_data = json.loads(raw_message)

            # Validate message type
            message_type = message_data.get("type")
            if not message_type:
                await self.send_message(
                    connection_id, ErrorMessage(error="Missing message type")
                )
                return

            # Route message based on type
            if message_type == MessageType.AUTHORIZE:
                message = AuthorizeMessage(**message_data)
                await self._message_handler.handle_authorize(connection_id, message)

            elif message_type == MessageType.PONG:
                message = PongMessage(**message_data)
                await self._message_handler.handle_pong(connection_id, message)

            elif message_type == MessageType.CHAT_MESSAGE:
                # Handle chat message through MessageProcessor
                await self._message_handler.handle_chat_message(
                    connection_id, message_data, self._forward_turn_events
                )

            elif message_type == MessageType.INTERRUPT_STREAM:
                if not connection_state.is_authenticated:
                    await self.send_message(
                        connection_id, ErrorMessage(error="Authentication required")
                    )
                    return

                message = InterruptStreamMessage(**message_data)
                await self.interrupt_active_turn(connection_id, message.turn_id)

            else:
                # Check if connection is authenticated for other message types
                if not connection_state.is_authenticated:
                    await self.send_message(
                        connection_id, ErrorMessage(error="Authentication required")
                    )
                    return

                # TODO: Handle other message types (chat, etc.)
                logger.info(
                    f"Unhandled message type from {connection_id}: {message_type}"
                )
                await self.send_message(
                    connection_id,
                    ErrorMessage(error=f"Unsupported message type: {message_type}"),
                )

        except ValidationError as e:
            logger.error(f"Message validation error from {connection_id}: {e}")
            await self.send_message(
                connection_id, ErrorMessage(error="Invalid message format")
            )

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error from {connection_id}: {e}")
            await self.send_message(
                connection_id, ErrorMessage(error="Invalid JSON format")
            )

        except Exception as e:
            logger.error(f"Unexpected error handling message from {connection_id}: {e}")
            await self.send_message(
                connection_id, ErrorMessage(error="Internal server error")
            )


# Global WebSocket manager instance
websocket_manager = WebSocketManager()
