"""Tests for OpenAIChatAgent __interrupt__ parsing (built-in HITL shape)."""

from types import SimpleNamespace

import pytest


class _FakeAgent:
    def __init__(self, chunks):
        self._chunks = chunks

    def astream(self, *_, **__):
        async def gen():
            for c in self._chunks:
                yield c

        return gen()


@pytest.mark.asyncio
async def test_interrupt_single_action_request_forwarded_as_list():
    from src.services.agent_service.openai_chat_agent import OpenAIChatAgent

    interrupt_value = {
        "action_requests": [
            {
                "name": "write_file",
                "args": {"file_path": "a.txt"},
                "description": "desc",
            },
        ],
        "review_configs": [
            {
                "action_name": "write_file",
                "allowed_decisions": ["approve", "edit", "reject"],
            },
        ],
    }
    chunks = [
        ("updates", {"__interrupt__": [SimpleNamespace(value=interrupt_value)]}),
    ]
    agent = OpenAIChatAgent.__new__(OpenAIChatAgent)
    agent.agent = _FakeAgent(chunks)

    events = []
    async for ev in agent._consume_astream(_FakeAgent(chunks).astream(), "s1"):
        events.append(ev)

    assert len(events) == 1
    assert events[0]["type"] == "hitl_request"
    assert events[0]["session_id"] == "s1"
    assert events[0]["action_requests"] == interrupt_value["action_requests"]
    assert events[0]["review_configs"] == interrupt_value["review_configs"]


@pytest.mark.asyncio
async def test_interrupt_multi_action_requests_preserve_order():
    from src.services.agent_service.openai_chat_agent import OpenAIChatAgent

    interrupt_value = {
        "action_requests": [
            {
                "name": "write_file",
                "args": {"file_path": "a"},
                "description": "d1",
            },
            {
                "name": "file_delete",
                "args": {"file_path": "b"},
                "description": "d2",
            },
        ],
        "review_configs": [
            {"action_name": "write_file", "allowed_decisions": ["approve", "reject"]},
            {"action_name": "file_delete", "allowed_decisions": ["approve", "reject"]},
        ],
    }
    chunks = [("updates", {"__interrupt__": [SimpleNamespace(value=interrupt_value)]})]
    agent = OpenAIChatAgent.__new__(OpenAIChatAgent)

    events = []
    async for ev in agent._consume_astream(_FakeAgent(chunks).astream(), "s2"):
        events.append(ev)

    assert events[0]["action_requests"][0]["name"] == "write_file"
    assert events[0]["action_requests"][1]["name"] == "file_delete"


def test_build_interrupt_on_matrix():
    from src.services.agent_service.openai_chat_agent import _build_interrupt_on

    mcp_names = {"mcp_tool_a", "mcp_tool_b"}
    matrix = _build_interrupt_on(mcp_names)

    # MCP + delegate_task + FS mutating — all True
    for name in mcp_names | {
        "delegate_task",
        "write_file",
        "copy_file",
        "move_file",
        "file_delete",
        "edit_file",
    }:
        assert matrix[name] is True

    # safe tools not in matrix
    for name in {"read_file", "list_directory", "file_search"}:
        assert name not in matrix


@pytest.mark.asyncio
async def test_resume_after_approval_uses_command_with_decisions():
    from langgraph.types import Command

    from src.services.agent_service.openai_chat_agent import OpenAIChatAgent

    agent = OpenAIChatAgent.__new__(OpenAIChatAgent)

    captured: dict = {}

    class _Fake:
        def astream(self, resume_value, *, config, stream_mode, context):
            captured["resume_value"] = resume_value
            captured["config"] = config

            async def gen():
                if False:
                    yield

            return gen()

    agent.agent = _Fake()

    events = []
    async for ev in agent.resume_after_approval(
        session_id="s1",
        decisions=[{"type": "approve"}, {"type": "reject", "message": "x"}],
    ):
        events.append(ev)

    assert isinstance(captured["resume_value"], Command)
    assert captured["resume_value"].resume == {
        "decisions": [{"type": "approve"}, {"type": "reject", "message": "x"}]
    }
    assert captured["config"]["configurable"] == {"thread_id": "s1"}
