"""Tests for BackgroundSweepService — expired task cleanup."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.services.stm_service.service import STMService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(
    task_id: str,
    status: str,
    age_seconds: float,
) -> dict:
    """Build a synthetic task-record matching the DelegateTaskTool schema."""
    created_at = (
        datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    ).isoformat()
    return {
        "task_id": task_id,
        "description": f"task-{task_id}",
        "status": status,
        "created_at": created_at,
    }


def _mock_stm(sessions: list[dict]) -> MagicMock:
    """Create a mock STMService that owns a set of sessions."""
    service = MagicMock(spec=STMService)

    # list_sessions returns all sessions passed in
    service.list_all_sessions.return_value = sessions

    # get_session_metadata: look up by session_id key in each session dict
    def _get_meta(session_id: str) -> dict:
        for s in sessions:
            if s.get("session_id") == session_id:
                return s.get("metadata", {})
        return {}

    service.get_session_metadata.side_effect = _get_meta
    service.update_session_metadata.return_value = True
    return service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sweep_config():
    """Return a minimal SweepConfig with short TTL for fast tests."""
    from src.services.task_sweep_service.sweep import SweepConfig

    return SweepConfig(sweep_interval_seconds=60, task_ttl_seconds=300)


@pytest.fixture
def sweep_service(sweep_config):
    """Return a BackgroundSweepService instance with a mock STMService."""
    from src.services.task_sweep_service.sweep import BackgroundSweepService

    mock_stm = MagicMock(spec=STMService)
    mock_stm.list_all_sessions.return_value = []
    return BackgroundSweepService(stm_service=mock_stm, config=sweep_config)


# ---------------------------------------------------------------------------
# SweepConfig tests
# ---------------------------------------------------------------------------


class TestSweepConfig:
    def test_defaults_are_reasonable(self):
        """Default TTL and interval should be positive integers."""
        from src.services.task_sweep_service.sweep import SweepConfig

        cfg = SweepConfig()
        assert cfg.sweep_interval_seconds > 0
        assert cfg.task_ttl_seconds > 0

    def test_custom_values_accepted(self):
        from src.services.task_sweep_service.sweep import SweepConfig

        cfg = SweepConfig(sweep_interval_seconds=10, task_ttl_seconds=120)
        assert cfg.sweep_interval_seconds == 10
        assert cfg.task_ttl_seconds == 120


# ---------------------------------------------------------------------------
# _sweep_once unit tests
# ---------------------------------------------------------------------------


class TestSweepOnce:
    @pytest.mark.asyncio
    async def test_expired_pending_task_is_marked_failed(self, sweep_config):
        """A pending task older than TTL must be flipped to 'failed'."""
        from src.services.task_sweep_service.sweep import BackgroundSweepService

        expired_task = _make_task(
            "t1", "pending", age_seconds=sweep_config.task_ttl_seconds + 1
        )
        session = {
            "session_id": "sess-1",
            "metadata": {"pending_tasks": [expired_task]},
        }
        stm = _mock_stm([session])

        svc = BackgroundSweepService(stm_service=stm, config=sweep_config)
        await svc._sweep_once()

        stm.update_session_metadata.assert_called_once()
        args = stm.update_session_metadata.call_args[0]
        assert args[0] == "sess-1"
        updated_tasks = args[1]["pending_tasks"]
        assert updated_tasks[0]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_fresh_pending_task_is_not_touched(self, sweep_config):
        """A pending task within TTL must NOT be modified."""
        from src.services.task_sweep_service.sweep import BackgroundSweepService

        fresh_task = _make_task(
            "t2", "pending", age_seconds=sweep_config.task_ttl_seconds - 10
        )
        session = {
            "session_id": "sess-2",
            "metadata": {"pending_tasks": [fresh_task]},
        }
        stm = _mock_stm([session])

        svc = BackgroundSweepService(stm_service=stm, config=sweep_config)
        await svc._sweep_once()

        stm.update_session_metadata.assert_not_called()

    @pytest.mark.asyncio
    async def test_done_task_is_never_touched(self, sweep_config):
        """Tasks with status 'done' must be ignored regardless of age."""
        from src.services.task_sweep_service.sweep import BackgroundSweepService

        old_done = _make_task(
            "t3", "done", age_seconds=sweep_config.task_ttl_seconds + 100
        )
        session = {
            "session_id": "sess-3",
            "metadata": {"pending_tasks": [old_done]},
        }
        stm = _mock_stm([session])

        svc = BackgroundSweepService(stm_service=stm, config=sweep_config)
        await svc._sweep_once()

        stm.update_session_metadata.assert_not_called()

    @pytest.mark.asyncio
    async def test_failed_task_is_never_touched(self, sweep_config):
        """Tasks already in 'failed' status must not be re-processed."""
        from src.services.task_sweep_service.sweep import BackgroundSweepService

        old_failed = _make_task(
            "t4", "failed", age_seconds=sweep_config.task_ttl_seconds + 100
        )
        session = {
            "session_id": "sess-4",
            "metadata": {"pending_tasks": [old_failed]},
        }
        stm = _mock_stm([session])

        svc = BackgroundSweepService(stm_service=stm, config=sweep_config)
        await svc._sweep_once()

        stm.update_session_metadata.assert_not_called()

    @pytest.mark.asyncio
    async def test_running_task_is_also_expired(self, sweep_config):
        """Tasks with status 'running' that exceed TTL must also be failed."""
        from src.services.task_sweep_service.sweep import BackgroundSweepService

        expired_running = _make_task(
            "t5", "running", age_seconds=sweep_config.task_ttl_seconds + 1
        )
        session = {
            "session_id": "sess-5",
            "metadata": {"pending_tasks": [expired_running]},
        }
        stm = _mock_stm([session])

        svc = BackgroundSweepService(stm_service=stm, config=sweep_config)
        await svc._sweep_once()

        stm.update_session_metadata.assert_called_once()
        updated_tasks = stm.update_session_metadata.call_args[0][1]["pending_tasks"]
        assert updated_tasks[0]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_session_without_pending_tasks_is_skipped(self, sweep_config):
        """Sessions that have no pending_tasks key should not cause errors."""
        from src.services.task_sweep_service.sweep import BackgroundSweepService

        session = {"session_id": "sess-6", "metadata": {}}
        stm = _mock_stm([session])

        svc = BackgroundSweepService(stm_service=stm, config=sweep_config)
        await svc._sweep_once()  # must not raise

        stm.update_session_metadata.assert_not_called()

    @pytest.mark.asyncio
    async def test_mixed_tasks_only_expired_ones_are_failed(self, sweep_config):
        """Only expired pending/running tasks should flip; others stay unchanged."""
        from src.services.task_sweep_service.sweep import BackgroundSweepService

        expired = _make_task(
            "tx", "pending", age_seconds=sweep_config.task_ttl_seconds + 5
        )
        fresh = _make_task("ty", "pending", age_seconds=10)
        done = _make_task("tz", "done", age_seconds=sweep_config.task_ttl_seconds + 5)

        session = {
            "session_id": "sess-7",
            "metadata": {"pending_tasks": [expired, fresh, done]},
        }
        stm = _mock_stm([session])

        svc = BackgroundSweepService(stm_service=stm, config=sweep_config)
        await svc._sweep_once()

        stm.update_session_metadata.assert_called_once()
        tasks = stm.update_session_metadata.call_args[0][1]["pending_tasks"]
        status_map = {t["task_id"]: t["status"] for t in tasks}
        assert status_map["tx"] == "failed"
        assert status_map["ty"] == "pending"
        assert status_map["tz"] == "done"


# ---------------------------------------------------------------------------
# Configurable interval test
# ---------------------------------------------------------------------------


class TestSweepInterval:
    def test_interval_is_read_from_config(self):
        """BackgroundSweepService must expose sweep_interval_seconds from config."""
        from src.services.task_sweep_service.sweep import (
            BackgroundSweepService,
            SweepConfig,
        )

        cfg = SweepConfig(sweep_interval_seconds=42, task_ttl_seconds=300)
        stm = MagicMock(spec=STMService)
        stm.list_all_sessions.return_value = []
        svc = BackgroundSweepService(stm_service=stm, config=cfg)
        assert svc.config.sweep_interval_seconds == 42

    def test_ttl_is_read_from_config(self):
        """BackgroundSweepService must expose task_ttl_seconds from config."""
        from src.services.task_sweep_service.sweep import (
            BackgroundSweepService,
            SweepConfig,
        )

        cfg = SweepConfig(sweep_interval_seconds=60, task_ttl_seconds=999)
        stm = MagicMock(spec=STMService)
        stm.list_all_sessions.return_value = []
        svc = BackgroundSweepService(stm_service=stm, config=cfg)
        assert svc.config.task_ttl_seconds == 999


# ---------------------------------------------------------------------------
# start / stop lifecycle tests
# ---------------------------------------------------------------------------


class TestSweepLifecycle:
    @pytest.mark.asyncio
    async def test_start_creates_background_task(self):
        """start() should schedule the sweep loop as an asyncio background task."""
        from src.services.task_sweep_service.sweep import (
            BackgroundSweepService,
            SweepConfig,
        )

        cfg = SweepConfig(sweep_interval_seconds=60, task_ttl_seconds=300)
        stm = MagicMock(spec=STMService)
        stm.list_all_sessions.return_value = []
        svc = BackgroundSweepService(stm_service=stm, config=cfg)

        await svc.start()
        assert svc.is_running()
        await svc.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_background_task(self):
        """stop() should cancel the background loop and mark service as stopped."""
        from src.services.task_sweep_service.sweep import (
            BackgroundSweepService,
            SweepConfig,
        )

        cfg = SweepConfig(sweep_interval_seconds=60, task_ttl_seconds=300)
        stm = MagicMock(spec=STMService)
        stm.list_all_sessions.return_value = []
        svc = BackgroundSweepService(stm_service=stm, config=cfg)

        await svc.start()
        await svc.stop()
        assert not svc.is_running()
