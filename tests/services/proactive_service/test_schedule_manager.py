"""Tests for ScheduleManager (APScheduler wrapper)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.services.proactive_service.config import ProactiveConfig, ScheduleEntry
from src.services.proactive_service.schedule_manager import ScheduleManager


def _make_config(schedules=None):
    return ProactiveConfig(schedules=schedules or [], watcher_interval_seconds=30)


class TestScheduleManager:
    async def test_start_registers_jobs(self):
        config = _make_config(
            schedules=[
                ScheduleEntry(id="morning", cron="0 9 * * *", prompt_key="morning"),
            ]
        )
        trigger_fn = AsyncMock()
        get_connections_fn = MagicMock(return_value={})
        mgr = ScheduleManager(
            config=config, trigger_fn=trigger_fn, get_connections_fn=get_connections_fn
        )
        await mgr.start()
        assert mgr.is_running()
        await mgr.stop()

    async def test_disabled_schedule_is_skipped(self):
        config = _make_config(
            schedules=[
                ScheduleEntry(
                    id="disabled", cron="0 9 * * *", prompt_key="x", enabled=False
                ),
            ]
        )
        trigger_fn = AsyncMock()
        get_connections_fn = MagicMock(return_value={})
        mgr = ScheduleManager(
            config=config, trigger_fn=trigger_fn, get_connections_fn=get_connections_fn
        )
        await mgr.start()
        jobs = mgr._scheduler.get_jobs()
        assert len(jobs) == 0
        await mgr.stop()

    async def test_trigger_broadcasts_to_connections(self):
        conn = MagicMock()
        conn.connection_id = uuid4()
        conn.is_authenticated = True
        conn.is_closing = False
        trigger_fn = AsyncMock()
        config = _make_config()
        get_connections_fn = MagicMock(return_value={conn.connection_id: conn})
        mgr = ScheduleManager(
            config=config, trigger_fn=trigger_fn, get_connections_fn=get_connections_fn
        )
        await mgr._on_schedule_fire(schedule_id="morning", prompt_key="morning")
        trigger_fn.assert_called_once_with(
            connection_id=conn.connection_id,
            trigger_type="scheduled",
            prompt_key="morning",
        )

    async def test_no_connections_is_noop(self):
        trigger_fn = AsyncMock()
        config = _make_config()
        get_connections_fn = MagicMock(return_value={})
        mgr = ScheduleManager(
            config=config, trigger_fn=trigger_fn, get_connections_fn=get_connections_fn
        )
        await mgr._on_schedule_fire(schedule_id="morning", prompt_key="morning")
        trigger_fn.assert_not_called()
