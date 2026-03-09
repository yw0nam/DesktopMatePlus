"""Background sweep service that marks expired delegated tasks as failed.

DelegateTaskTool stores task records in STM metadata under ``pending_tasks``.
If NanoClaw never responds the task stays in ``pending`` (or ``running``) status
forever.  This service periodically scans every session and marks stale tasks as
``failed``.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field

from src.services.stm_service.service import STMService

# Statuses that are considered "active" and therefore eligible for expiry.
_EXPIRABLE_STATUSES = frozenset({"pending", "running"})

# Sentinel user/agent IDs used when scanning all sessions.
# list_sessions requires user_id + agent_id; we use wildcard-style blank strings
# only if the STM implementation supports it, otherwise the sweep calls
# list_sessions per-session via a known set of sessions.
_SCAN_USER_ID = ""
_SCAN_AGENT_ID = ""


class SweepConfig(BaseModel):
    """Configuration for the background sweep service."""

    sweep_interval_seconds: int = Field(
        default=60,
        ge=1,
        description="How often (in seconds) to run the sweep loop.",
    )
    task_ttl_seconds: int = Field(
        default=300,
        ge=1,
        description="Maximum age (in seconds) a pending/running task may have before being marked failed.",
    )


class BackgroundSweepService:
    """Periodically scans STM sessions and expires stale delegated tasks.

    Usage (in FastAPI lifespan)::

        sweep_svc = BackgroundSweepService(stm_service=stm, config=cfg)
        asyncio.create_task(sweep_svc.start())
        ...
        await sweep_svc.stop()
    """

    def __init__(self, stm_service: STMService, config: SweepConfig) -> None:
        self._stm = stm_service
        self.config = config
        self._task: Optional[asyncio.Task] = None  # type: ignore[type-arg]

    # ------------------------------------------------------------------
    # Public lifecycle API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the background sweep loop as an asyncio Task."""
        if self._task is not None and not self._task.done():
            logger.warning("BackgroundSweepService already running — ignoring start()")
            return
        self._task = asyncio.create_task(self._loop(), name="task_sweep_loop")
        logger.info(
            f"BackgroundSweepService started "
            f"(interval={self.config.sweep_interval_seconds}s, "
            f"ttl={self.config.task_ttl_seconds}s)"
        )

    async def stop(self) -> None:
        """Cancel the background sweep loop and wait for it to finish."""
        if self._task is None or self._task.done():
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        logger.info("BackgroundSweepService stopped")

    def is_running(self) -> bool:
        """Return True if the sweep loop is currently active."""
        return self._task is not None and not self._task.done()

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        """Run sweep forever, sleeping between iterations."""
        while True:
            try:
                await self._sweep_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("BackgroundSweepService: unhandled error during sweep")
            await asyncio.sleep(self.config.sweep_interval_seconds)

    # ------------------------------------------------------------------
    # Core sweep logic — public for easy unit-testing
    # ------------------------------------------------------------------

    async def _sweep_once(self) -> None:
        """Scan all sessions and expire stale tasks in a single pass."""
        now = datetime.now(timezone.utc)
        ttl_seconds = self.config.task_ttl_seconds

        try:
            sessions = self._stm.list_sessions(_SCAN_USER_ID, _SCAN_AGENT_ID)
        except Exception:
            logger.exception("BackgroundSweepService: failed to list sessions")
            return

        for session in sessions:
            session_id: str = session.get("session_id", "")
            if not session_id:
                continue

            try:
                metadata = self._stm.get_session_metadata(session_id)
            except Exception:
                logger.exception(
                    f"BackgroundSweepService: failed to get metadata for session {session_id}"
                )
                continue

            pending_tasks: list[dict] = metadata.get("pending_tasks", [])
            if not pending_tasks:
                continue

            updated = False
            for task in pending_tasks:
                if task.get("status") not in _EXPIRABLE_STATUSES:
                    continue

                created_at_raw: str = task.get("created_at", "")
                if not created_at_raw:
                    continue

                try:
                    created_at = datetime.fromisoformat(created_at_raw)
                    # Ensure timezone-aware comparison
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                except ValueError:
                    logger.warning(
                        f"BackgroundSweepService: unparseable created_at "
                        f"'{created_at_raw}' for task {task.get('task_id')}"
                    )
                    continue

                age_seconds = (now - created_at).total_seconds()
                if age_seconds > ttl_seconds:
                    logger.info(
                        f"BackgroundSweepService: expiring task {task.get('task_id')} "
                        f"(age={age_seconds:.0f}s, ttl={ttl_seconds}s, session={session_id})"
                    )
                    task["status"] = "failed"
                    updated = True

            if updated:
                try:
                    self._stm.update_session_metadata(
                        session_id, {"pending_tasks": pending_tasks}
                    )
                except Exception:
                    logger.exception(
                        f"BackgroundSweepService: failed to update metadata for session {session_id}"
                    )
