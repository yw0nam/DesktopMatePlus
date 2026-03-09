"""Tests for LTM consolidation in AgentService.save_memory.

Verifies:
- Turn counter is computed as count of HumanMessage only (user turns)
- AIMessage, SystemMessage (synthetic) are NOT counted as turns
- LTM consolidation triggers when (current_turn - last_consolidated) >= INTERVAL
- Synthetic messages in history are included in the slice passed to LTM
- History slice starts at the last_consolidated-th HumanMessage (not last_consolidated*2)
- No LTM consolidation when interval threshold is not reached
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
# Turn counter: HumanMessage-only count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_turn_counter_counts_human_messages_only(agent):
    """Turn counter = number of HumanMessages in history."""
    # 8 HumanMessages → current_turn = 8
    history = [HumanMessage(content=f"msg {i}") for i in range(8)]
    stm = _make_stm(history, metadata={"ltm_last_consolidated_at_turn": 0})
    ltm = _make_ltm()

    # 8 turns < 10 (INTERVAL), so LTM should NOT be called
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
async def test_turn_counter_exact_human_count(agent):
    """Turn counter counts all 9 HumanMessages exactly, below threshold."""
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
    """LTM receives history starting from the last_consolidated-th HumanMessage.

    With last_consolidated=0 and a pure H/A history, the slice starts at index 0
    (the first HumanMessage), which equals the full history.
    """
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
    # last_consolidated=0 means no turns consolidated yet → full history
    assert messages_arg == history


@pytest.mark.asyncio
async def test_consolidation_slice_starts_from_offset(agent):
    """When last_consolidated > 0, slice starts at the last_consolidated-th HumanMessage.

    With last_consolidated=3 and a pure H/A history, the 3rd HumanMessage (0-indexed)
    is at index 6, so the slice is history[6:].
    """
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
    # In a pure H/A history, the 3rd HumanMessage is at index 6
    assert messages_arg[0] == HumanMessage(content="user 3")
    assert messages_arg == history[6:]


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
    """Pure synthetic messages do not create user turns.

    If a session has only synthetic SystemMessages (no HumanMessages),
    turn counter = 0 and consolidation is never triggered.
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
# Bug regression: synthetic messages must NOT inflate turn counter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_synthetic_messages_do_not_inflate_turn_counter(agent):
    """Synthetic (non-HumanMessage) messages must NOT count as turns.

    5 H/A pairs + 10 SystemMessages = 20 total messages.
    Old len//2 = 10 would wrongly trigger consolidation.
    HumanMessage-only count = 5 must NOT trigger (< 10 interval).
    """
    history = []
    for i in range(5):
        history.append(HumanMessage(content=f"user {i}"))
        history.append(AIMessage(content=f"assistant {i}"))
    for i in range(10):
        history.append(SystemMessage(content=f"[TaskResult:task-{i}] Done."))

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
async def test_slice_excludes_pre_boundary_synthetic_messages(agent):
    """Slice must start at the last_consolidated-th HumanMessage, not last_consolidated*2.

    Layout: 3 H/A pairs + 5 SystemMessages + 10 H/A pairs, last_consolidated=3.
    13 HumanMessages total, gap = 13 - 3 = 10 >= interval → triggers consolidation.
    Old history[6:] starts at the first SystemMessage (wrong).
    New slice must start exactly at H("user 3") (the 4th HumanMessage, index 11).
    """
    history = []
    # 3 H/A pairs → indices 0..5
    for i in range(3):
        history.append(HumanMessage(content=f"user {i}"))
        history.append(AIMessage(content=f"assistant {i}"))
    # 5 synthetic messages → indices 6..10
    for i in range(5):
        history.append(SystemMessage(content=f"[TaskResult:task-{i}] Done."))
    # 10 H/A pairs → indices 11..30  (13 HumanMessages total)
    for i in range(3, 13):
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

    ltm.add_memory.assert_called_once()
    call_kwargs = ltm.add_memory.call_args
    messages_arg = call_kwargs.kwargs.get("messages") or call_kwargs.args[0]

    # Slice must start at H("user 3"), NOT at a SystemMessage
    assert isinstance(
        messages_arg[0], HumanMessage
    ), f"Slice must start at HumanMessage, got {type(messages_arg[0])}"
    assert messages_arg[0].content == "user 3"


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
