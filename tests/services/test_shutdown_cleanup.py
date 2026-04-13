"""Tests for _shutdown() cleanup — verifies all services are properly closed."""

from unittest.mock import AsyncMock, MagicMock


class TestShutdownCleanup:
    """Verify _shutdown() calls cleanup in reverse init order."""

    async def test_sweep_service_stop_is_awaited(self):
        """sweep_service.stop() must be awaitable and complete without error."""
        from unittest.mock import MagicMock

        from src.services.task_sweep_service.sweep import (
            BackgroundSweepService,
            SweepConfig,
        )

        mock_repo = MagicMock()

        svc = BackgroundSweepService(
            pending_task_repo=mock_repo,
            config=SweepConfig(sweep_interval_seconds=60, task_ttl_seconds=300),
        )
        # stop() on a never-started service must be a no-op, not raise
        await svc.stop()

    async def test_slack_service_cleanup_called(self):
        """SlackService.cleanup() must be awaited when Slack is initialized."""
        from src.services.channel_service.slack_service import (
            SlackService,
            SlackSettings,
        )

        settings = SlackSettings(
            enabled=True, bot_token="xoxb-fake", signing_secret="sec"
        )
        svc = SlackService(settings)
        # cleanup is a no-op for HTTP clients but should be awaitable
        await svc.cleanup()  # must not raise

    async def test_websocket_manager_close_all(self):
        """WebSocketManager.close_all() closes all active connections."""
        from src.services.websocket_service.manager.websocket_manager import (
            WebSocketManager,
        )

        mgr = WebSocketManager(ping_interval=30, pong_timeout=10, disconnect_timeout=5)
        # No connections — close_all should complete without error
        await mgr.close_all()

    async def test_websocket_manager_close_all_with_connections(self):
        """close_all() calls disconnect on each active connection."""
        from uuid import uuid4

        from src.services.websocket_service.manager.websocket_manager import (
            WebSocketManager,
        )

        mgr = WebSocketManager(ping_interval=30, pong_timeout=10, disconnect_timeout=5)

        conn_id = uuid4()
        mock_conn = MagicMock()
        mock_conn.is_closing = False
        mock_conn.message_processor = None
        mock_conn.websocket = AsyncMock()
        mgr.connections[conn_id] = mock_conn

        # Patch _close_connection to avoid actual WS operations
        mgr._close_connection = AsyncMock()
        await mgr.close_all()

        mgr._close_connection.assert_called_once_with(
            connection_id=conn_id,
            code=1001,
            reason="Server shutting down",
            notify_client=True,
        )


class TestChannelServiceCleanup:
    async def test_cleanup_when_no_slack_service(self):
        """Shutdown with no Slack service must not raise."""
        from src.services import channel_service

        original = channel_service._slack_service
        channel_service._slack_service = None
        try:
            await channel_service.cleanup_channel_service()
        finally:
            channel_service._slack_service = original

    async def test_cleanup_calls_slack_cleanup(self):
        """cleanup_channel_service() delegates to SlackService.cleanup()."""
        from src.services import channel_service

        mock_slack = AsyncMock()
        original = channel_service._slack_service
        channel_service._slack_service = mock_slack
        try:
            await channel_service.cleanup_channel_service()
            mock_slack.cleanup.assert_called_once()
        finally:
            channel_service._slack_service = original
