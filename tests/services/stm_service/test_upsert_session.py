from unittest.mock import MagicMock, patch

import pytest

from src.services.stm_service.mongodb import MongoDBSTM


class TestUpsertSession:
    @pytest.fixture
    def stm(self):
        with patch.object(MongoDBSTM, "initialize_memory", return_value=MagicMock()):
            svc = MongoDBSTM(
                connection_string="mongodb://localhost",
                database_name="test",
                sessions_collection_name="sessions",
                messages_collection_name="messages",
            )
            svc._sessions_collection = MagicMock()
            return svc

    def test_upsert_creates_session_if_not_exists(self, stm):
        stm._sessions_collection.update_one.return_value = MagicMock(upserted_id="new")
        result = stm.upsert_session("slack:T1:C1:default", "default", "yuri")
        assert result is True
        stm._sessions_collection.update_one.assert_called_once()
        call_args = stm._sessions_collection.update_one.call_args
        assert call_args[1]["upsert"] is True

    def test_upsert_returns_true_on_success(self, stm):
        stm._sessions_collection.update_one.return_value = MagicMock()
        result = stm.upsert_session("slack:T1:C1:default", "default", "yuri")
        assert result is True

    def test_upsert_filter_uses_session_id_only(self, stm):
        stm._sessions_collection.update_one.return_value = MagicMock()
        stm.upsert_session("my-session", "user1", "agent1")
        filter_arg = stm._sessions_collection.update_one.call_args[0][0]
        assert filter_arg == {"session_id": "my-session"}
        update_arg = stm._sessions_collection.update_one.call_args[0][1]
        assert update_arg["$set"]["user_id"] == "user1"
        assert update_arg["$set"]["agent_id"] == "agent1"
