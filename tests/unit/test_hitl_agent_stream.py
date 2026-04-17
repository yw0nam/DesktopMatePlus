"""Unit tests for HitL interrupt detection and resume in OpenAIChatAgent."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.websocket import ToolCategory
from src.services.agent_service.openai_chat_agent import OpenAIChatAgent


def _make_agent() -> OpenAIChatAgent:
    """Create an agent with mocked internals."""
    agent = OpenAIChatAgent.__new__(OpenAIChatAgent)
    agent.agent = MagicMock()
    agent._mcp_tools = []
    agent._personas = {}
    agent.llm = MagicMock()
    agent.mcp_config = None
    agent.model_name = "test"
    agent.temperature = 0
    agent.top_p = 1
    return agent


async def _fake_astream_with_interrupt(*args, **kwargs):
    """Simulate astream that hits an interrupt."""
    yield (
        "updates",
        {
            "__interrupt__": [
                MagicMock(
                    value={
                        "tool_name": "mcp_search",
                        "tool_args": {"query": "test"},
                        "request_id": "req-123",
                    }
                )
            ]
        },
    )


async def _fake_astream_normal(*args, **kwargs):
    """Simulate normal astream with model output."""
    yield (
        "updates",
        {
            "model": {"messages": [MagicMock(content="Hello world")]},
        },
    )


async def _fake_astream_resume_approve(*args, **kwargs):
    """Simulate resumed astream after approval -- tool executes then model responds."""
    yield (
        "updates",
        {
            "tools": {"messages": [MagicMock(content="Tool executed successfully")]},
        },
    )
    yield (
        "updates",
        {
            "model": {"messages": [MagicMock(content="Here is the result")]},
        },
    )


async def _fake_astream_resume_with_second_interrupt(*args, **kwargs):
    """Simulate resumed astream that hits another interrupt."""
    yield (
        "updates",
        {
            "tools": {"messages": [MagicMock(content="First tool done")]},
        },
    )
    yield (
        "updates",
        {
            "__interrupt__": [
                MagicMock(
                    value={
                        "tool_name": "mcp_write",
                        "tool_args": {"data": "important"},
                        "request_id": "req-456",
                    }
                )
            ]
        },
    )


# Helper for mocking async iterator
class AsyncIteratorMock:
    def __init__(self, items: list):
        self.items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.items)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class TestInterruptDetection:
    """Test __interrupt__ detection in _process_message."""

    @pytest.mark.asyncio
    async def test_interrupt_detected_in_updates_stream(self):
        """__interrupt__ in updates stream should yield hitl_request."""
        agent = _make_agent()
        agent.agent.astream = _fake_astream_with_interrupt

        events = []
        async for event in agent._process_message(
            messages=[],
            config={"configurable": {"thread_id": "test-session"}},
        ):
            events.append(event)

        assert len(events) == 1
        assert events[0]["type"] == "hitl_request"
        assert events[0]["tool_name"] == "mcp_search"
        assert events[0]["tool_args"] == {"query": "test"}
        assert events[0]["request_id"] == "req-123"
        assert events[0]["session_id"] == "test-session"

    @pytest.mark.asyncio
    async def test_hitl_request_event_has_correct_fields(self):
        """hitl_request should contain request_id, tool_name, tool_args, session_id."""
        agent = _make_agent()
        agent.agent.astream = _fake_astream_with_interrupt

        events = []
        async for event in agent._process_message(
            messages=[],
            config={"configurable": {"thread_id": "sess-1"}},
        ):
            events.append(event)

        hitl_event = events[0]
        required_fields = {"type", "request_id", "tool_name", "tool_args", "session_id"}
        assert required_fields.issubset(hitl_event.keys())

    @pytest.mark.asyncio
    async def test_stream_exits_after_hitl_request(self):
        """After hitl_request, _process_message should NOT yield final_response."""
        agent = _make_agent()
        agent.agent.astream = _fake_astream_with_interrupt

        events = []
        async for event in agent._process_message(
            messages=[],
            config={"configurable": {"thread_id": "test"}},
        ):
            events.append(event)

        event_types = [e["type"] for e in events]
        assert "final_response" not in event_types
        assert "stream_end" not in event_types

    @pytest.mark.asyncio
    async def test_stream_hitl_request_propagated_through_stream(self):
        """stream() should yield hitl_request and NOT yield stream_end."""
        agent = _make_agent()
        agent.agent.astream = _fake_astream_with_interrupt

        events = []
        async for event in agent.stream(
            messages=[],
            session_id="test-session",
        ):
            events.append(event)

        event_types = [e["type"] for e in events]
        assert "stream_start" in event_types
        assert "hitl_request" in event_types
        assert "stream_end" not in event_types


class TestResumeAfterApproval:
    """Test resume_after_approval method."""

    @pytest.mark.asyncio
    async def test_resume_approve_continues_stream(self):
        """Approved resume should yield tool result and stream_end."""
        agent = _make_agent()
        agent.agent.astream = _fake_astream_resume_approve

        events = []
        async for event in agent.resume_after_approval(
            session_id="test-session",
            approved=True,
            request_id="req-123",
        ):
            events.append(event)

        event_types = [e["type"] for e in events]
        assert "stream_end" in event_types

    @pytest.mark.asyncio
    async def test_resume_uses_command_as_first_positional_arg(self):
        """Command(resume=...) should be passed as first positional arg to astream."""
        agent = _make_agent()
        agent.agent.astream = AsyncMock(return_value=AsyncIteratorMock([]))

        events = []
        async for event in agent.resume_after_approval(
            session_id="sess-1",
            approved=True,
            request_id="req-1",
        ):
            events.append(event)

        # Check astream was called with Command as first arg
        call_args = agent.agent.astream.call_args
        first_arg = call_args[0][0]
        from langgraph.types import Command

        assert isinstance(first_arg, Command)

    @pytest.mark.asyncio
    async def test_resume_second_interrupt_yields_another_hitl_request(self):
        """If resume hits another interrupt, yield another hitl_request."""
        agent = _make_agent()
        agent.agent.astream = _fake_astream_resume_with_second_interrupt

        events = []
        async for event in agent.resume_after_approval(
            session_id="test-session",
            approved=True,
            request_id="req-123",
        ):
            events.append(event)

        event_types = [e["type"] for e in events]
        assert "hitl_request" in event_types
        hitl_events = [e for e in events if e["type"] == "hitl_request"]
        assert hitl_events[0]["tool_name"] == "mcp_write"
        assert hitl_events[0]["request_id"] == "req-456"
        # Should NOT have stream_end after interrupt
        assert "stream_end" not in event_types


class TestConsumeAstreamCategory:
    @pytest.mark.asyncio
    async def test_hitl_request_event_includes_category(self):
        fake_interrupt = MagicMock()
        fake_interrupt.value = {
            "request_id": "r-1",
            "tool_name": "write_file",
            "tool_args": {"path": "/tmp/x"},
            "category": ToolCategory.STATE_MUTATING.value,
        }

        async def fake_astream():
            yield ("updates", {"__interrupt__": [fake_interrupt]})

        agent = _make_agent()
        events = [e async for e in agent._consume_astream(fake_astream(), "sess-1")]

        assert events, "no events yielded"
        evt = events[0]
        assert evt["type"] == "hitl_request"
        assert evt["category"] == ToolCategory.STATE_MUTATING.value
        assert evt["session_id"] == "sess-1"

    @pytest.mark.asyncio
    async def test_hitl_request_event_falls_back_to_dangerous(self):
        fake_interrupt = MagicMock()
        fake_interrupt.value = {
            "request_id": "r-2",
            "tool_name": "legacy_tool",
            "tool_args": {},
        }

        async def fake_astream():
            yield ("updates", {"__interrupt__": [fake_interrupt]})

        agent = _make_agent()
        events = [e async for e in agent._consume_astream(fake_astream(), "sess-2")]

        assert events[0]["category"] == ToolCategory.DANGEROUS.value
