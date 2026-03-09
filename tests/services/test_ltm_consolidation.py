"""Tests for LTM consolidation in AgentService.save_memory.

Verifies:
- Turn counter is computed as len(history) // 2 (total messages divided by 2)
- LTM consolidation triggers when (current_turn - last_consolidated) >= INTERVAL
- Synthetic messages (SystemMessage injected via NanoClaw callback) are included
  in history and therefore in the messages passed to LTM on consolidation
- No LTM consolidation when interval threshold is not reached
- Correct history slice is passed to LTM (from last_consolidated * 2 onward)
"""

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.services.agent_service.service import AgentService


class ConcreteAgentService(AgentService):
    """Minimal concrete subclass for testing AgentService.save_memory."""

    def initialize_model(self):
        return MagicMock(), MagicMock()

    async def is_healthy(self):
        return True, "ok"

    async def stream(self, *args, **kwargs):
        yield {"type": "stream_end"}


@pytest.fixture
def agent():
    return ConcreteAgentService()


def _make_stm(history: list, metadata: dict | None = None):
    """Build a synchronous mock STM service."""
    stm = MagicMock()
    stm.add_chat_history.return_value = "session-id"
    stm.get_chat_history.return_value = history
    stm.get_session_metadata.return_value = metadata or {}
    stm.update_session_metadata.return_value = True
    return stm


def _make_ltm():
    ltm = MagicMock()
    ltm.add_memory.return_value = {"results": [], "relations": []}
    return ltm


# ---------------------------------------------------------------------------
# Turn counter: len(history) // 2
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_turn_counter_counts_message_pairs(agent):
    """Turn counter = len(full history) // 2, flooring odd counts."""
    # 8 messages = 4 human+AI pairs → current_turn = 4
    history = [HumanMessage(content=f"msg {i}") for i in range(8)]
    stm = _make_stm(history, metadata={"ltm_last_consolidated_at_turn": 0})
    ltm = _make_ltm()

    # 4 turns < 10 (INTERVAL), so LTM should NOT be called
    await agent.save_memory(
        new_chats=[HumanMessage(content="new")],
        stm_service=stm,
        ltm_service=ltm,
        user_id="u1",
        agent_id="a1",
        session_id="s1",
    )

    ltm.add_memory.assert_not_called()


@pytest.mark.asyncio
async def test_turn_counter_floors_odd_message_count(agent):
    """Odd number of messages: floor(9/2) = 4, below threshold."""
    history = [HumanMessage(content=f"msg {i}") for i in range(9)]
    stm = _make_stm(history, metadata={"ltm_last_consolidated_at_turn": 0})
    ltm = _make_ltm()

    await agent.save_memory(
        new_chats=[],
        stm_service=stm,
        ltm_service=ltm,
        user_id="u1",
        agent_id="a1",
        session_id="s1",
    )

    ltm.add_memory.assert_not_called()


# ---------------------------------------------------------------------------
# LTM consolidation triggers at correct threshold
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consolidation_triggers_at_interval(agent):
    """LTM consolidation fires when current_turn - last_consolidated >= 10."""
    # 20 messages = 10 pairs, last consolidated at 0 → gap = 10 >= 10
    history = []
    for i in range(10):
        history.append(HumanMessage(content=f"user {i}"))
        history.append(AIMessage(content=f"assistant {i}"))

    stm = _make_stm(history, metadata={"ltm_last_consolidated_at_turn": 0})
    ltm = _make_ltm()

    await agent.save_memory(
        new_chats=[],
        stm_service=stm,
        ltm_service=ltm,
        user_id="u1",
        agent_id="a1",
        session_id="s1",
    )

    ltm.add_memory.assert_called_once()


@pytest.mark.asyncio
async def test_consolidation_not_triggered_below_interval(agent):
    """LTM consolidation is NOT triggered when gap < 10 turns."""
    # 18 messages = 9 pairs, last_consolidated = 0 → gap = 9 < 10
    history = []
    for i in range(9):
        history.append(HumanMessage(content=f"user {i}"))
        history.append(AIMessage(content=f"assistant {i}"))

    stm = _make_stm(history, metadata={"ltm_last_consolidated_at_turn": 0})
    ltm = _make_ltm()

    await agent.save_memory(
        new_chats=[],
        stm_service=stm,
        ltm_service=ltm,
        user_id="u1",
        agent_id="a1",
        session_id="s1",
    )

    ltm.add_memory.assert_not_called()


@pytest.mark.asyncio
async def test_consolidation_uses_last_consolidated_offset(agent):
    """Gap is measured from last_consolidated, not from zero."""
    # 12 pairs total, last consolidated at 3 → gap = 9 < 10, no trigger
    history = []
    for i in range(12):
        history.append(HumanMessage(content=f"user {i}"))
        history.append(AIMessage(content=f"assistant {i}"))

    stm = _make_stm(history, metadata={"ltm_last_consolidated_at_turn": 3})
    ltm = _make_ltm()

    await agent.save_memory(
        new_chats=[],
        stm_service=stm,
        ltm_service=ltm,
        user_id="u1",
        agent_id="a1",
        session_id="s1",
    )

    ltm.add_memory.assert_not_called()


@pytest.mark.asyncio
async def test_consolidation_triggers_with_correct_offset(agent):
    """Consolidation fires when gap exactly reaches threshold from offset."""
    # 13 pairs, last_consolidated = 3 → gap = 10 >= 10, should trigger
    history = []
    for i in range(13):
        history.append(HumanMessage(content=f"user {i}"))
        history.append(AIMessage(content=f"assistant {i}"))

    stm = _make_stm(history, metadata={"ltm_last_consolidated_at_turn": 3})
    ltm = _make_ltm()

    await agent.save_memory(
        new_chats=[],
        stm_service=stm,
        ltm_service=ltm,
        user_id="u1",
        agent_id="a1",
        session_id="s1",
    )

    ltm.add_memory.assert_called_once()


# ---------------------------------------------------------------------------
# Correct history slice passed to LTM
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consolidation_passes_correct_history_slice(agent):
    """LTM receives history[last_consolidated*2:], not the full history."""
    history = []
    for i in range(10):
        history.append(HumanMessage(content=f"user {i}"))
        history.append(AIMessage(content=f"assistant {i}"))

    last_consolidated = 0
    stm = _make_stm(
        history, metadata={"ltm_last_consolidated_at_turn": last_consolidated}
    )
    ltm = _make_ltm()

    await agent.save_memory(
        new_chats=[],
        stm_service=stm,
        ltm_service=ltm,
        user_id="u1",
        agent_id="a1",
        session_id="s1",
    )

    call_kwargs = ltm.add_memory.call_args
    messages_arg = call_kwargs.kwargs.get("messages") or call_kwargs.args[0]
    expected_slice = history[last_consolidated * 2 :]
    assert messages_arg == expected_slice


@pytest.mark.asyncio
async def test_consolidation_slice_starts_from_offset(agent):
    """When last_consolidated > 0, slice starts at last_consolidated*2."""
    history = []
    for i in range(13):
        history.append(HumanMessage(content=f"user {i}"))
        history.append(AIMessage(content=f"assistant {i}"))

    last_consolidated = 3
    stm = _make_stm(
        history, metadata={"ltm_last_consolidated_at_turn": last_consolidated}
    )
    ltm = _make_ltm()

    await agent.save_memory(
        new_chats=[],
        stm_service=stm,
        ltm_service=ltm,
        user_id="u1",
        agent_id="a1",
        session_id="s1",
    )

    call_kwargs = ltm.add_memory.call_args
    messages_arg = call_kwargs.kwargs.get("messages") or call_kwargs.args[0]
    expected_slice = history[last_consolidated * 2 :]
    assert messages_arg == expected_slice


@pytest.mark.asyncio
async def test_session_metadata_updated_after_consolidation(agent):
    """After LTM consolidation, session metadata is updated with current_turn."""
    history = []
    for i in range(10):
        history.append(HumanMessage(content=f"user {i}"))
        history.append(AIMessage(content=f"assistant {i}"))

    stm = _make_stm(history, metadata={"ltm_last_consolidated_at_turn": 0})
    ltm = _make_ltm()

    await agent.save_memory(
        new_chats=[],
        stm_service=stm,
        ltm_service=ltm,
        user_id="u1",
        agent_id="a1",
        session_id="s1",
    )

    stm.update_session_metadata.assert_called_once()
    call_args = stm.update_session_metadata.call_args
    updated_meta = (
        call_args.args[1] if call_args.args else call_args.kwargs.get("metadata")
    )
    assert updated_meta == {"ltm_last_consolidated_at_turn": 10}


# ---------------------------------------------------------------------------
# Synthetic messages (injected SystemMessages) are included in consolidation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_synthetic_messages_included_in_consolidation(agent):
    """Synthetic SystemMessages in history are visible to LTM consolidation.

    NanoClaw callback injects SystemMessages into STM.  Those messages are
    retrieved by get_chat_history() and included in the slice passed to LTM.
    """
    # Build a realistic session: 9 human+AI pairs plus 1 synthetic SystemMessage
    # Total = 19 messages, len//2 = 9 — below threshold alone.
    # Add one more human+AI pair to reach 10 pairs total from start.
    history = []
    for i in range(9):
        history.append(HumanMessage(content=f"user {i}"))
        history.append(AIMessage(content=f"assistant {i}"))
    # Synthetic message injected by callback (SystemMessage)
    history.append(SystemMessage(content="[TaskResult:task-123] Code reviewed."))
    # One more human+AI pair  → total = 21 messages, len//2 = 10 → threshold met
    history.append(HumanMessage(content="user 9"))
    history.append(AIMessage(content="assistant 9"))

    stm = _make_stm(history, metadata={"ltm_last_consolidated_at_turn": 0})
    ltm = _make_ltm()

    await agent.save_memory(
        new_chats=[],
        stm_service=stm,
        ltm_service=ltm,
        user_id="u1",
        agent_id="a1",
        session_id="s1",
    )

    ltm.add_memory.assert_called_once()

    # The synthetic message must be present in the slice sent to LTM
    call_kwargs = ltm.add_memory.call_args
    messages_arg = call_kwargs.kwargs.get("messages") or call_kwargs.args[0]
    synthetic_contents = [
        m.content for m in messages_arg if isinstance(m, SystemMessage)
    ]
    assert any(
        "TaskResult" in c for c in synthetic_contents
    ), "Synthetic SystemMessage was not included in messages passed to LTM"


@pytest.mark.asyncio
async def test_synthetic_only_session_does_not_miscount(agent):
    """Pure synthetic messages do not create extra 'user turns'.

    If a session has only synthetic SystemMessages (no human+AI pairs),
    len(history)//2 floors to 0 and consolidation is never triggered.
    """
    history = [
        SystemMessage(content="[TaskResult:task-1] Done."),
        SystemMessage(content="[TaskResult:task-2] Done."),
    ]
    stm = _make_stm(history, metadata={"ltm_last_consolidated_at_turn": 0})
    ltm = _make_ltm()

    await agent.save_memory(
        new_chats=[],
        stm_service=stm,
        ltm_service=ltm,
        user_id="u1",
        agent_id="a1",
        session_id="s1",
    )

    ltm.add_memory.assert_not_called()


# ---------------------------------------------------------------------------
# No LTM service — no crash
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_ltm_service_skips_consolidation(agent):
    """When ltm_service is None, save_memory runs without error."""
    history = []
    for i in range(10):
        history.append(HumanMessage(content=f"user {i}"))
        history.append(AIMessage(content=f"assistant {i}"))

    stm = _make_stm(history, metadata={})

    # Should not raise
    await agent.save_memory(
        new_chats=[HumanMessage(content="new")],
        stm_service=stm,
        ltm_service=None,
        user_id="u1",
        agent_id="a1",
        session_id="s1",
    )
