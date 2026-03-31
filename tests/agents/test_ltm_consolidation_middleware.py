from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from src.services.agent_service.middleware.ltm_middleware import (
    _LTM_CONSOLIDATION_INTERVAL,
    ltm_consolidation_hook,
)


def _state(n_human: int, last: int = 0) -> dict:
    msgs = []
    for i in range(n_human):
        msgs.append(HumanMessage(content=f"h{i}"))
        msgs.append(AIMessage(content=f"a{i}"))
    return {
        "messages": msgs,
        "user_id": "u1",
        "agent_id": "yuri",
        "ltm_last_consolidated_at_turn": last,
    }


def test_returns_none_below_threshold():
    result = ltm_consolidation_hook(
        _state(_LTM_CONSOLIDATION_INTERVAL - 1), MagicMock()
    )
    assert result is None


def test_returns_update_at_threshold():
    with (
        patch(
            "src.services.agent_service.middleware.ltm_middleware.get_ltm_service"
        ) as m,
        patch("asyncio.create_task"),
    ):
        m.return_value = MagicMock()
        result = ltm_consolidation_hook(
            _state(_LTM_CONSOLIDATION_INTERVAL), MagicMock()
        )
    assert result == {"ltm_last_consolidated_at_turn": _LTM_CONSOLIDATION_INTERVAL}


def test_skips_when_ltm_unavailable():
    with patch(
        "src.services.agent_service.middleware.ltm_middleware.get_ltm_service"
    ) as m:
        m.return_value = None
        result = ltm_consolidation_hook(
            _state(_LTM_CONSOLIDATION_INTERVAL), MagicMock()
        )
    assert result is None


def test_no_double_trigger_within_interval():
    # consolidated at 10, current 15 — delta 5 < 10
    with (
        patch(
            "src.services.agent_service.middleware.ltm_middleware.get_ltm_service"
        ) as m,
        patch("asyncio.create_task") as mock_task,
    ):
        m.return_value = MagicMock()
        result = ltm_consolidation_hook(_state(15, last=10), MagicMock())
    assert result is None
    mock_task.assert_not_called()
