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
        close_connection_fn,
    ):
        """Initialize heartbeat monitor.

        Args:
            ping_interval: Interval between ping messages in seconds.
            pong_timeout: Timeout for pong response in seconds.
            get_connection_fn: Function to check if connection exists.
            send_message_fn: Function to send messages to connections.
            close_connection_fn: Function to close connections with code and reason.
        """
        self.ping_interval = ping_interval
        self.pong_timeout = pong_timeout
        self.get_connection = get_connection_fn
        self.send_message = send_message_fn
        self.close_connection = close_connection_fn

    async def heartbeat_loop(self, connection_state: ConnectionState):
        """Heartbeat loop for a connection.

        Args:
            connection_state: Connection state to monitor.
        """
        connection_id = connection_state.connection_id
        first_ping = True

        try:
            while self.get_connection(connection_id) is not None:
                # Check if connection is closing
                if connection_state.is_closing:
                    logger.debug(
                        f"Connection {connection_id} is closing, stopping heartbeat"
                    )
                    break

                # Send ping
                ping_message = PingMessage()
                await self.send_message(connection_id, ping_message)
                connection_state.last_ping_time = time.time()
                logger.debug(f"Sent ping to {connection_id}")

                # Wait for ping interval
                await asyncio.sleep(self.ping_interval)

                # Skip pong check on first ping (client hasn't had a chance to respond yet)
                if first_ping:
                    first_ping = False
                    continue

                # Check if we received pong within timeout
                # We expect pong within (ping_interval + pong_timeout) from last pong
                if connection_state.last_pong_time is not None:
                    time_since_last_pong = time.time() - connection_state.last_pong_time
                    max_allowed_time = self.ping_interval + self.pong_timeout

                    if time_since_last_pong > max_allowed_time:
                        logger.warning(
                            f"Connection {connection_id} failed to respond to ping "
                            f"(last pong: {time_since_last_pong:.1f}s ago, max: {max_allowed_time}s)"
                        )
                        # Close connection due to timeout using standardized method
                        await self.close_connection(
                            connection_id=connection_id,
                            code=4000,
                            reason="Ping timeout",
                            notify_client=True,
                        )
                        break

        except asyncio.CancelledError:
            logger.debug(f"Heartbeat loop cancelled for {connection_id}")
            raise  # Re-raise to allow proper task cancellation
        except Exception as e:
            logger.error(f"Error in heartbeat loop for {connection_id}: {e}")
            # Close connection due to unexpected error
            await self.close_connection(
                connection_id=connection_id,
                code=1011,
                reason="Internal heartbeat error",
                notify_client=False,
            )
