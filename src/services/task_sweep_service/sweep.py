"""Background sweep — marks expired delegated tasks as failed."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from typing import TYPE_CHECKING

from loguru import logger
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from src.services.channel_service.slack_service import SlackService
    from src.services.pending_task_repository import PendingTaskRepository

_EXPIRABLE_STATUSES = frozenset({"pending", "running"})


class SweepConfig(BaseModel):
    sweep_interval_seconds: int = Field(default=60, ge=1)
    task_ttl_seconds: int = Field(default=300, ge=1)


class BackgroundSweepService:
    def __init__(
        self,
        pending_task_repo: PendingTaskRepository,
        config: SweepConfig,
        slack_service_fn: Callable[[], SlackService | None] | None = None,
    ) -> None:
        self._repo = pending_task_repo
        self.config = config
        self._slack_service_fn = slack_service_fn
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop(), name="task_sweep_loop")
        logger.info(
            f"BackgroundSweepService started "
            f"(interval={self.config.sweep_interval_seconds}s, ttl={self.config.task_ttl_seconds}s)"
        )

    async def stop(self) -> None:
        if self._task is None or self._task.done():
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        logger.info("BackgroundSweepService stopped")

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def _loop(self) -> None:
        while True:
            try:
                await self._sweep_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("BackgroundSweepService: unhandled error during sweep")
            await asyncio.sleep(self.config.sweep_interval_seconds)

    async def _sweep_once(self) -> None:
        try:
            expired = await asyncio.to_thread(
                self._repo.find_expirable,
                _EXPIRABLE_STATUSES,
                self.config.task_ttl_seconds,
            )
        except Exception:
            logger.exception("BackgroundSweepService: failed to query expirable tasks")
            return

        for task in expired:
            task_id = task.get("task_id", "")
            try:
                await asyncio.to_thread(self._repo.update_status, task_id, "failed")
                logger.info(f"Expired task {task_id}")
            except Exception:
                logger.exception(f"BackgroundSweepService: failed to expire {task_id}")
                continue

            if not self._slack_service_fn:
                continue
            rc = task.get("reply_channel")
            if rc and rc.get("provider") == "slack":
                slack = self._slack_service_fn()
                if slack:
                    try:
                        await slack.send_message(
                            rc["channel_id"],
                            "태스크가 시간 초과됐어. 다시 시도해줘",
                        )
                    except Exception:
                        logger.exception(
                            "Failed to send sweep timeout Slack notification"
                        )
