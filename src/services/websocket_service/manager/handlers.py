"""Message handlers for different WebSocket message types."""

import asyncio
import json
from uuid import UUID, uuid4

from langchain_core.messages import HumanMessage
from loguru import logger

from src.models.websocket import (
    AuthorizeErrorMessage,
    AuthorizeMessage,
    AuthorizeSuccessMessage,
    ChatMessage,
    ErrorMessage,
    PongMessage,
)
from src.services import get_agent_service
from src.services.service_manager import (
    get_emotion_motion_mapper,
    get_session_registry,
    get_tts_service,
)
from src.services.websocket_service.message_processor import MessageProcessor


class MessageHandler:
    """Handles different types of WebSocket messages."""

    def __init__(self, get_connection_fn, send_message_fn, close_connection_fn):
        """Initialize message handler.

        Args:
            get_connection_fn: Function to get connection state by ID.
            send_message_fn: Function to send messages to connections.
            close_connection_fn: Function to close connections with code and reason.
        """
        self.get_connection = get_connection_fn
        self.send_message = send_message_fn
        self.close_connection = close_connection_fn

    @staticmethod
    def validate_token(token: str) -> str | None:
        """Validate authentication token.

        Args:
            token: Authentication token to validate.

        Returns:
            User ID if token is valid, None otherwise.
        """
        # TODO: Implement proper token validation
        # For now, always return a valid token (NOT FOR PRODUCTION)
        return "valid_token"

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
                connection_id=connection_id,
                user_id=user_id,
                tts_service=get_tts_service(),
                mapper=get_emotion_motion_mapper(),
            )

            response = AuthorizeSuccessMessage(connection_id=connection_id)
            await self.send_message(connection_id, response)
            logger.info(f"Connection {connection_id} authenticated as {user_id}")
        else:
            response = AuthorizeErrorMessage(error="Invalid authentication token")
            await self.send_message(connection_id, response)
            logger.warning(f"Authentication failed for connection {connection_id}")

            # Close connection after sending error using standardized method
            await self.close_connection(
                connection_id=connection_id,
                code=4001,
                reason="Authentication failed",
                notify_client=True,
            )

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
        self, connection_id: UUID, message_data: ChatMessage, forward_events_fn
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
            persona_id = message_data.get("persona_id", "yuri")
            # Extract session_id from client (None for new conversations)
            session_id = message_data.get("session_id")
            message_data.get("limit", 10)
            images = message_data.get("images", None)
            metadata = dict(message_data.get("metadata", {}) or {})
            tts_enabled = message_data.get("tts_enabled", True)
            reference_id = message_data.get("reference_id", None)

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

            # CRITICAL: Generate UUID for new conversations (when client sends None)
            # This ensures a single UUID is used throughout the entire conversation turn
            if session_id is None:
                session_id = str(uuid4())
                logger.info(
                    f"Generated new session_id {session_id} for user {user_id}, agent {agent_id}"
                )
            else:
                logger.info(
                    f"Using existing session_id {session_id} for user {user_id}, agent {agent_id}"
                )

            session_id = str(session_id)
            metadata.setdefault("session_id", session_id)

            registry = get_session_registry()
            if registry:
                await asyncio.to_thread(registry.upsert, session_id, user_id, agent_id)

            content = [{"type": "text", "text": content}]
            if images and agent_service.support_image:
                content.extend(images)

            metadata["user_id"] = user_id
            metadata["agent_id"] = agent_id

            agent_stream = agent_service.stream(
                messages=[HumanMessage(content=content)],
                session_id=session_id,
                persona_id=persona_id,
                user_id=user_id,
                agent_id=agent_id,
            )

            turn_id = await connection_state.message_processor.start_turn(
                session_id=session_id,
                user_input=content,
                agent_stream=agent_stream,
                metadata=metadata,
                tts_enabled=tts_enabled,
                reference_id=reference_id,
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
                    f"Failed to register forward task for turn {turn_id} on connection {connection_id}"
                )

        except RuntimeError as e:
            # Handle concurrent turn constraint violation
            error_msg = str(e)
            if "Another turn is already active" in error_msg:
                logger.warning(
                    f"Concurrent turn rejected for {connection_id}: {error_msg}"
                )
                await self.send_message(
                    connection_id,
                    ErrorMessage(
                        error=error_msg,
                        code=4002,  # Custom code for concurrent turn rejection
                    ),
                )
            else:
                logger.error(
                    f"Runtime error processing chat message from {connection_id}: {e}"
                )
                await self.send_message(
                    connection_id,
                    ErrorMessage(error=f"Failed to process message: {e!s}"),
                )

        except Exception as e:
            logger.error(f"Error processing chat message from {connection_id}: {e}")
            await self.send_message(
                connection_id,
                ErrorMessage(error=f"Failed to process message: {e!s}"),
            )

    async def handle_interrupt(
        self, connection_id: UUID, turn_id: str | None = None
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
            f"Connection {connection_id} gone before forwarding events for turn {turn_id}"
        )
        return

    message_processor = connection_state.message_processor
    if not message_processor:
        logger.debug(
            f"No message processor available when forwarding events for turn {turn_id}"
        )
        return

    websocket = connection_state.websocket

    try:
        async for event in message_processor.stream_events(turn_id):
            event_type = event.get("type")
            logger.debug(
                f"Forwarding event {event_type} for turn {turn_id} to connection {connection_id}"
            )
            try:
                event_json = json.dumps(event, default=str)
                await websocket.send_text(event_json)
                logger.info(
                    f"Sent {event_type} event to connection {connection_id} (turn {turn_id})"
                )
            except Exception as send_error:
                logger.error(
                    f"Failed to send event {event_type} for turn {turn_id} on connection {connection_id}: {send_error}"
                )
                break
    except Exception as exc:
        logger.error(
            f"Error forwarding events for turn {turn_id} on connection {connection_id}: {exc}"
        )
