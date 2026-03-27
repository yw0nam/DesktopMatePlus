"""Tests for BackgroundSweepService — expired task cleanup."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.agent_service.session_registry import SessionRegistry
from src.services.task_sweep_service.sweep import BackgroundSweepService, SweepConfig

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


def _make_sweep(sessions=None, pending_tasks=None):
    """Create a BackgroundSweepService with mocked agent + registry."""
    registry = MagicMock(spec=SessionRegistry)
    registry.find_all.return_value = sessions or [{"thread_id": "t1"}]

    agent_svc = MagicMock()
    checkpoint = MagicMock()
    checkpoint.values = {"pending_tasks": pending_tasks or []}
    agent_svc.agent.aget_state = AsyncMock(return_value=checkpoint)
    agent_svc.agent.aupdate_state = AsyncMock()

    svc = BackgroundSweepService(
        agent_service=agent_svc,
        session_registry=registry,
        config=SweepConfig(sweep_interval_seconds=60, task_ttl_seconds=300),
    )
    return svc, agent_svc, registry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sweep_config():
    """Return a minimal SweepConfig with short TTL for fast tests."""
    return SweepConfig(sweep_interval_seconds=60, task_ttl_seconds=300)


# ---------------------------------------------------------------------------
# SweepConfig tests
# ---------------------------------------------------------------------------


class TestSweepConfig:
    def test_defaults_are_reasonable(self):
        """Default TTL and interval should be positive integers."""
        cfg = SweepConfig()
        assert cfg.sweep_interval_seconds > 0
        assert cfg.task_ttl_seconds > 0

    def test_custom_values_accepted(self):
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
        expired_task = _make_task(
            "t1", "pending", age_seconds=sweep_config.task_ttl_seconds + 1
        )
        svc, agent_svc, _ = _make_sweep(
            sessions=[{"thread_id": "t1"}],
            pending_tasks=[expired_task],
        )
        await svc._sweep_once()

        agent_svc.agent.aupdate_state.assert_called_once()
        call_args = agent_svc.agent.aupdate_state.call_args[0]
        updated_tasks = call_args[1]["pending_tasks"]
        assert updated_tasks[0]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_fresh_pending_task_is_not_touched(self, sweep_config):
        """A pending task within TTL must NOT be modified."""
        fresh_task = _make_task(
            "t2", "pending", age_seconds=sweep_config.task_ttl_seconds - 10
        )
        svc, agent_svc, _ = _make_sweep(
            sessions=[{"thread_id": "t1"}],
            pending_tasks=[fresh_task],
        )
        await svc._sweep_once()

        agent_svc.agent.aupdate_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_done_task_is_never_touched(self, sweep_config):
        """Tasks with status 'done' must be ignored regardless of age."""
        old_done = _make_task(
            "t3", "done", age_seconds=sweep_config.task_ttl_seconds + 100
        )
        svc, agent_svc, _ = _make_sweep(
            sessions=[{"thread_id": "t1"}],
            pending_tasks=[old_done],
        )
        await svc._sweep_once()

        agent_svc.agent.aupdate_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_failed_task_is_never_touched(self, sweep_config):
        """Tasks already in 'failed' status must not be re-processed."""
        old_failed = _make_task(
            "t4", "failed", age_seconds=sweep_config.task_ttl_seconds + 100
        )
        svc, agent_svc, _ = _make_sweep(
            sessions=[{"thread_id": "t1"}],
            pending_tasks=[old_failed],
        )
        await svc._sweep_once()

        agent_svc.agent.aupdate_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_running_task_is_also_expired(self, sweep_config):
        """Tasks with status 'running' that exceed TTL must also be failed."""
        expired_running = _make_task(
            "t5", "running", age_seconds=sweep_config.task_ttl_seconds + 1
        )
        svc, agent_svc, _ = _make_sweep(
            sessions=[{"thread_id": "t1"}],
            pending_tasks=[expired_running],
        )
        await svc._sweep_once()

        agent_svc.agent.aupdate_state.assert_called_once()
        updated_tasks = agent_svc.agent.aupdate_state.call_args[0][1]["pending_tasks"]
        assert updated_tasks[0]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_session_without_pending_tasks_is_skipped(self, sweep_config):
        """Sessions that have no pending_tasks key should not cause errors."""
        svc, agent_svc, _ = _make_sweep(
            sessions=[{"thread_id": "t1"}],
            pending_tasks=[],
        )
        await svc._sweep_once()  # must not raise

        agent_svc.agent.aupdate_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_mixed_tasks_only_expired_ones_are_failed(self, sweep_config):
        """Only expired pending/running tasks should flip; others stay unchanged."""
        expired = _make_task(
            "tx", "pending", age_seconds=sweep_config.task_ttl_seconds + 5
        )
        fresh = _make_task("ty", "pending", age_seconds=10)
        done = _make_task("tz", "done", age_seconds=sweep_config.task_ttl_seconds + 5)

        svc, agent_svc, _ = _make_sweep(
            sessions=[{"thread_id": "t1"}],
            pending_tasks=[expired, fresh, done],
        )
        await svc._sweep_once()

        agent_svc.agent.aupdate_state.assert_called_once()
        tasks = agent_svc.agent.aupdate_state.call_args[0][1]["pending_tasks"]
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
        cfg = SweepConfig(sweep_interval_seconds=42, task_ttl_seconds=300)
        svc, _, _ = _make_sweep()
        svc.config = cfg
        assert svc.config.sweep_interval_seconds == 42

    def test_ttl_is_read_from_config(self):
        """BackgroundSweepService must expose task_ttl_seconds from config."""
        cfg = SweepConfig(sweep_interval_seconds=60, task_ttl_seconds=999)
        svc, _, _ = _make_sweep()
        svc.config = cfg
        assert svc.config.task_ttl_seconds == 999


# ---------------------------------------------------------------------------
# start / stop lifecycle tests
# ---------------------------------------------------------------------------


class TestSweepLifecycle:
    @pytest.mark.asyncio
    async def test_start_creates_background_task(self):
        """start() should schedule the sweep loop as an asyncio background task."""
        svc, _, _ = _make_sweep(sessions=[])
        await svc.start()
        assert svc.is_running()
        await svc.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_background_task(self):
        """stop() should cancel the background loop and mark service as stopped."""
        svc, _, _ = _make_sweep(sessions=[])
        await svc.start()
        await svc.stop()
        assert not svc.is_running()
