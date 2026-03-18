from unittest.mock import MagicMock

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from src.services.websocket_service.manager.memory_orchestrator import (
    load_context,
    save_turn,
)


@pytest.mark.asyncio
class TestLoadContext:
    async def test_returns_empty_list_when_no_services(self):
        result = await load_context(
            stm_service=None,
            ltm_service=None,
            user_id="u1",
            agent_id="a1",
            session_id="s1",
            query="hello",
            limit=10,
        )
        assert result == []

    async def test_prepends_ltm_before_stm_history(self):
        stm = MagicMock()
        ltm = MagicMock()
        ltm.search_memory.return_value = {"results": [{"memory": "past event"}]}
        stm_msgs = [HumanMessage(content="hi")]
        stm.get_chat_history.return_value = stm_msgs

        result = await load_context(
            stm_service=stm,
            ltm_service=ltm,
            user_id="u1",
            agent_id="a1",
            session_id="s1",
            query="hello",
            limit=10,
        )

        assert len(result) == 2
        assert isinstance(result[0], SystemMessage)
        assert "past event" in result[0].content
        assert result[1] is stm_msgs[0]
        # LTM searched only once
        ltm.search_memory.assert_called_once()

    async def test_skips_ltm_prefix_when_no_results(self):
        stm = MagicMock()
        ltm = MagicMock()
        ltm.search_memory.return_value = {"results": []}
        stm.get_chat_history.return_value = [HumanMessage(content="hi")]

        result = await load_context(
            stm_service=stm,
            ltm_service=ltm,
            user_id="u1",
            agent_id="a1",
            session_id="s1",
            query="hello",
            limit=10,
        )

        assert len(result) == 1
        assert isinstance(result[0], HumanMessage)

    async def test_returns_stm_history_without_ltm(self):
        stm = MagicMock()
        stm.get_chat_history.return_value = [HumanMessage(content="hi")]

        result = await load_context(
            stm_service=stm,
            ltm_service=None,
            user_id="u1",
            agent_id="a1",
            session_id="s1",
            query="hello",
            limit=10,
        )

        assert len(result) == 1


@pytest.mark.asyncio
class TestSaveTurn:
    async def test_saves_to_stm(self):
        stm = MagicMock()
        new_chats = [HumanMessage(content="hi")]

        await save_turn(
            new_chats=new_chats,
            stm_service=stm,
            ltm_service=None,
            user_id="u1",
            agent_id="a1",
            session_id="s1",
        )

        stm.add_chat_history.assert_called_once_with(
            user_id="u1", agent_id="a1", session_id="s1", messages=new_chats
        )

    async def test_consolidates_to_ltm_at_interval(self):
        stm = MagicMock()
        ltm = MagicMock()
        new_chats = [HumanMessage(content="hi")]
        history = [HumanMessage(content=f"msg{i}") for i in range(10)]
        stm.get_chat_history.return_value = history
        stm.get_session_metadata.return_value = {"ltm_last_consolidated_at_turn": 0}

        await save_turn(
            new_chats=new_chats,
            stm_service=stm,
            ltm_service=ltm,
            user_id="u1",
            agent_id="a1",
            session_id="s1",
        )

        ltm.add_memory.assert_called_once()
        stm.update_session_metadata.assert_called()

    async def test_skips_ltm_consolidation_below_interval(self):
        stm = MagicMock()
        ltm = MagicMock()
        new_chats = [HumanMessage(content="hi")]
        history = [HumanMessage(content=f"msg{i}") for i in range(5)]
        stm.get_chat_history.return_value = history
        stm.get_session_metadata.return_value = {"ltm_last_consolidated_at_turn": 0}

        await save_turn(
            new_chats=new_chats,
            stm_service=stm,
            ltm_service=ltm,
            user_id="u1",
            agent_id="a1",
            session_id="s1",
        )

        ltm.add_memory.assert_not_called()

    async def test_no_op_when_empty_new_chats(self):
        stm = MagicMock()

        await save_turn(
            new_chats=[],
            stm_service=stm,
            ltm_service=None,
            user_id="u1",
            agent_id="a1",
            session_id="s1",
        )

        stm.add_chat_history.assert_not_called()
