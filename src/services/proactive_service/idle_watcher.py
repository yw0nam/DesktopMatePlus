"""Idle connection watcher — triggers proactive talk after inactivity."""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from uuid import UUID

from loguru import logger

from src.services.proactive_service.config import ProactiveConfig

if TYPE_CHECKING:
    from src.services.websocket_service.manager.connection import ConnectionState


class IdleWatcher:
    """Periodically scans connections for idle users."""

    def __init__(
        self,
        config: ProactiveConfig,
        get_connections_fn: Callable[[], dict[UUID, ConnectionState]],
        trigger_fn: Callable[..., Any],
        persona_overrides: dict[str, int] | None = None,
        get_persona_fn: Callable[[UUID], str] | None = None,
    ):
        self._config = config
        self._get_connections = get_connections_fn
        self._trigger = trigger_fn
        self._persona_overrides = persona_overrides or {}
        self._get_persona_fn = get_persona_fn
        self._task: asyncio.Task | None = None
        self._triggered_connections: set[UUID] = set()

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop(), name="idle_watcher_loop")

    async def stop(self) -> None:
        if self._task is None or self._task.done():
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task

    async def _loop(self) -> None:
        while True:
            try:
                await self.scan_once(get_persona_fn=self._get_persona_fn)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("IdleWatcher: unhandled error during scan")
            await asyncio.sleep(self._config.watcher_interval_seconds)

    async def scan_once(
        self,
        get_persona_fn: Callable[[UUID], str] | None = None,
    ) -> None:
        """Scan all connections and trigger proactive talk for idle ones."""
        now = time.time()
        connections = self._get_connections()

        self._triggered_connections &= connections.keys()

        for connection_id, conn in list(connections.items()):
            if not conn.is_authenticated or conn.is_closing:
                continue
            mp = conn.message_processor
            if not mp or mp._current_turn_id is not None:
                continue

            timeout = self._config.idle_timeout_seconds
            effective_fn = get_persona_fn or self._get_persona_fn
            if effective_fn is not None:
                persona = effective_fn(connection_id)
                if persona in self._persona_overrides:
                    timeout = self._persona_overrides[persona]

            idle_seconds = now - conn.last_user_message_at
            if idle_seconds < timeout:
                self._triggered_connections.discard(connection_id)
                continue

            if connection_id in self._triggered_connections:
                continue

            self._triggered_connections.add(connection_id)
            await self._trigger(
                connection_id=connection_id,
                trigger_type="idle",
                idle_seconds=int(idle_seconds),
            )

    def reset_connection(self, connection_id: UUID) -> None:
        self._triggered_connections.discard(connection_id)
