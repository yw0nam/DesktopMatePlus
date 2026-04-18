"""Spike: verify MongoDBSaver (sync) + HumanInTheLoopMiddleware interrupt/resume cycle.

Blocker for HITL built-in middleware migration. If this fails, the
migration plan needs to pivot (async saver swap or dependency bump).

Pattern mirrors tests/spike/test_interrupt_in_middleware.py — uses
FakeToolChatModel so no live LLM is needed; MONGO_URL env var required.
"""

import os
from collections.abc import Callable, Sequence
from typing import Any
from uuid import uuid4

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.language_models import FakeMessagesListChatModel
from langchain_core.language_models.chat_models import LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.types import Command
from pymongo import MongoClient

MONGO_URL = os.getenv("MONGO_URL", "mongodb://admin:test@192.168.0.43:27017/")


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


@tool
def mutating_tool(payload: str) -> str:
    """Fake mutating tool that must be gated by HITL."""
    return f"applied: {payload}"


def _fake_llm() -> FakeToolChatModel:
    return FakeToolChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "mutating_tool",
                        "args": {"payload": "x"},
                        "id": "call_1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Done."),
        ]
    )


@pytest.mark.spike
@pytest.mark.asyncio
async def test_mongodb_saver_supports_hitl_interrupt_and_resume():
    """Agent with MongoDBSaver pauses on mutating_tool, resumes on approve."""
    if not MONGO_URL:
        pytest.skip("MONGO_URL env var not set")

    mongo_client = MongoClient(MONGO_URL)
    # Use a unique db name per test to avoid cross-run contamination
    checkpointer = MongoDBSaver(client=mongo_client, db_name=f"spike_{uuid4().hex[:8]}")

    agent = create_agent(
        model=_fake_llm(),
        tools=[mutating_tool],
        checkpointer=checkpointer,
        middleware=[
            HumanInTheLoopMiddleware(interrupt_on={"mutating_tool": True}),
        ],
    )

    thread_id = f"spike-{uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    # Drain astream to reach interrupt
    interrupt_value = None
    async for stream_type, data in agent.astream(
        {"messages": [("human", "call mutating_tool")]},
        config=config,
        stream_mode=["updates"],
    ):
        if stream_type == "updates" and "__interrupt__" in data:
            interrupt_value = data["__interrupt__"][0].value

    assert interrupt_value is not None, "Graph did not reach interrupt"
    assert interrupt_value["action_requests"][0]["name"] == "mutating_tool"

    # Resume with approve — MongoDB checkpoint must be readable on same thread_id
    tool_executed = False
    async for stream_type, data in agent.astream(
        Command(resume={"decisions": [{"type": "approve"}]}),
        config=config,
        stream_mode=["updates"],
    ):
        if stream_type == "updates":
            for node_name, updates in data.items():
                if node_name == "tools":
                    for msg in updates.get("messages", []):
                        if "applied: x" in str(getattr(msg, "content", "")):
                            tool_executed = True

    assert tool_executed, "Tool did not execute after approve resume"
