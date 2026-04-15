"""Tests for idle watcher and ConnectionState timestamp."""

import time
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.services.proactive_service.config import ProactiveConfig
from src.services.proactive_service.idle_watcher import IdleWatcher
from src.services.websocket_service.manager.connection import ConnectionState


class TestConnectionStateTimestamp:
    def test_last_user_message_at_initialized_to_created_at(self):
        ws = MagicMock()
        conn = ConnectionState(ws, uuid4())
        assert conn.last_user_message_at == conn.created_at

    def test_last_user_message_at_is_updatable(self):
        ws = MagicMock()
        conn = ConnectionState(ws, uuid4())
        now = time.time()
        conn.last_user_message_at = now
        assert conn.last_user_message_at == now


def _make_connection(idle_seconds: float = 400.0):
    conn = MagicMock()
    conn.is_authenticated = True
    conn.is_closing = False
    conn.last_user_message_at = time.time() - idle_seconds
    conn.connection_id = uuid4()
    conn.user_id = "test_user"
    conn.message_processor = MagicMock()
    conn.message_processor._current_turn_id = None
    return conn


class TestIdleWatcher:
    async def test_detects_idle_connection(self):
        conn = _make_connection(idle_seconds=400.0)
        trigger_fn = AsyncMock()
        config = ProactiveConfig(idle_timeout_seconds=300, watcher_interval_seconds=1)
        watcher = IdleWatcher(
            config=config,
            get_connections_fn=lambda: {conn.connection_id: conn},
            trigger_fn=trigger_fn,
        )
        await watcher.scan_once()
        trigger_fn.assert_called_once()

    async def test_skips_active_connection(self):
        conn = _make_connection(idle_seconds=10.0)
        trigger_fn = AsyncMock()
        config = ProactiveConfig(idle_timeout_seconds=300, watcher_interval_seconds=1)
        watcher = IdleWatcher(
            config=config,
            get_connections_fn=lambda: {conn.connection_id: conn},
            trigger_fn=trigger_fn,
        )
        await watcher.scan_once()
        trigger_fn.assert_not_called()

    async def test_skips_unauthenticated_connection(self):
        conn = _make_connection(idle_seconds=400.0)
        conn.is_authenticated = False
        trigger_fn = AsyncMock()
        config = ProactiveConfig(idle_timeout_seconds=300, watcher_interval_seconds=1)
        watcher = IdleWatcher(
            config=config,
            get_connections_fn=lambda: {conn.connection_id: conn},
            trigger_fn=trigger_fn,
        )
        await watcher.scan_once()
        trigger_fn.assert_not_called()

    async def test_skips_closing_connection(self):
        conn = _make_connection(idle_seconds=400.0)
        conn.is_closing = True
        trigger_fn = AsyncMock()
        config = ProactiveConfig(idle_timeout_seconds=300, watcher_interval_seconds=1)
        watcher = IdleWatcher(
            config=config,
            get_connections_fn=lambda: {conn.connection_id: conn},
            trigger_fn=trigger_fn,
        )
        await watcher.scan_once()
        trigger_fn.assert_not_called()

    async def test_skips_connection_with_active_turn(self):
        conn = _make_connection(idle_seconds=400.0)
        conn.message_processor._current_turn_id = "active-turn"
        trigger_fn = AsyncMock()
        config = ProactiveConfig(idle_timeout_seconds=300, watcher_interval_seconds=1)
        watcher = IdleWatcher(
            config=config,
            get_connections_fn=lambda: {conn.connection_id: conn},
            trigger_fn=trigger_fn,
        )
        await watcher.scan_once()
        trigger_fn.assert_not_called()

    async def test_uses_persona_override_timeout(self):
        conn = _make_connection(idle_seconds=200.0)
        trigger_fn = AsyncMock()
        config = ProactiveConfig(idle_timeout_seconds=300, watcher_interval_seconds=1)
        watcher = IdleWatcher(
            config=config,
            get_connections_fn=lambda: {conn.connection_id: conn},
            trigger_fn=trigger_fn,
            persona_overrides={"yuri": 150},
        )
        await watcher.scan_once(get_persona_fn=lambda cid: "yuri")
        trigger_fn.assert_called_once()

    async def test_does_not_retrigger_same_connection(self):
        conn = _make_connection(idle_seconds=400.0)
        trigger_fn = AsyncMock()
        config = ProactiveConfig(idle_timeout_seconds=300, watcher_interval_seconds=1)
        watcher = IdleWatcher(
            config=config,
            get_connections_fn=lambda: {conn.connection_id: conn},
            trigger_fn=trigger_fn,
        )
        await watcher.scan_once()
        await watcher.scan_once()
        trigger_fn.assert_called_once()  # only once despite two scans

    async def test_reset_connection_allows_retrigger(self):
        conn = _make_connection(idle_seconds=400.0)
        trigger_fn = AsyncMock()
        config = ProactiveConfig(idle_timeout_seconds=300, watcher_interval_seconds=1)
        watcher = IdleWatcher(
            config=config,
            get_connections_fn=lambda: {conn.connection_id: conn},
            trigger_fn=trigger_fn,
        )
        await watcher.scan_once()
        watcher.reset_connection(conn.connection_id)
        await watcher.scan_once()
        assert trigger_fn.call_count == 2
