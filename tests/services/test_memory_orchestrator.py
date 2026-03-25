from unittest.mock import MagicMock

from src.services.websocket_service.manager.memory_orchestrator import load_ltm_prefix


async def test_load_ltm_prefix_returns_empty_without_ltm():
    result = await load_ltm_prefix(
        ltm_service=None, user_id="u1", agent_id="a1", query="hi"
    )
    assert result == []


async def test_load_ltm_prefix_returns_system_message():
    ltm = MagicMock()
    ltm.search_memory = MagicMock(return_value={"results": [{"text": "memory"}]})
    result = await load_ltm_prefix(
        ltm_service=ltm, user_id="u1", agent_id="a1", query="hi"
    )
    assert len(result) == 1
    assert "Long-term memories" in result[0].content


def test_save_turn_not_exported():
    import src.services.websocket_service.manager.memory_orchestrator as mo

    assert not hasattr(mo, "save_turn"), "save_turn should be removed"


def test_load_context_not_exported():
    import src.services.websocket_service.manager.memory_orchestrator as mo

    assert not hasattr(
        mo, "load_context"
    ), "load_context should be replaced by load_ltm_prefix"
