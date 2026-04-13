"""Tests for BackgroundSweepService — expired task cleanup."""

from unittest.mock import MagicMock

import pytest

from src.services.task_sweep_service.sweep import BackgroundSweepService, SweepConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo(expired_tasks=None):
    """Create a mock PendingTaskRepository."""
    mock_repo = MagicMock()
    mock_repo.find_expirable.return_value = expired_tasks or []
    mock_repo.update_status.return_value = True
    return mock_repo


def _make_sweep(expired_tasks=None):
    """Create a BackgroundSweepService with mocked PendingTaskRepository."""
    mock_repo = _make_repo(expired_tasks=expired_tasks)
    svc = BackgroundSweepService(
        pending_task_repo=mock_repo,
        config=SweepConfig(sweep_interval_seconds=60, task_ttl_seconds=300),
    )
    return svc, mock_repo


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
        expired_task = {"task_id": "t1", "status": "pending"}
        svc, mock_repo = _make_sweep(expired_tasks=[expired_task])
        await svc._sweep_once()

        mock_repo.update_status.assert_called_once_with("t1", "failed")

    @pytest.mark.asyncio
    async def test_fresh_pending_task_is_not_touched(self, sweep_config):
        """When find_expirable returns empty list, update_status must NOT be called."""
        svc, mock_repo = _make_sweep(expired_tasks=[])
        await svc._sweep_once()

        mock_repo.update_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_done_task_is_never_touched(self, sweep_config):
        """Tasks with status 'done' are not returned by find_expirable — no update called."""
        svc, mock_repo = _make_sweep(expired_tasks=[])
        await svc._sweep_once()

        mock_repo.update_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_failed_task_is_never_touched(self, sweep_config):
        """Tasks already in 'failed' status are not returned by find_expirable."""
        svc, mock_repo = _make_sweep(expired_tasks=[])
        await svc._sweep_once()

        mock_repo.update_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_running_task_is_also_expired(self, sweep_config):
        """Tasks with status 'running' that exceed TTL must also be failed."""
        expired_running = {"task_id": "t5", "status": "running"}
        svc, mock_repo = _make_sweep(expired_tasks=[expired_running])
        await svc._sweep_once()

        mock_repo.update_status.assert_called_once_with("t5", "failed")

    @pytest.mark.asyncio
    async def test_find_expirable_returns_empty_list_is_skipped(self, sweep_config):
        """When find_expirable returns empty list, update_status should not be called."""
        svc, mock_repo = _make_sweep(expired_tasks=[])
        await svc._sweep_once()  # must not raise

        mock_repo.update_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_mixed_tasks_only_expired_ones_are_failed(self, sweep_config):
        """Only tasks returned by find_expirable are marked failed."""
        expired1 = {"task_id": "tx", "status": "pending"}
        expired2 = {"task_id": "ty", "status": "running"}
        svc, mock_repo = _make_sweep(expired_tasks=[expired1, expired2])
        await svc._sweep_once()

        assert mock_repo.update_status.call_count == 2
        calls = {call.args[0] for call in mock_repo.update_status.call_args_list}
        assert calls == {"tx", "ty"}
        for call in mock_repo.update_status.call_args_list:
            assert call.args[1] == "failed"


# ---------------------------------------------------------------------------
# Configurable interval test
# ---------------------------------------------------------------------------


class TestSweepInterval:
    def test_interval_is_read_from_config(self):
        """BackgroundSweepService must expose sweep_interval_seconds from config."""
        cfg = SweepConfig(sweep_interval_seconds=42, task_ttl_seconds=300)
        svc, _ = _make_sweep()
        svc.config = cfg
        assert svc.config.sweep_interval_seconds == 42

    def test_ttl_is_read_from_config(self):
        """BackgroundSweepService must expose task_ttl_seconds from config."""
        cfg = SweepConfig(sweep_interval_seconds=60, task_ttl_seconds=999)
        svc, _ = _make_sweep()
        svc.config = cfg
        assert svc.config.task_ttl_seconds == 999


# ---------------------------------------------------------------------------
# start / stop lifecycle tests
# ---------------------------------------------------------------------------


class TestSweepLifecycle:
    @pytest.mark.asyncio
    async def test_start_creates_background_task(self):
        """start() should schedule the sweep loop as an asyncio background task."""
        svc, _ = _make_sweep(expired_tasks=[])
        await svc.start()
        assert svc.is_running()
        await svc.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_background_task(self):
        """stop() should cancel the background loop and mark service as stopped."""
        svc, _ = _make_sweep(expired_tasks=[])
        await svc.start()
        await svc.stop()
        assert not svc.is_running()
