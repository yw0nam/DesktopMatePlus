"""Heartbeat monitoring for WebSocket connections."""

import asyncio
import time

from loguru import logger

from src.models.websocket import PingMessage

from .connection import ConnectionState


class HeartbeatMonitor:
    """Monitors WebSocket connections with ping/pong heartbeats."""

    def __init__(
        self,
        ping_interval: int,
        pong_timeout: int,
        get_connection_fn,
        send_message_fn,
        disconnect_fn,
    ):
        """Initialize heartbeat monitor.

        Args:
            ping_interval: Interval between ping messages in seconds.
            pong_timeout: Timeout for pong response in seconds.
            get_connection_fn: Function to check if connection exists.
            send_message_fn: Function to send messages to connections.
            disconnect_fn: Function to disconnect connections.
        """
        self.ping_interval = ping_interval
        self.pong_timeout = pong_timeout
        self.get_connection = get_connection_fn
        self.send_message = send_message_fn
        self.disconnect = disconnect_fn

    async def heartbeat_loop(self, connection_state: ConnectionState):
        """Heartbeat loop for a connection.

        Args:
            connection_state: Connection state to monitor.
        """
        connection_id = connection_state.connection_id

        try:
            while self.get_connection(connection_id) is not None:
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
