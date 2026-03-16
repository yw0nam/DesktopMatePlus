"""Tests for on_disconnect knowledge summary trigger."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.services.stm_service.service import STMService
from src.services.websocket_service.manager.disconnect_handler import (
    build_delegate_payload,
    on_disconnect_handler,
)


@pytest.fixture
def mock_stm():
    svc = MagicMock(spec=STMService)
    return svc


@pytest.fixture
def mock_delegate():
    return AsyncMock()


@pytest.mark.asyncio
async def test_trigger_fires_when_conditions_met(mock_stm, mock_delegate):
    """Should call delegate when knowledge_saved=False and turns >= MIN_TURNS."""
    mock_stm.get_session_metadata.return_value = {"knowledge_saved": False}
    mock_stm.get_chat_history.return_value = [
        HumanMessage(content="hi"),
        AIMessage(content="hello"),
        HumanMessage(content="bye"),
        AIMessage(content="goodbye"),
        HumanMessage(content="again"),
    ]
    await on_disconnect_handler(
        session_id="s1",
        user_id="u1",
        agent_id="a1",
        stm_service=mock_stm,
        delegate=mock_delegate,
    )
    mock_delegate.assert_called_once()


@pytest.mark.asyncio
async def test_trigger_skips_when_already_saved(mock_stm, mock_delegate):
    """Should NOT call delegate when knowledge_saved=True."""
    mock_stm.get_session_metadata.return_value = {"knowledge_saved": True}
    await on_disconnect_handler(
        session_id="s1",
        user_id="u1",
        agent_id="a1",
        stm_service=mock_stm,
        delegate=mock_delegate,
    )
    mock_delegate.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_skips_when_insufficient_turns(mock_stm, mock_delegate):
    """Should NOT call delegate when human message count < MIN_TURNS (3)."""
    mock_stm.get_session_metadata.return_value = {"knowledge_saved": False}
    mock_stm.get_chat_history.return_value = [
        HumanMessage(content="hi"),
        AIMessage(content="hello"),
    ]  # only 1 HumanMessage
    await on_disconnect_handler(
        session_id="s1",
        user_id="u1",
        agent_id="a1",
        stm_service=mock_stm,
        delegate=mock_delegate,
    )
    mock_delegate.assert_not_called()


def test_option_a_payload_when_turns_below_threshold(mock_stm):
    """Option A: inline STM messages when turns < STM_INLINE_MAX_TURNS (30)."""
    mock_stm.get_chat_history.return_value = [
        HumanMessage(content=f"msg{i}") for i in range(5)  # 5 turns < 30
    ]
    payload = build_delegate_payload(
        session_id="s1", user_id="u1", agent_id="a1", stm=mock_stm
    )
    assert "stm_messages" in payload
    assert "stm_fetch_url" not in payload


def test_option_b_payload_when_turns_above_threshold(mock_stm):
    """Option B: fetch URL when turns >= STM_INLINE_MAX_TURNS (30)."""
    mock_stm.get_chat_history.return_value = [
        HumanMessage(content=f"msg{i}") for i in range(35)  # 35 turns >= 30
    ]
    payload = build_delegate_payload(
        session_id="s1", user_id="u1", agent_id="a1", stm=mock_stm
    )
    assert "stm_fetch_url" in payload
    assert "stm_messages" not in payload
