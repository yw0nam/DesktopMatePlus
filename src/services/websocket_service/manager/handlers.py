"""Message handlers for different WebSocket message types."""

import asyncio
import json
from typing import Optional
from uuid import UUID, uuid4

from langchain_core.messages import HumanMessage
from loguru import logger

from src.models.websocket import (
    AuthorizeErrorMessage,
    AuthorizeMessage,
    AuthorizeSuccessMessage,
    ErrorMessage,
    PongMessage,
)
from src.services import get_agent_service
from src.services.websocket_service.message_processor import MessageProcessor


class MessageHandler:
    """Handles different types of WebSocket messages."""

    def __init__(self, get_connection_fn, send_message_fn, disconnect_fn=None):
        """Initialize message handler.

        Args:
            get_connection_fn: Function to get connection state by ID.
            send_message_fn: Function to send messages to connections.
            disconnect_fn: Function to disconnect connections.
        """
        self.get_connection = get_connection_fn
        self.send_message = send_message_fn
        self.disconnect = disconnect_fn

    @staticmethod
    def validate_token(token: str) -> Optional[str]:
        """Validate authentication token.

        Args:
            token: Authentication token to validate.

        Returns:
            User ID if token is valid, None otherwise.
        """
        # TODO: Implement proper token validation
        # For now, accept any non-empty token
        if token and len(token.strip()) > 0:
            return f"user_{hash(token) % 10000}"
        return None

    async def handle_authorize(self, connection_id: UUID, message: AuthorizeMessage):
        """Handle client authorization request.

        Args:
            connection_id: Connection identifier.
            message: Authorization message.
        """
        connection_state = self.get_connection(connection_id)
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
                if self.disconnect:
                    self.disconnect(connection_id)

    async def handle_pong(self, connection_id: UUID, message: PongMessage):
        """Handle client pong response.

        Args:
            connection_id: Connection identifier.
            message: Pong message.
        """
        import time

        connection_state = self.get_connection(connection_id)
        if connection_state:
            connection_state.last_pong_time = time.time()
            logger.debug(f"Received pong from {connection_id}")

    async def handle_chat_message(
        self, connection_id: UUID, message_data: dict, forward_events_fn
    ):
        """Handle incoming chat message.

        Args:
            connection_id: Connection identifier (temporary per session).
            message_data: Chat message data including agent_id and user_id.
            forward_events_fn: Function to forward events to client.
        """
        connection_state = self.get_connection(connection_id)
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

        agent_service = get_agent_service()
        if agent_service is None:
            logger.error("Agent service not initialized")
            await self.send_message(
                connection_id,
                ErrorMessage(error="Agent service not initialized"),
            )
            return

        try:
            # Extract message content and persistent identifiers
            content = message_data.get("content", "")
            agent_id = message_data.get("agent_id")
            user_id = message_data.get("user_id")
            conversation_id = message_data.get("conversation_id", str(uuid4()))
            metadata = dict(message_data.get("metadata", {}) or {})

            # Validate required persistent identifiers
            if not agent_id or not isinstance(agent_id, str) or not agent_id.strip():
                await self.send_message(
                    connection_id,
                    ErrorMessage(
                        error="agent_id is required and must be a non-empty string"
                    ),
                )
                return

            if not user_id or not isinstance(user_id, str) or not user_id.strip():
                await self.send_message(
                    connection_id,
                    ErrorMessage(
                        error="user_id is required and must be a non-empty string"
                    ),
                )
                return

            metadata.setdefault("conversation_id", conversation_id)
            messages = [HumanMessage(content=content)]

            # Use persistent user_id for client_id instead of connection-based ID

            agent_stream = agent_service.stream(
                messages=messages,
                client_id=conversation_id,
                user_id=user_id,
                agent_id=agent_id,
                with_memory=True,
            )

            turn_id = await connection_state.message_processor.start_turn(
                conversation_id=conversation_id,
                user_input=content,
                agent_stream=agent_stream,
                metadata=metadata,
            )

            forward_task = asyncio.create_task(
                forward_events_fn(connection_id, turn_id),
                name=f"ws-forward-events-{turn_id}",
            )
            added = await connection_state.message_processor.add_task_to_turn(
                turn_id, forward_task
            )
            if not added:
                logger.debug(
                    "Failed to register forward task for turn %s on connection %s",
                    turn_id,
                    connection_id,
                )

        except Exception as e:
            logger.error(f"Error processing chat message from {connection_id}: {e}")
            await self.send_message(
                connection_id,
                ErrorMessage(error=f"Failed to process message: {str(e)}"),
            )

    async def handle_interrupt(
        self, connection_id: UUID, turn_id: Optional[str] = None
    ) -> bool:
        """Interrupt an active conversation turn for a connection.

        Args:
            connection_id: Connection identifier.
            turn_id: Specific turn to interrupt, or None to interrupt all active turns.

        Returns:
            True if any turns were interrupted.
        """
        connection_state = self.get_connection(connection_id)
        if not connection_state or not connection_state.message_processor:
            logger.warning(f"No message processor for connection {connection_id}")
            await self.send_message(
                connection_id,
                ErrorMessage(error="No active turns to interrupt", code=4004),
            )
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
            else:
                await self.send_message(
                    connection_id,
                    ErrorMessage(
                        error=f"Active turn {turn_id} not found or already finished",
                        code=4004,
                    ),
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
            else:
                await self.send_message(
                    connection_id,
                    ErrorMessage(
                        error="No active turns to interrupt",
                        code=4004,
                    ),
                )

            return interrupted_count > 0


async def forward_turn_events(
    connection_id: UUID, turn_id: str, get_connection_fn
) -> None:
    """Forward MessageProcessor events to the WebSocket client.

    Args:
        connection_id: Connection identifier.
        turn_id: Turn identifier.
        get_connection_fn: Function to get connection state.
    """
    connection_state = get_connection_fn(connection_id)
    if not connection_state:
        logger.debug(
            "Connection %s gone before forwarding events for turn %s",
            connection_id,
            turn_id,
        )
        return

    message_processor = connection_state.message_processor
    if not message_processor:
        logger.debug(
            "No message processor available when forwarding events for turn %s",
            turn_id,
        )
        return

    websocket = connection_state.websocket

    try:
        async for event in message_processor.stream_events(turn_id):
            try:
                await websocket.send_text(json.dumps(event, default=str))
            except Exception as send_error:  # noqa: BLE001
                logger.error(
                    "Failed to send event %s for turn %s on connection %s: %s",
                    event.get("type"),
                    turn_id,
                    connection_id,
                    send_error,
                )
                break
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Error forwarding events for turn %s on connection %s: %s",
            turn_id,
            connection_id,
            exc,
        )
