"""Tests for stream() error handling in OpenAIChatAgent.

BE-BUG-1: When _process_message() yields an error event,
stream() must NOT yield a subsequent stream_end event.
"""

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage

from src.services.agent_service.openai_chat_agent import OpenAIChatAgent


def make_agent() -> OpenAIChatAgent:
    """Construct a minimal OpenAIChatAgent for testing."""
    with patch("src.services.agent_service.openai_chat_agent.ChatOpenAI"):
        agent = OpenAIChatAgent(
            temperature=0.7,
            top_p=0.9,
            openai_api_key="test-key",
            model_name="gpt-4o",
        )
    agent.agent = MagicMock()  # prevent real agent calls
    agent._personas = {}
    return agent


async def collect_stream(
    agent: OpenAIChatAgent, messages, **kwargs
) -> list[dict[str, Any]]:
    """Drain stream() into a list."""
    events = []
    async for event in agent.stream(messages=messages, **kwargs):
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# Fix 1: stream() must not emit stream_end after an error event
# ---------------------------------------------------------------------------


class TestStreamErrorHandling:
    async def test_error_in_process_message_suppresses_stream_end(self):
        """When _process_message yields an error, stream_end must NOT follow."""
        agent = make_agent()

        async def fake_process_message(**_kwargs) -> AsyncIterator[dict]:
            yield {"type": "stream_token", "chunk": "hello"}
            yield {"type": "error", "error": "메시지 처리 중 오류가 발생했습니다."}

        with patch.object(agent, "_process_message", side_effect=fake_process_message):
            events = await collect_stream(agent, [HumanMessage(content="hi")])

        types = [e["type"] for e in events]
        assert "error" in types, "error event must be emitted"
        assert (
            "stream_end" not in types
        ), "stream_end must NOT be emitted after an error event"

    async def test_normal_completion_still_emits_stream_end(self):
        """When _process_message completes normally, stream_end must be emitted."""
        agent = make_agent()
        from langchain_core.messages import AIMessage

        async def fake_process_message(**_kwargs) -> AsyncIterator[dict]:
            yield {"type": "stream_token", "chunk": "hello"}
            yield {"type": "final_response", "data": [AIMessage(content="hello")]}

        with patch.object(agent, "_process_message", side_effect=fake_process_message):
            events = await collect_stream(agent, [HumanMessage(content="hi")])

        types = [e["type"] for e in events]
        assert (
            "stream_end" in types
        ), "stream_end must be emitted after normal completion"
        assert "error" not in types

    async def test_stream_start_always_emitted(self):
        """stream_start is always emitted regardless of error."""
        agent = make_agent()

        async def fake_process_message(**_kwargs) -> AsyncIterator[dict]:
            yield {"type": "error", "error": "oops"}

        with patch.object(agent, "_process_message", side_effect=fake_process_message):
            events = await collect_stream(agent, [HumanMessage(content="hi")])

        types = [e["type"] for e in events]
        assert "stream_start" in types, "stream_start must always be emitted"


# ---------------------------------------------------------------------------
# Fix 2: CustomAgentState default values
# ---------------------------------------------------------------------------


class TestCustomAgentStateDefaults:
    def test_ltm_last_consolidated_at_turn_has_default(self):
        """ltm_last_consolidated_at_turn must have a default."""
        from src.services.agent_service.state import CustomAgentState

        optional_keys = getattr(CustomAgentState, "__optional_keys__", set())
        required_keys = getattr(CustomAgentState, "__required_keys__", set())

        assert (
            "ltm_last_consolidated_at_turn" in optional_keys
            or "ltm_last_consolidated_at_turn" not in required_keys
        ), "ltm_last_consolidated_at_turn must be optional (have a default value)"

    def test_knowledge_saved_has_default(self):
        """knowledge_saved must have a default."""
        from src.services.agent_service.state import CustomAgentState

        optional_keys = getattr(CustomAgentState, "__optional_keys__", set())
        required_keys = getattr(CustomAgentState, "__required_keys__", set())

        assert (
            "knowledge_saved" in optional_keys or "knowledge_saved" not in required_keys
        ), "knowledge_saved must be optional (have a default value)"
