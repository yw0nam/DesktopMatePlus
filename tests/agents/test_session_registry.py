from unittest.mock import MagicMock

from src.services.agent_service.session_registry import SessionRegistry


def _make_registry():
    col = MagicMock()
    return SessionRegistry(col), col


def test_upsert_filters_by_thread_id():
    registry, col = _make_registry()
    registry.upsert("thread-1", "user-1", "yuri")
    col.update_one.assert_called_once()
    assert col.update_one.call_args[0][0] == {"thread_id": "thread-1"}


def test_list_sessions_calls_find_with_filter():
    registry, col = _make_registry()
    col.find.return_value = [{"thread_id": "t1"}]
    result = registry.list_sessions("u1", "yuri")
    call_filter = col.find.call_args[0][0]
    assert call_filter == {"user_id": "u1", "agent_id": "yuri"}
    assert result[0]["thread_id"] == "t1"


def test_find_all_returns_list():
    registry, col = _make_registry()
    col.find.return_value = [{"thread_id": "t1"}, {"thread_id": "t2"}]
    assert len(registry.find_all()) == 2


def test_delete_true_on_success():
    registry, col = _make_registry()
    col.delete_one.return_value = MagicMock(deleted_count=1)
    assert registry.delete("t1") is True


def test_delete_false_on_miss():
    registry, col = _make_registry()
    col.delete_one.return_value = MagicMock(deleted_count=0)
    assert registry.delete("nope") is False
