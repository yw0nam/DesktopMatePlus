"""APScheduler-based schedule manager for time-triggered proactive talks."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from src.services.proactive_service.config import ProactiveConfig

if TYPE_CHECKING:
    from src.services.websocket_service.manager.connection import ConnectionState


class ScheduleManager:
    def __init__(
        self,
        config: ProactiveConfig,
        trigger_fn: Callable[..., Any],
        get_connections_fn: Callable[[], dict[UUID, ConnectionState]],
    ):
        self._config = config
        self._trigger = trigger_fn
        self._get_connections = get_connections_fn
        self._scheduler = AsyncIOScheduler()

    async def start(self) -> None:
        for entry in self._config.schedules:
            if not entry.enabled:
                logger.info(f"Schedule '{entry.id}' is disabled, skipping")
                continue
            try:
                trigger = CronTrigger.from_crontab(entry.cron)
                self._scheduler.add_job(
                    self._on_schedule_fire,
                    trigger=trigger,
                    id=f"proactive_{entry.id}",
                    kwargs={"schedule_id": entry.id, "prompt_key": entry.prompt_key},
                    replace_existing=True,
                )
            except Exception:
                logger.exception(f"Failed to register schedule '{entry.id}'")
        self._scheduler.start()

    async def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def is_running(self) -> bool:
        return self._scheduler.running

    async def _on_schedule_fire(self, schedule_id: str, prompt_key: str) -> None:
        connections = self._get_connections()
        active = {
            cid: c
            for cid, c in connections.items()
            if c.is_authenticated and not c.is_closing
        }
        if not active:
            logger.info(f"Schedule '{schedule_id}' fired but no active connections")
            return
        for connection_id in active:
            await self._trigger(
                connection_id=connection_id,
                trigger_type="scheduled",
                prompt_key=prompt_key,
            )
