from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import HumanMessage

from src.services.agent_service.openai_chat_agent import OpenAIChatAgent


def _agent():
    with patch("src.services.agent_service.openai_chat_agent.ChatOpenAI"):
        svc = OpenAIChatAgent(
            temperature=0.7, top_p=0.9, openai_api_key="sk-test", model_name="gpt-4o"
        )
    svc.agent = MagicMock()
    return svc


async def _drain(gen):
    results = []
    async for item in gen:
        results.append(item)
    return results


async def test_stream_uses_thread_id():
    svc = _agent()
    captured = {}

    async def capturing_astream(input, config=None, context=None, **kw):
        captured["config"] = config
        captured["context"] = context
        return
        yield  # make it a generator

    svc.agent.astream = capturing_astream
    await _drain(svc.stream(messages=[HumanMessage("hi")], session_id="s1"))
    assert captured["config"]["configurable"]["thread_id"] == "s1"
    assert "session_id" not in captured["config"]["configurable"]


async def test_stream_passes_context():
    svc = _agent()
    captured = {}

    async def capturing_astream(input, config=None, context=None, **kw):
        captured["context"] = context
        return
        yield

    svc.agent.astream = capturing_astream
    rc = {"provider": "slack", "channel_id": "C1"}
    await _drain(
        svc.stream(
            messages=[HumanMessage("hi")],
            session_id="s1",
            context={"reply_channel": rc},
        )
    )
    assert captured["context"] == {"reply_channel": rc}


async def test_invoke_uses_thread_id():
    svc = _agent()
    svc.agent.ainvoke = AsyncMock(
        return_value={"messages": [MagicMock(content="reply")]}
    )
    await svc.invoke(messages=[HumanMessage("hi")], session_id="s2")

    config = (
        svc.agent.ainvoke.call_args.kwargs.get("config")
        or svc.agent.ainvoke.call_args[1]
    )
    assert config["configurable"]["thread_id"] == "s2"
    assert "session_id" not in config["configurable"]


async def test_stream_injects_persona_only_for_new_session():
    """Persona SystemMessage must NOT be prepended when session_id is set (continuing session)."""

    svc = _agent()
    svc._personas = {"yuri": "You are Yuri."}
    captured_messages = {}

    async def capturing_astream(input, config=None, context=None, **kw):
        captured_messages["messages"] = input.get("messages", [])
        return
        yield

    svc.agent.astream = capturing_astream

    # Continuing session: session_id is set — persona must NOT be prepended
    await _drain(
        svc.stream(
            messages=[HumanMessage("hi")],
            session_id="existing-session",
            persona_id="yuri",
        )
    )
    types = [type(m).__name__ for m in captured_messages["messages"]]
    assert (
        "SystemMessage" not in types
    ), "SystemMessage must not be injected for a continuing session"


async def test_stream_injects_persona_for_new_session():
    """Persona SystemMessage MUST be prepended when is_new_session=True."""
    from langchain_core.messages import SystemMessage

    svc = _agent()
    svc._personas = {"yuri": "You are Yuri."}
    captured_messages = {}

    async def capturing_astream(input, config=None, context=None, **kw):
        captured_messages["messages"] = input.get("messages", [])
        return
        yield

    svc.agent.astream = capturing_astream

    # New session: is_new_session=True — persona MUST be prepended
    await _drain(
        svc.stream(
            messages=[HumanMessage("hi")],
            session_id="abc-123",
            persona_id="yuri",
            is_new_session=True,
        )
    )
    assert captured_messages["messages"], "Expected messages to be captured"
    assert isinstance(
        captured_messages["messages"][0], SystemMessage
    ), "First message must be SystemMessage for a new session"


async def test_invoke_injects_persona_only_for_new_session():
    """invoke() must NOT inject persona SystemMessage for a continuing session (session_id set)."""

    svc = _agent()
    svc._personas = {"yuri": "You are Yuri."}
    captured_input = {}

    async def capturing_ainvoke(input, config=None, context=None, **kw):
        captured_input["messages"] = input.get("messages", [])
        return {"messages": [MagicMock(content="reply")]}

    svc.agent.ainvoke = capturing_ainvoke

    await svc.invoke(
        messages=[HumanMessage("hi")],
        session_id="existing-session",
        persona_id="yuri",
    )
    types = [type(m).__name__ for m in captured_input["messages"]]
    assert (
        "SystemMessage" not in types
    ), "SystemMessage must not be injected for a continuing session in invoke()"


async def test_invoke_injects_persona_for_new_session():
    """invoke() MUST inject persona SystemMessage when is_new_session=True."""
    from langchain_core.messages import SystemMessage

    svc = _agent()
    svc._personas = {"yuri": "You are Yuri."}
    captured_input = {}

    async def capturing_ainvoke(input, config=None, context=None, **kw):
        captured_input["messages"] = input.get("messages", [])
        return {"messages": [MagicMock(content="reply")]}

    svc.agent.ainvoke = capturing_ainvoke

    await svc.invoke(
        messages=[HumanMessage("hi")],
        session_id="abc-123",
        persona_id="yuri",
        is_new_session=True,
    )
    assert captured_input["messages"], "Expected messages to be captured"
    assert isinstance(
        captured_input["messages"][0], SystemMessage
    ), "First message must be SystemMessage for a new session in invoke()"
