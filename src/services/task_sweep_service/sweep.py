"""Background sweep — marks expired delegated tasks as failed."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

from loguru import logger
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from src.services.agent_service.service import AgentService
    from src.services.agent_service.session_registry import SessionRegistry
    from src.services.channel_service.slack_service import SlackService

_EXPIRABLE_STATUSES = frozenset({"pending", "running"})


class SweepConfig(BaseModel):
    sweep_interval_seconds: int = Field(default=60, ge=1)
    task_ttl_seconds: int = Field(default=300, ge=1)


class BackgroundSweepService:
    def __init__(
        self,
        agent_service: "AgentService",
        session_registry: "SessionRegistry",
        config: SweepConfig,
        slack_service_fn: Callable[[], "SlackService | None"] | None = None,
    ) -> None:
        self._agent = agent_service
        self._registry = session_registry
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
        try:
            await self._task
        except asyncio.CancelledError:
            pass
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
        now = datetime.now(timezone.utc)
        ttl = self.config.task_ttl_seconds

        try:
            sessions = self._registry.find_all()
        except Exception:
            logger.exception("BackgroundSweepService: failed to list sessions")
            return

        for session in sessions:
            thread_id = session.get("thread_id", "")
            if not thread_id:
                continue
            config = {"configurable": {"thread_id": thread_id}}

            try:
                state = (await self._agent.agent.aget_state(config)).values
            except Exception:
                logger.exception(
                    f"BackgroundSweepService: aget_state failed for {thread_id}"
                )
                continue

            pending: list[dict] = list(state.get("pending_tasks", []))
            if not pending:
                continue

            updated = False
            for task in pending:
                if task.get("status") not in _EXPIRABLE_STATUSES:
                    continue
                raw = task.get("created_at", "")
                if not raw:
                    continue
                try:
                    created_at = datetime.fromisoformat(raw)
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
                if (now - created_at).total_seconds() > ttl:
                    logger.info(
                        f"Expiring task {task.get('task_id')} for thread {thread_id}"
                    )
                    task["status"] = "failed"
                    updated = True

            if not updated:
                continue

            try:
                await self._agent.agent.aupdate_state(
                    config, {"pending_tasks": pending}
                )
            except Exception:
                logger.exception(
                    f"BackgroundSweepService: aupdate_state failed for {thread_id}"
                )
                continue

            if not self._slack_service_fn:
                continue
            for task in pending:
                if task["status"] != "failed":
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
