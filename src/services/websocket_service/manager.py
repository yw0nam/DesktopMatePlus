"""WebSocket connection management and utilities."""

import asyncio
import json
import time
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from weakref import WeakSet

from fastapi import WebSocket
from loguru import logger
from pydantic import ValidationError

from src.models.websocket import (
    AuthorizeErrorMessage,
    AuthorizeMessage,
    AuthorizeSuccessMessage,
    ErrorMessage,
    MessageType,
    PingMessage,
    PongMessage,
    ServerMessage,
)

from .message_processor import MessageProcessor, TurnStatus


class ConnectionState:
    """State information for a WebSocket connection."""

    def __init__(self, websocket: WebSocket, connection_id: UUID):
        self.websocket = websocket
        self.connection_id = connection_id
        self.is_authenticated = False
        self.last_ping_time: Optional[float] = None
        self.last_pong_time: Optional[float] = None
        self.user_id: Optional[str] = None
        self.created_at = time.time()
        self.message_processor: Optional[MessageProcessor] = None


class WebSocketManager:
    """Manages WebSocket connections, authentication, and message routing."""

    def __init__(self, ping_interval: int = 30, pong_timeout: int = 10):
        """Initialize WebSocket manager.

        Args:
            ping_interval: Interval between ping messages in seconds
            pong_timeout: Timeout for pong response in seconds
        """
        self.connections: Dict[UUID, ConnectionState] = {}
        self.ping_interval = ping_interval
        self.pong_timeout = pong_timeout
        self._heartbeat_tasks: WeakSet = WeakSet()

    async def connect(self, websocket: WebSocket) -> UUID:
        """Accept a new WebSocket connection.

        Args:
            websocket: The WebSocket connection

        Returns:
            UUID: Unique connection identifier
        """
        await websocket.accept()
        connection_id = uuid4()
        connection_state = ConnectionState(websocket, connection_id)
        self.connections[connection_id] = connection_state

        logger.info(f"WebSocket connection established: {connection_id}")

        # Start heartbeat task for this connection
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(connection_state))
        self._heartbeat_tasks.add(heartbeat_task)

        return connection_id

    def disconnect(self, connection_id: UUID):
        """Disconnect and cleanup a WebSocket connection.

        Args:
            connection_id: The connection identifier to disconnect
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
            connection_id: Target connection identifier
            message: Message to send
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
            message: Message to broadcast
            authenticated_only: If True, only send to authenticated connections
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
            token: Authentication token to validate

        Returns:
            Optional[str]: User ID if token is valid, None otherwise
        """
        # TODO: Implement proper token validation
        # For now, accept any non-empty token
        if token and len(token.strip()) > 0:
            return f"user_{hash(token) % 10000}"
        return None

    async def handle_authorize(self, connection_id: UUID, message: AuthorizeMessage):
        """Handle client authorization request.

        Args:
            connection_id: Connection identifier
            message: Authorization message
        """
        connection_state = self.connections.get(connection_id)
        if not connection_state:
            return

        user_id = self.validate_token(message.token)
        if user_id:
            connection_state.is_authenticated = True
            connection_state.user_id = user_id

            # Initialize MessageProcessor for this connection
            connection_state.message_processor = MessageProcessor(
                connection_id=connection_id, user_id=user_id
            )

            response = AuthorizeSuccessMessage(connection_id=connection_id)
            await self.send_message(connection_id, response)
            logger.info(f"Connection {connection_id} authenticated as {user_id}")
        else:
            response = AuthorizeErrorMessage(error="Invalid authentication token")
            await self.send_message(connection_id, response)
            logger.warning(f"Authentication failed for connection {connection_id}")

            # Close connection after sending error
            try:
                await connection_state.websocket.close(
                    code=4001, reason="Authentication failed"
                )
            except Exception as e:
                logger.error(f"Error closing websocket after auth failure: {e}")
            finally:
                self.disconnect(connection_id)

    async def handle_pong(self, connection_id: UUID, message: PongMessage):
        """Handle client pong response.

        Args:
            connection_id: Connection identifier
            message: Pong message
        """
        connection_state = self.connections.get(connection_id)
        if connection_state:
            connection_state.last_pong_time = time.time()
            logger.debug(f"Received pong from {connection_id}")

    async def handle_chat_message(self, connection_id: UUID, message_data: dict):
        """Handle incoming chat message.

        Args:
            connection_id: Connection identifier
            message_data: Chat message data
        """
        connection_state = self.connections.get(connection_id)
        if not connection_state:
            logger.error(f"No connection state for {connection_id}")
            return

        # Check authentication first
        if not connection_state.is_authenticated:
            logger.warning(f"Unauthenticated chat message attempt from {connection_id}")
            await self.send_message(
                connection_id, ErrorMessage(error="Authentication required")
            )
            return

        # Check message processor availability
        if not connection_state.message_processor:
            logger.error(f"No message processor for connection {connection_id}")
            await self.send_message(
                connection_id, ErrorMessage(error="Message processor not initialized")
            )
            return

        try:
            # Extract message content
            content = message_data.get("content", "")
            metadata = message_data.get("metadata", {})

            # Start a new conversation turn
            turn_id = await connection_state.message_processor.start_conversation_turn(
                user_message=content, metadata=metadata
            )

            # Update turn status to processing
            await connection_state.message_processor.update_turn_status(
                turn_id, TurnStatus.PROCESSING
            )

            # TODO: This is where we'll integrate with LangGraph in future tasks
            # For now, just complete the turn with a placeholder response
            logger.info(
                f"Processing chat message for turn {turn_id}: {content[:100]}..."
            )

            # Simulate processing (this will be replaced with actual LangGraph integration)
            await asyncio.sleep(0.1)  # Small delay to simulate processing

            # Complete the turn
            await connection_state.message_processor.complete_turn(
                turn_id,
                metadata={
                    "response": "MessageProcessor integration complete - awaiting LangGraph integration"
                },
            )

            # Send a placeholder response
            from src.models.websocket import ChatResponseMessage

            response = ChatResponseMessage(
                content=f"Turn {turn_id} processed successfully. MessageProcessor is working!",
                metadata={"turn_id": turn_id, "status": "completed"},
            )
            await self.send_message(connection_id, response)

        except Exception as e:
            logger.error(f"Error processing chat message from {connection_id}: {e}")
            await self.send_message(
                connection_id,
                ErrorMessage(error=f"Failed to process message: {str(e)}"),
            )

    async def interrupt_active_turn(
        self, connection_id: UUID, turn_id: Optional[str] = None
    ) -> bool:
        """Interrupt an active conversation turn for a connection.

        Args:
            connection_id: Connection identifier
            turn_id: Specific turn to interrupt, or None to interrupt all active turns

        Returns:
            bool: True if any turns were interrupted
        """
        connection_state = self.connections.get(connection_id)
        if not connection_state or not connection_state.message_processor:
            logger.warning(f"No message processor for connection {connection_id}")
            return False

        if turn_id:
            # Interrupt specific turn
            result = await connection_state.message_processor.interrupt_turn(
                turn_id, "Client requested interruption"
            )
            if result:
                await self.send_message(
                    connection_id,
                    ErrorMessage(error=f"Turn {turn_id} interrupted", code=4003),
                )
            return result
        else:
            # Interrupt all active turns
            active_turns = await connection_state.message_processor.get_active_turns()
            interrupted_count = 0

            for turn in active_turns:
                result = await connection_state.message_processor.interrupt_turn(
                    turn.turn_id, "Client requested interruption"
                )
                if result:
                    interrupted_count += 1

            if interrupted_count > 0:
                await self.send_message(
                    connection_id,
                    ErrorMessage(
                        error=f"Interrupted {interrupted_count} active turns", code=4003
                    ),
                )

            return interrupted_count > 0

    async def get_connection_stats(
        self, connection_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific connection.

        Args:
            connection_id: Connection identifier

        Returns:
            Dictionary with connection statistics or None if not found
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

    async def handle_message(self, connection_id: UUID, raw_message: str):
        """Handle incoming WebSocket message.

        Args:
            connection_id: Connection identifier
            raw_message: Raw JSON message string
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
                await self.handle_authorize(connection_id, message)

            elif message_type == MessageType.PONG:
                message = PongMessage(**message_data)
                await self.handle_pong(connection_id, message)

            elif message_type == MessageType.CHAT_MESSAGE:
                # Handle chat message through MessageProcessor
                await self.handle_chat_message(connection_id, message_data)

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

    async def _heartbeat_loop(self, connection_state: ConnectionState):
        """Heartbeat loop for a connection.

        Args:
            connection_state: Connection state to monitor
        """
        connection_id = connection_state.connection_id

        try:
            while connection_id in self.connections:
                # Send ping
                ping_message = PingMessage()
                await self.send_message(connection_id, ping_message)
                connection_state.last_ping_time = time.time()

                # Wait for ping interval
                await asyncio.sleep(self.ping_interval)

                # Check if we received pong within timeout
                if (
                    connection_state.last_pong_time is None
                    or connection_state.last_ping_time is None
                    or (
                        connection_state.last_ping_time
                        - connection_state.last_pong_time
                    )
                    > self.pong_timeout
                ):
                    logger.warning(
                        f"Connection {connection_id} failed to respond to ping"
                    )
                    # Close connection due to timeout
                    try:
                        await connection_state.websocket.close(
                            code=4000, reason="Ping timeout"
                        )
                    except Exception as e:
                        logger.error(
                            f"Error closing websocket due to ping timeout: {e}"
                        )
                        break
                    finally:
                        self.disconnect(connection_id)

        except asyncio.CancelledError:
            logger.debug(f"Heartbeat loop cancelled for {connection_id}")
        except Exception as e:
            logger.error(f"Error in heartbeat loop for {connection_id}: {e}")
            self.disconnect(connection_id)


# Global WebSocket manager instance
websocket_manager = WebSocketManager()
