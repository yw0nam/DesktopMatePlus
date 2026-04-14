"""Spike test: verify interrupt() works inside awrap_tool_call middleware.

This determines whether Option A (middleware-based HitL) is viable.
Uses a fake chat model with bind_tools support to avoid external API dependency.
"""

from collections.abc import Callable, Sequence
from typing import Any

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.language_models import FakeMessagesListChatModel
from langchain_core.language_models.chat_models import LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, interrupt


class FakeToolChatModel(FakeMessagesListChatModel):
    """FakeMessagesListChatModel that supports bind_tools (returns self)."""

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, BaseMessage]:
        return self


class InterruptMiddleware(AgentMiddleware):
    """Test middleware that calls interrupt() for a specific tool."""

    async def awrap_tool_call(self, request, handler):
        tool_name = request.tool_call["name"]
        if tool_name == "dangerous_tool":
            resume_value = interrupt(
                {
                    "tool_name": tool_name,
                    "tool_args": request.tool_call.get("args", {}),
                    "request_id": "test-123",
                }
            )
            if resume_value.get("approved"):
                return await handler(request)
            return "User denied execution."
        return await handler(request)


@tool
def dangerous_tool(query: str) -> str:
    """A tool that requires approval."""
    return f"Executed with: {query}"


def _make_fake_llm() -> FakeToolChatModel:
    """Create a fake LLM that first calls dangerous_tool, then returns final answer."""
    return FakeToolChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "dangerous_tool",
                        "args": {"query": "hello"},
                        "id": "call_123",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Done! The tool returned the result."),
        ]
    )


def _check_messages_for(messages: list, substring: str) -> bool:
    """Check if any message (object or plain string) contains the substring."""
    for msg in messages:
        text = msg.content if hasattr(msg, "content") else str(msg)
        if substring in text.lower():
            return True
    return False


@pytest.mark.asyncio
async def test_interrupt_in_middleware():
    """Verify interrupt() works inside awrap_tool_call."""
    llm = _make_fake_llm()
    checkpointer = MemorySaver()

    agent = create_agent(
        model=llm,
        tools=[dangerous_tool],
        checkpointer=checkpointer,
        middleware=[InterruptMiddleware()],
    )

    config = {"configurable": {"thread_id": "spike-test-1"}}

    # Step 1: Invoke agent — should hit interrupt
    interrupt_found = False
    interrupt_value = None
    async for stream_type, data in agent.astream(
        {"messages": [("human", "Use the dangerous_tool with query 'hello'")]},
        config=config,
        stream_mode=["updates"],
    ):
        if stream_type == "updates" and "__interrupt__" in data:
            interrupt_found = True
            interrupt_value = data["__interrupt__"][0].value

    assert interrupt_found, "interrupt() was not detected in stream output"
    assert interrupt_value["tool_name"] == "dangerous_tool"
    assert interrupt_value["request_id"] == "test-123"

    # Step 2: Resume with approval — Command as first positional arg
    resumed = False
    tool_executed = False
    async for stream_type, data in agent.astream(
        Command(resume={"approved": True, "request_id": "test-123"}),
        config=config,
        stream_mode=["updates"],
    ):
        if stream_type == "updates":
            resumed = True
            for node_name, updates in data.items():
                if node_name == "tools":
                    messages = updates.get("messages", [])
                    if _check_messages_for(messages, "executed with:"):
                        tool_executed = True

    assert resumed, "Graph did not resume after Command(resume=...)"
    assert tool_executed, "Tool was not executed after approval"


@pytest.mark.asyncio
async def test_interrupt_deny_in_middleware():
    """Verify deny path works — tool returns denial string."""
    llm = _make_fake_llm()
    checkpointer = MemorySaver()

    agent = create_agent(
        model=llm,
        tools=[dangerous_tool],
        checkpointer=checkpointer,
        middleware=[InterruptMiddleware()],
    )

    config = {"configurable": {"thread_id": "spike-test-2"}}

    # Step 1: Hit interrupt
    async for _stream_type, _data in agent.astream(
        {"messages": [("human", "Use the dangerous_tool with query 'test'")]},
        config=config,
        stream_mode=["updates"],
    ):
        pass  # Just drain to interrupt point

    # Step 2: Resume with denial
    denied = False
    async for stream_type, data in agent.astream(
        Command(resume={"approved": False, "request_id": "test-123"}),
        config=config,
        stream_mode=["updates"],
    ):
        if stream_type == "updates":
            for node_name, updates in data.items():
                if node_name == "tools":
                    messages = updates.get("messages", [])
                    if _check_messages_for(messages, "denied"):
                        denied = True

    assert denied, "Deny path did not return error message"
