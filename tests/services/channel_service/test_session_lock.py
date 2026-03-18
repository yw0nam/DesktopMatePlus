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

    def test_locks_cache_has_bounded_maxsize(self):
        """_locks 캐시의 maxsize가 양수로 설정되어 있는지 확인한다."""
        from src.services.channel_service.session_lock import _locks

        assert _locks.maxsize > 0
