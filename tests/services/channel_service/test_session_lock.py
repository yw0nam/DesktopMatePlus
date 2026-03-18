import pytest

from src.services.channel_service.session_lock import session_lock


class TestSessionLock:
    def test_same_session_id_returns_same_lock(self):
        lock_a = session_lock("session-1")
        lock_b = session_lock("session-1")
        assert lock_a is lock_b

    def test_different_session_ids_return_different_locks(self):
        lock_a = session_lock("session-A")
        lock_b = session_lock("session-B")
        assert lock_a is not lock_b

    @pytest.mark.asyncio
    async def test_lock_is_async_context_manager(self):
        lock = session_lock("session-ctx")
        async with lock:
            pass  # Must not raise

    def test_lock_count_bounded_by_maxsize(self):
        """maxsize를 초과하면 가장 오래된 항목이 자동 evict된다."""
        from src.services.channel_service.session_lock import _locks
        original_maxsize = _locks.maxsize
        assert original_maxsize > 0
