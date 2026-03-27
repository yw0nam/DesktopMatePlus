# tests/services/websocket_service/test_knowledge_trigger.py
from unittest.mock import AsyncMock, MagicMock

from langchain_core.messages import HumanMessage

from src.services.websocket_service.manager.disconnect_handler import (
    MIN_TURNS_FOR_SUMMARY,
    STM_INLINE_MAX_TURNS,
    build_delegate_payload,
    on_disconnect_handler,
)


def _agent_service(messages, knowledge_saved=False):
    svc = MagicMock()
    checkpoint = MagicMock()
    checkpoint.values = {"messages": messages, "knowledge_saved": knowledge_saved}
    svc.agent.aget_state = AsyncMock(return_value=checkpoint)
    svc.agent.aupdate_state = AsyncMock()
    return svc


async def test_skips_when_knowledge_saved():
    svc = _agent_service(
        [HumanMessage("hi")] * MIN_TURNS_FOR_SUMMARY, knowledge_saved=True
    )
    delegate = AsyncMock()
    await on_disconnect_handler(
        "s1", "u1", "yuri", agent_service=svc, delegate=delegate
    )
    delegate.assert_not_called()


async def test_skips_when_too_few_turns():
    svc = _agent_service([HumanMessage("hi")])  # below threshold
    delegate = AsyncMock()
    await on_disconnect_handler(
        "s1", "u1", "yuri", agent_service=svc, delegate=delegate
    )
    delegate.assert_not_called()


async def test_delegates_and_marks_saved():
    msgs = [HumanMessage(f"msg {i}") for i in range(MIN_TURNS_FOR_SUMMARY)]
    svc = _agent_service(msgs)
    delegate = AsyncMock()
    await on_disconnect_handler(
        "s1", "u1", "yuri", agent_service=svc, delegate=delegate
    )
    delegate.assert_called_once()
    update = svc.agent.aupdate_state.call_args[0][1]
    assert update == {"knowledge_saved": True}


async def test_aget_state_called_with_thread_id():
    msgs = [HumanMessage(f"m{i}") for i in range(MIN_TURNS_FOR_SUMMARY)]
    svc = _agent_service(msgs)
    await on_disconnect_handler(
        "sess-99", "u1", "yuri", agent_service=svc, delegate=AsyncMock()
    )
    config = svc.agent.aget_state.call_args[0][0]
    assert config["configurable"]["thread_id"] == "sess-99"


def test_option_a_payload_when_turns_below_threshold():
    msgs = [HumanMessage(f"m{i}") for i in range(STM_INLINE_MAX_TURNS - 1)]
    payload = build_delegate_payload("s1", "u1", "yuri", msgs)
    assert "stm_messages" in payload
    assert "stm_fetch_url" not in payload


def test_option_b_payload_when_turns_above_threshold():
    msgs = [HumanMessage(f"m{i}") for i in range(STM_INLINE_MAX_TURNS + 1)]
    payload = build_delegate_payload("s1", "u1", "yuri", msgs)
    assert "stm_fetch_url" in payload
    assert "stm_messages" not in payload
