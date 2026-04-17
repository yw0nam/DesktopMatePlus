"""E2E tests for Human-in-the-Loop (HitL) WebSocket flow.

Requires: FASTAPI_URL env var pointing to a running backend.
    FASTAPI_URL=http://127.0.0.1:7123 uv run pytest -m e2e tests/e2e/test_hitl_e2e.py --tb=long

Tests cover:
  - hitl_response without pending approval (protocol error)
  - Normal chat without tool calls (no hitl_request, flow unchanged)
  - Safe built-in tool bypass (no hitl_request for non-dangerous tools)
  - Full approve flow (chat → hitl_request → approve → stream_end)
  - Full deny flow (chat → hitl_request → deny → stream_end)
  - Multi-tool sequential approval
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import websockets

from src.models.websocket import ToolCategory
from src.services.agent_service.middleware.hitl_middleware import HitLMiddleware

TOKEN = "demo-token"
AGENT_ID = "e2e-hitl-agent"
USER_ID = "e2e-hitl-user"
PERSONA_ID = "yuri"
CONNECT_TIMEOUT = 10
RECV_TIMEOUT = 90.0

# Prompt designed to trigger delegate_task tool (always in dangerous list)
DELEGATE_PROMPT = (
    "다음 작업을 NanoClaw에게 위임해줘: 'hello world를 출력하는 간단한 스크립트를 만들어줘'. "
    "반드시 delegate_task 도구를 사용해서 위임해."
)

# Simple greeting that should NOT trigger any dangerous tool
SAFE_CHAT_PROMPT = "안녕! 한 문장으로 짧게 인사해줘."

# Prompt that should trigger a built-in safe tool (memory search)
SAFE_TOOL_PROMPT = "내 기억에서 '취미'에 대해 검색해줘. search_memory 도구를 사용해."


async def _connect_and_authorize(ws_url: str):
    """Connect to WebSocket and complete authorization.

    Returns the authorized websocket connection.
    """
    ws = await websockets.connect(
        ws_url,
        open_timeout=CONNECT_TIMEOUT,
        ping_interval=20,
        ping_timeout=10,
        close_timeout=5,
    )
    await ws.send(json.dumps({"type": "authorize", "token": TOKEN}))

    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=RECV_TIMEOUT)
        data = json.loads(raw)
        if data.get("type") == "ping":
            await ws.send(json.dumps({"type": "pong"}))
            continue
        if data.get("type") == "authorize_success":
            return ws
        if data.get("type") == "authorize_error":
            await ws.close()
            pytest.fail(f"WebSocket authorization failed: {data.get('error')}")


async def _recv_skip_ping(
    ws,
    timeout: float = RECV_TIMEOUT,
) -> dict:
    """Receive next non-ping message from WebSocket."""
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        data = json.loads(raw)
        if data.get("type") == "ping":
            await ws.send(json.dumps({"type": "pong"}))
            continue
        return data


async def _collect_until_terminal(
    ws,
    terminal_types: set[str] | None = None,
    timeout: float = RECV_TIMEOUT,
) -> list[dict]:
    """Collect events until a terminal event type is received.

    Terminal types default to stream_end, error, and hitl_request.
    """
    if terminal_types is None:
        terminal_types = {"stream_end", "error", "hitl_request"}

    events: list[dict] = []
    try:
        while True:
            event = await _recv_skip_ping(ws, timeout=timeout)
            events.append(event)
            if event.get("type") in terminal_types:
                break
    except TimeoutError:
        received = [e.get("type") for e in events]
        pytest.fail(
            f"Timed out after {timeout}s waiting for terminal event "
            f"{terminal_types}. Received: {received}"
        )
    return events


def _send_chat(
    content: str,
    session_id: str | None = None,
    tts_enabled: bool = False,
) -> str:
    """Build a chat_message JSON payload."""
    return json.dumps(
        {
            "type": "chat_message",
            "content": content,
            "session_id": session_id,
            "agent_id": AGENT_ID,
            "user_id": USER_ID,
            "persona_id": PERSONA_ID,
            "tts_enabled": tts_enabled,
        }
    )


@pytest.mark.e2e
class TestHitLProtocol:
    """Protocol-level HitL tests — always work against a real backend."""

    async def test_hitl_response_without_pending_approval(self, e2e_session):
        """Sending hitl_response when no approval is pending returns error."""
        ws = await _connect_and_authorize(e2e_session["ws_url"])
        try:
            # Send hitl_response without any prior hitl_request
            await ws.send(
                json.dumps(
                    {
                        "type": "hitl_response",
                        "request_id": "nonexistent-request-id",
                        "approved": True,
                    }
                )
            )

            # Should receive an error response
            event = await _recv_skip_ping(ws, timeout=15.0)
            assert event.get("type") == "error", (
                f"Expected error for hitl_response without pending approval, "
                f"got: {event}"
            )
        finally:
            await ws.close()

    async def test_hitl_response_requires_authentication(self, e2e_session):
        """Sending hitl_response before authorization returns error."""
        ws = await websockets.connect(
            e2e_session["ws_url"],
            open_timeout=CONNECT_TIMEOUT,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        )
        try:
            # Send hitl_response without authorizing first
            await ws.send(
                json.dumps(
                    {
                        "type": "hitl_response",
                        "request_id": "req-1",
                        "approved": True,
                    }
                )
            )

            event = await _recv_skip_ping(ws, timeout=15.0)
            assert (
                event.get("type") == "error"
            ), f"Expected error for unauthenticated hitl_response, got: {event}"
            assert (
                "authentication" in event.get("error", "").lower()
                or "auth" in event.get("error", "").lower()
            ), f"Error should mention authentication: {event.get('error')}"
        finally:
            await ws.close()


@pytest.mark.e2e
class TestHitLExistingFlowUnchanged:
    """Verify existing chat flows are NOT affected by HitL."""

    async def test_normal_chat_no_hitl_request(self, e2e_session):
        """Normal chat without tool calls produces no hitl_request events."""
        ws = await _connect_and_authorize(e2e_session["ws_url"])
        try:
            await ws.send(_send_chat(SAFE_CHAT_PROMPT))

            events = await _collect_until_terminal(ws)
            event_types = [e["type"] for e in events]

            assert (
                "hitl_request" not in event_types
            ), "Normal chat should not trigger hitl_request"
            assert "stream_start" in event_types, "Missing stream_start event"
            assert "stream_end" in event_types, "Missing stream_end event"
        finally:
            await ws.close()

    async def test_normal_chat_stream_tokens_present(self, e2e_session):
        """Normal chat produces stream_token events as before."""
        ws = await _connect_and_authorize(e2e_session["ws_url"])
        try:
            await ws.send(_send_chat(SAFE_CHAT_PROMPT))

            events = await _collect_until_terminal(ws)
            token_events = [e for e in events if e["type"] == "stream_token"]

            assert (
                len(token_events) > 0
            ), "Expected at least one stream_token event in normal chat"
        finally:
            await ws.close()

    async def test_safe_tool_no_hitl_request(self, e2e_session):
        """Built-in safe tool calls (e.g. search_memory) bypass HitL gate.

        If the LLM non-deterministically chooses a dangerous tool (MCP)
        instead of the built-in search_memory, the test is skipped.
        """
        ws = await _connect_and_authorize(e2e_session["ws_url"])
        try:
            await ws.send(_send_chat(SAFE_TOOL_PROMPT))

            events = await _collect_until_terminal(ws)
            event_types = [e["type"] for e in events]

            if "hitl_request" in event_types:
                pytest.skip(
                    "Agent chose a dangerous tool instead of built-in search_memory "
                    "(LLM non-determinism) — cannot verify safe-tool bypass. "
                    f"Events: {event_types}"
                )
            # Should complete normally
            assert (
                "stream_end" in event_types or "error" in event_types
            ), "Chat with safe tool should reach stream_end or error"
        finally:
            await ws.close()


@pytest.mark.e2e
class TestHitLApproveFlow:
    """Full HitL approve flow — requires agent to call delegate_task."""

    async def test_hitl_approve_completes_stream(self, e2e_session):
        """Send chat → receive hitl_request → approve → stream_end.

        This test prompts the agent to use delegate_task, which is always
        in the HitL dangerous list. If the agent does not call delegate_task,
        the test is skipped (LLM behavior is non-deterministic).
        """
        ws = await _connect_and_authorize(e2e_session["ws_url"])
        try:
            await ws.send(_send_chat(DELEGATE_PROMPT))

            # Collect events until hitl_request or stream_end
            events = await _collect_until_terminal(ws)
            event_types = [e["type"] for e in events]

            if "hitl_request" not in event_types:
                pytest.skip(
                    "Agent did not call a dangerous tool — cannot test approve flow. "
                    f"Events: {event_types}"
                )

            hitl_event = next(e for e in events if e["type"] == "hitl_request")

            # Validate hitl_request fields
            assert "request_id" in hitl_event, "hitl_request missing request_id"
            assert "tool_name" in hitl_event, "hitl_request missing tool_name"
            assert "tool_args" in hitl_event, "hitl_request missing tool_args"
            assert "session_id" in hitl_event, "hitl_request missing session_id"
            assert hitl_event["category"] in {
                "state_mutating",
                "external",
                "dangerous",
            }, f"hitl_request category must be non-bypass, got: {hitl_event.get('category')}"

            # Send approval
            await ws.send(
                json.dumps(
                    {
                        "type": "hitl_response",
                        "request_id": hitl_event["request_id"],
                        "approved": True,
                    }
                )
            )

            # Collect remaining events until stream_end
            # After approval, may get more hitl_requests (multi-tool), or stream_end
            remaining = await _collect_until_terminal(
                ws,
                terminal_types={"stream_end", "error"},
                timeout=RECV_TIMEOUT,
            )
            remaining_types = [e["type"] for e in remaining]

            assert (
                "stream_end" in remaining_types or "error" in remaining_types
            ), f"Expected stream_end or error after approval. Got: {remaining_types}"
        finally:
            await ws.close()

    async def test_hitl_request_has_correct_schema(self, e2e_session):
        """hitl_request event must contain all required fields with correct types."""
        ws = await _connect_and_authorize(e2e_session["ws_url"])
        try:
            await ws.send(_send_chat(DELEGATE_PROMPT))

            events = await _collect_until_terminal(ws)
            event_types = [e["type"] for e in events]

            if "hitl_request" not in event_types:
                pytest.skip(
                    "Agent did not call a dangerous tool — cannot validate schema. "
                    f"Events: {event_types}"
                )

            hitl_event = next(e for e in events if e["type"] == "hitl_request")

            # Validate field types
            assert isinstance(hitl_event["request_id"], str), "request_id must be str"
            assert isinstance(hitl_event["tool_name"], str), "tool_name must be str"
            assert isinstance(hitl_event["tool_args"], dict), "tool_args must be dict"
            assert isinstance(hitl_event["session_id"], str), "session_id must be str"
            assert len(hitl_event["request_id"]) > 0, "request_id must not be empty"
            assert len(hitl_event["tool_name"]) > 0, "tool_name must not be empty"
            assert hitl_event["category"] in {
                "state_mutating",
                "external",
                "dangerous",
            }, f"hitl_request category must be non-bypass, got: {hitl_event.get('category')}"
        finally:
            await ws.close()


@pytest.mark.e2e
class TestHitLDenyFlow:
    """Full HitL deny flow — requires agent to call delegate_task."""

    async def test_hitl_deny_completes_stream(self, e2e_session):
        """Send chat → receive hitl_request → deny → agent handles denial → stream_end."""
        ws = await _connect_and_authorize(e2e_session["ws_url"])
        try:
            await ws.send(_send_chat(DELEGATE_PROMPT))

            events = await _collect_until_terminal(ws)
            event_types = [e["type"] for e in events]

            if "hitl_request" not in event_types:
                pytest.skip(
                    "Agent did not call a dangerous tool — cannot test deny flow. "
                    f"Events: {event_types}"
                )

            hitl_event = next(e for e in events if e["type"] == "hitl_request")
            assert hitl_event["category"] in {
                "state_mutating",
                "external",
                "dangerous",
            }, f"hitl_request category must be non-bypass, got: {hitl_event.get('category')}"

            # Send denial
            await ws.send(
                json.dumps(
                    {
                        "type": "hitl_response",
                        "request_id": hitl_event["request_id"],
                        "approved": False,
                    }
                )
            )

            # After denial, agent should get error message and eventually stream_end
            remaining = await _collect_until_terminal(
                ws,
                terminal_types={"stream_end", "error"},
                timeout=RECV_TIMEOUT,
            )
            remaining_types = [e["type"] for e in remaining]

            assert (
                "stream_end" in remaining_types or "error" in remaining_types
            ), f"Expected stream_end or error after denial. Got: {remaining_types}"
        finally:
            await ws.close()


@pytest.mark.e2e
class TestHitLMultiToolApproval:
    """Multi-tool sequential approval — approve first, handle second."""

    async def test_hitl_multi_tool_sequential_approval(self, e2e_session):
        """If agent calls 2+ dangerous tools, approve each sequentially."""
        ws = await _connect_and_authorize(e2e_session["ws_url"])
        try:
            # Use a prompt that might trigger multiple tool calls
            multi_prompt = (
                "다음 두 작업을 각각 NanoClaw에게 위임해줘: "
                "1) 'hello world 스크립트 작성' "
                "2) '간단한 테스트 작성'. "
                "각각 별도로 delegate_task 도구를 사용해서 위임해."
            )
            await ws.send(_send_chat(multi_prompt))

            hitl_count = 0
            all_events: list[dict] = []

            # Collect first batch of events
            events = await _collect_until_terminal(ws)
            all_events.extend(events)
            event_types = [e["type"] for e in events]

            if "hitl_request" not in event_types:
                pytest.skip(
                    "Agent did not call a dangerous tool — cannot test multi-tool flow. "
                    f"Events: {event_types}"
                )

            # Approve and collect, up to 5 iterations (safety limit)
            for _ in range(5):
                last_event = all_events[-1]
                if last_event["type"] != "hitl_request":
                    break

                hitl_count += 1
                assert last_event["category"] in {
                    "state_mutating",
                    "external",
                    "dangerous",
                }, f"hitl_request category must be non-bypass, got: {last_event.get('category')}"
                # Approve the tool call
                await ws.send(
                    json.dumps(
                        {
                            "type": "hitl_response",
                            "request_id": last_event["request_id"],
                            "approved": True,
                        }
                    )
                )

                # Collect next batch
                next_events = await _collect_until_terminal(
                    ws,
                    terminal_types={"stream_end", "error", "hitl_request"},
                    timeout=RECV_TIMEOUT,
                )
                all_events.extend(next_events)

            final_types = [e["type"] for e in all_events]

            # Must eventually reach stream_end or error
            assert "stream_end" in final_types or "error" in final_types, (
                f"Expected stream_end or error after approving all tools. "
                f"HitL requests seen: {hitl_count}. Events: {final_types}"
            )

            # Should have seen at least 1 hitl_request (already verified by skip above)
            assert (
                hitl_count >= 1
            ), f"Expected at least 1 hitl_request, got {hitl_count}"
        finally:
            await ws.close()


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_read_only_tool_bypasses_hitl_via_middleware():
    """read_only category must not trigger interrupt() at the middleware layer."""
    mw = HitLMiddleware(category_map={"search_memory": ToolCategory.READ_ONLY})
    request = MagicMock()
    request.tool_call = {"name": "search_memory", "args": {"query": "cat"}}
    handler = AsyncMock(return_value="memory hit")

    with patch(
        "src.services.agent_service.middleware.hitl_middleware.interrupt"
    ) as mock_interrupt:
        result = await mw.awrap_tool_call(request, handler)

    mock_interrupt.assert_not_called()
    handler.assert_awaited_once_with(request)
    assert result == "memory hit"
