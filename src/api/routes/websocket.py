"""WebSocket API routes."""

import asyncio
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from src.configs.settings import get_settings
from src.services.websocket_service import websocket_manager
from src.services.websocket_service.error_classifier import (
    ErrorClassifier,
    ErrorSeverity,
)

router = APIRouter(prefix="/v1/chat", tags=["WebSocket"])


@router.websocket("/stream")
async def websocket_chat_stream(websocket: WebSocket):
    """WebSocket endpoint for real-time chat streaming.

    This endpoint provides:
    - Connection lifecycle management with unique connection IDs
    - Authentication via 'authorize' message with token
    - Heartbeat mechanism with ping/pong messages
    - Message routing and validation
    - Graceful error handling and connection cleanup

    Expected client flow:
    1. Connect to wss://host/v1/chat/stream
    2. Send 'authorize' message with valid token
    3. Receive 'authorize_success' with connection_id
    4. Exchange messages and respond to ping messages with pong
    5. Handle errors and disconnections gracefully
    """
    connection_id = None
    request_id = f"ws_{uuid.uuid4().hex[:8]}"

    # Bind request ID to logger for this WebSocket connection
    ws_logger = logger.bind(request_id=request_id)

    try:
        # Accept connection and get unique ID
        connection_id = await websocket_manager.connect(websocket)
        ws_logger.info(f"🔌 WebSocket connected: {connection_id}")

        # Configuration for error tolerance and inactivity (loaded from YAML via settings)
        settings = get_settings()
        error_count = 0
        max_error_tolerance = settings.websocket.max_error_tolerance
        error_sleep_seconds = settings.websocket.error_backoff_seconds
        inactivity_timeout = settings.websocket.inactivity_timeout_seconds

        # Listen for messages
        while True:
            try:
                # Wait for a message with inactivity timeout
                raw_message = await asyncio.wait_for(
                    websocket.receive_text(), timeout=inactivity_timeout
                )
                ws_logger.debug(f"💬 Message received: {raw_message[:100]}...")

                # Reset error counter on successful receive
                error_count = 0

                # Handle message through manager
                await websocket_manager.handle_message(connection_id, raw_message)

            except WebSocketDisconnect:
                ws_logger.info(f"⚡ WebSocket disconnected: {connection_id}")
                break

            except TimeoutError:
                # No message received for configured inactivity period
                ws_logger.info(
                    f"⏱️ Inactivity timeout ({inactivity_timeout}s): {connection_id}"
                )
                break

            except Exception as e:
                # Classify error to determine handling strategy
                severity = ErrorClassifier.classify(e)
                ws_logger.error(
                    f"Error handling message ({severity}): {e}", exc_info=True
                )

                error_count += 1

                # Check if we should retry based on error classification
                if not ErrorClassifier.should_retry(
                    e, error_count, max_error_tolerance
                ):
                    if severity == ErrorSeverity.FATAL:
                        ws_logger.error(
                            f"Fatal error, closing connection: {connection_id}"
                        )
                    else:
                        ws_logger.error(
                            f"Exceeded error tolerance ({error_count}/{max_error_tolerance}): {connection_id}"
                        )
                    break

                # Apply appropriate backoff delay
                backoff_delay = ErrorClassifier.get_backoff_delay(
                    e, error_sleep_seconds
                )
                if backoff_delay > 0:
                    ws_logger.debug(
                        f"Applying backoff delay: {backoff_delay}s (error {error_count}/{max_error_tolerance})"
                    )
                    try:
                        await asyncio.sleep(backoff_delay)
                    except asyncio.CancelledError:
                        # If cancellation is requested, break the loop to allow cleanup
                        break

                # Continue listening after handling error
                continue

    except WebSocketDisconnect:
        ws_logger.info(f"⚡ WebSocket disconnected during setup: {connection_id}")

    except Exception as e:
        ws_logger.error(f"Unexpected WebSocket error: {e}")

    finally:
        # Cleanup connection
        if connection_id:
            await websocket_manager.disconnect(connection_id)
            ws_logger.info(f"🧹 WebSocket cleaned up: {connection_id}")
