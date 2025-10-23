"""WebSocket API routes."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from src.services.websocket_service import websocket_manager

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

    try:
        # Accept connection and get unique ID
        connection_id = await websocket_manager.connect(websocket)
        logger.info(f"WebSocket connection accepted: {connection_id}")

        # Listen for messages
        while True:
            try:
                # Receive message from client
                raw_message = await websocket.receive_text()
                logger.debug(
                    f"Received message from {connection_id}: {raw_message[:100]}..."
                )

                # Handle message through manager
                await websocket_manager.handle_message(connection_id, raw_message)

            except WebSocketDisconnect:
                logger.info(f"WebSocket client disconnected: {connection_id}")
                break

            except Exception as e:
                logger.error(
                    f"Error handling WebSocket message from {connection_id}: {e}"
                )
                # Continue listening for other messages
                continue

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected during connection: {connection_id}")

    except Exception as e:
        logger.error(f"Unexpected WebSocket error: {e}")

    finally:
        # Cleanup connection
        if connection_id:
            websocket_manager.disconnect(connection_id)
            logger.info(f"WebSocket connection cleaned up: {connection_id}")
