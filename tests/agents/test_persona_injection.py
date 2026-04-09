"""Tests for persona injection via is_new_session flag.

Root cause: handlers.py generates session_id = str(uuid4()) BEFORE calling
agent_service.stream(), so by the time stream() is called session_id is always
set, making the old `not session_id` condition always False — persona never injected.

Fix: add is_new_session: bool = False parameter; handlers captures the flag
BEFORE UUID generation.
"""

from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage, SystemMessage

from src.services.agent_service.openai_chat_agent import OpenAIChatAgent


def _agent():
    with patch("src.services.agent_service.openai_chat_agent.ChatOpenAI"):
        svc = OpenAIChatAgent(
            temperature=0.7, top_p=0.9, openai_api_key="sk-test", model_name="gpt-4o"
        )
    svc.agent = MagicMock()
    svc._personas = {"yuri": "You are Yuri."}
    return svc


async def _drain(gen):
    results = []
    async for item in gen:
        results.append(item)
    return results


# ── stream() tests ────────────────────────────────────────────────────────────


async def test_stream_injects_persona_when_is_new_session_true():
    """When is_new_session=True and persona_id matches, SystemMessage is prepended."""
    svc = _agent()
    captured: dict = {}

    async def fake_astream(input, config=None, context=None, **kw):
        captured["messages"] = input.get("messages", [])
        return
        yield  # make it an async generator

    svc.agent.astream = fake_astream

    await _drain(
        svc.stream(
            messages=[HumanMessage("hi")],
            session_id="abc-123",
            persona_id="yuri",
            is_new_session=True,
        )
    )

    assert captured["messages"], "Expected messages to be captured"
    assert isinstance(
        captured["messages"][0], SystemMessage
    ), "First message must be SystemMessage when is_new_session=True"
    assert "You are Yuri." in captured["messages"][0].content


async def test_stream_does_not_inject_persona_when_is_new_session_false():
    """When is_new_session=False (continuing session), no SystemMessage is prepended."""
    svc = _agent()
    captured: dict = {}

    async def fake_astream(input, config=None, context=None, **kw):
        captured["messages"] = input.get("messages", [])
        return
        yield

    svc.agent.astream = fake_astream

    await _drain(
        svc.stream(
            messages=[HumanMessage("hi")],
            session_id="abc-123",
            persona_id="yuri",
            is_new_session=False,
        )
    )

    types = [type(m).__name__ for m in captured["messages"]]
    assert (
        "SystemMessage" not in types
    ), "SystemMessage must NOT be injected when is_new_session=False"


async def test_stream_does_not_inject_persona_when_persona_id_unknown():
    """When is_new_session=True but persona_id not in personas dict, no SystemMessage."""
    svc = _agent()
    captured: dict = {}

    async def fake_astream(input, config=None, context=None, **kw):
        captured["messages"] = input.get("messages", [])
        return
        yield

    svc.agent.astream = fake_astream

    await _drain(
        svc.stream(
            messages=[HumanMessage("hi")],
            session_id="abc-123",
            persona_id="unknown_persona",
            is_new_session=True,
        )
    )

    types = [type(m).__name__ for m in captured["messages"]]
    assert (
        "SystemMessage" not in types
    ), "SystemMessage must NOT be injected when persona_id is unknown"


# ── invoke() tests ────────────────────────────────────────────────────────────


async def test_invoke_injects_persona_when_is_new_session_true():
    """invoke(): when is_new_session=True and persona_id matches, SystemMessage is prepended."""
    svc = _agent()
    captured: dict = {}

    async def fake_ainvoke(input, config=None, context=None, **kw):
        captured["messages"] = input.get("messages", [])
        return {"messages": [MagicMock(content="reply")]}

    svc.agent.ainvoke = fake_ainvoke

    await svc.invoke(
        messages=[HumanMessage("hi")],
        session_id="abc-123",
        persona_id="yuri",
        is_new_session=True,
    )

    assert captured["messages"], "Expected messages to be captured"
    assert isinstance(
        captured["messages"][0], SystemMessage
    ), "First message must be SystemMessage when is_new_session=True in invoke()"
    assert "You are Yuri." in captured["messages"][0].content


async def test_invoke_does_not_inject_persona_when_is_new_session_false():
    """invoke(): when is_new_session=False (continuing session), no SystemMessage."""
    svc = _agent()
    captured: dict = {}

    async def fake_ainvoke(input, config=None, context=None, **kw):
        captured["messages"] = input.get("messages", [])
        return {"messages": [MagicMock(content="reply")]}

    svc.agent.ainvoke = fake_ainvoke

    await svc.invoke(
        messages=[HumanMessage("hi")],
        session_id="abc-123",
        persona_id="yuri",
        is_new_session=False,
    )

    types = [type(m).__name__ for m in captured["messages"]]
    assert (
        "SystemMessage" not in types
    ), "SystemMessage must NOT be injected when is_new_session=False in invoke()"


async def test_invoke_does_not_inject_persona_when_persona_id_unknown():
    """invoke(): when is_new_session=True but persona_id not in personas dict, no SystemMessage."""
    svc = _agent()
    captured: dict = {}

    async def fake_ainvoke(input, config=None, context=None, **kw):
        captured["messages"] = input.get("messages", [])
        return {"messages": [MagicMock(content="reply")]}

    svc.agent.ainvoke = fake_ainvoke

    await svc.invoke(
        messages=[HumanMessage("hi")],
        session_id="abc-123",
        persona_id="unknown_persona",
        is_new_session=True,
    )

    types = [type(m).__name__ for m in captured["messages"]]
    assert (
        "SystemMessage" not in types
    ), "SystemMessage must NOT be injected when persona_id is unknown in invoke()"
