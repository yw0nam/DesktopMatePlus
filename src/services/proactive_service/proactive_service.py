"""ProactiveService — orchestrates all proactive talking triggers."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from loguru import logger

from src.services.proactive_service.config import ProactiveConfig
from src.services.proactive_service.idle_watcher import IdleWatcher
from src.services.proactive_service.prompt_loader import PromptLoader
from src.services.proactive_service.schedule_manager import ScheduleManager

if TYPE_CHECKING:
    from src.services.agent_service.service import AgentService
    from src.services.websocket_service.manager.websocket_manager import (
        WebSocketManager,
    )


class ProactiveService:
    """Orchestrates idle watcher, schedule manager, and prompt rendering
    to deliver proactive messages to connected users."""

    def __init__(
        self,
        config: ProactiveConfig,
        ws_manager: WebSocketManager,
        agent_service: AgentService,
        prompts_path: Path | None = None,
        persona_overrides: dict[str, int] | None = None,
    ):
        self._config = config
        self._ws_manager = ws_manager
        self._agent_service = agent_service
        self._prompt_loader = PromptLoader(prompts_path)
        self._persona_overrides = persona_overrides or {}
        self._last_proactive_at: dict[UUID, float] = {}

        self._idle_watcher = IdleWatcher(
            config=config,
            get_connections_fn=lambda: self._ws_manager.connections,
            trigger_fn=self.trigger_proactive,
            persona_overrides=self._persona_overrides,
            get_persona_fn=lambda cid: (
                getattr(self._ws_manager.connections.get(cid), "persona_id", "yuri")
                or "yuri"
            ),
        )
        self._schedule_manager = ScheduleManager(
            config=config,
            trigger_fn=self.trigger_proactive,
            get_connections_fn=lambda: self._ws_manager.connections,
        )

    async def start(self) -> None:
        """Start idle watcher and schedule manager."""
        await self._idle_watcher.start()
        await self._schedule_manager.start()
        logger.info("ProactiveService started")

    async def stop(self) -> None:
        """Stop idle watcher and schedule manager."""
        await self._idle_watcher.stop()
        await self._schedule_manager.stop()
        logger.info("ProactiveService stopped")

    async def trigger_proactive(
        self,
        connection_id: UUID,
        trigger_type: str,
        prompt_key: str | None = None,
        context: str | None = None,
        idle_seconds: int | None = None,
    ) -> dict[str, str]:
        """Execute a proactive trigger for a specific connection.

        Returns {"status": "triggered", "turn_id": "..."} on success,
        or {"status": "skipped", "reason": "..."} when skipped.
        """
        # 1. Connection check
        conn = self._ws_manager.connections.get(connection_id)
        if conn is None or conn.is_closing:
            return {"status": "skipped", "reason": "connection not found"}

        # Prune stale cooldown entries for disconnected connections
        known = set(self._ws_manager.connections.keys())
        if len(self._last_proactive_at) > len(known):
            self._last_proactive_at = {
                k: v for k, v in self._last_proactive_at.items() if k in known
            }

        # 2. Active turn check
        mp = conn.message_processor
        if not mp or mp._current_turn_id is not None:
            return {"status": "skipped", "reason": "active turn in progress"}

        # 3. Idle recheck — only for idle triggers
        now = time.time()
        if trigger_type == "idle":
            timeout = self._persona_overrides.get(
                "default", self._config.idle_timeout_seconds
            )
            if now - conn.last_user_message_at < timeout:
                return {"status": "skipped", "reason": "connection became active"}

        # 4. Cooldown
        last_at = self._last_proactive_at.get(connection_id, 0)
        if now - last_at < self._config.cooldown_seconds:
            remaining = int(self._config.cooldown_seconds - (now - last_at))
            return {
                "status": "skipped",
                "reason": f"cooldown active ({remaining}s remaining)",
            }

        # 5. Render prompt
        effective_key = prompt_key or trigger_type
        current_time = datetime.now().strftime("%H:%M:%S")
        prompt_text = self._prompt_loader.render(
            effective_key,
            idle_seconds=idle_seconds or 0,
            current_time=current_time,
            context=context or "",
        )

        # 6-7. Stream agent response + forward to client WebSocket
        try:
            from langchain_core.messages import HumanMessage

            agent_stream = self._agent_service.stream(
                messages=[HumanMessage(content=prompt_text)],
                session_id=str(connection_id),
                persona_id=conn.persona_id,
                user_id=conn.user_id or "unknown",
                agent_id="proactive",
                is_new_session=False,
            )

            turn_id: str | None = None
            got_stream_end = False
            websocket = conn.websocket
            async for event in agent_stream:
                event["proactive"] = True
                if event.get("type") == "stream_start":
                    turn_id = event.get("turn_id", "")
                elif event.get("type") == "stream_end":
                    got_stream_end = True
                event_json = json.dumps(event, default=str)
                await websocket.send_text(event_json)

            # If the agent errored without emitting stream_end, send a synthetic one
            # so the client is not left waiting indefinitely.
            if not got_stream_end:
                fallback = {
                    "type": "stream_end",
                    "turn_id": turn_id or "",
                    "proactive": True,
                }
                await websocket.send_text(json.dumps(fallback, default=str))

            # 8. Update cooldown timestamp
            self._last_proactive_at[connection_id] = time.time()
            logger.info(
                f"Proactive {trigger_type} triggered for {connection_id} "
                f"(turn_id={turn_id})"
            )
            return {"status": "triggered", "turn_id": turn_id or ""}

        except Exception as exc:
            logger.exception(f"Proactive trigger failed for {connection_id}: {exc}")
            return {"status": "skipped", "reason": f"error: {exc}"}

    def on_user_message(self, connection_id: UUID) -> None:
        """Reset idle tracking when a user sends a message."""
        self._idle_watcher.reset_connection(connection_id)
