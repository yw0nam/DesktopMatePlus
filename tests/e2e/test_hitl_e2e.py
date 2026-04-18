"""E2E tests for Human-in-the-Loop (HitL) WebSocket flow.

Requires: FASTAPI_URL env var pointing to a running backend.
    FASTAPI_URL=http://127.0.0.1:7123 uv run pytest -m e2e tests/e2e/test_hitl_e2e.py --tb=long

Tests cover:
  - hitl_response without pending approval (protocol error)
  - hitl_response before authorization (auth error)
  - Normal chat without tool calls (no hitl_request, flow unchanged)
  - Safe built-in tool bypass (no hitl_request for non-dangerous tools)
  - write_file approve / reject / edit flows
  - Multi parallel tool calls with mixed decisions
  - decisions count mismatch (4004 error + retry)
"""

import asyncio
import json
from pathlib import Path

import pytest
import websockets
import yaml

TOKEN = "demo-token"
AGENT_ID = "e2e-hitl-agent"
USER_ID = "e2e-hitl-user"
PERSONA_ID = "yuri"
CONNECT_TIMEOUT = 10
RECV_TIMEOUT = 90.0

# Simple greeting that should NOT trigger any dangerous tool
SAFE_CHAT_PROMPT = "안녕! 한 문장으로 짧게 인사해줘."

# Prompt that should trigger a built-in safe tool (memory search)
SAFE_TOOL_PROMPT = "내 기억에서 '취미'에 대해 검색해줘. search_memory 도구를 사용해."


def _filesystem_root_from_yaml() -> Path:
    """Read the filesystem_root_dir from services.e2e.yml."""
    cfg = yaml.safe_load(Path("yaml_files/services.e2e.yml").read_text())
    return Path(cfg["llm_config"]["configs"]["filesystem_root_dir"])


@pytest.fixture(autouse=True, scope="module")
def _cleanup_e2e_files():
    """Ensure sandbox exists before tests and clean up known artifacts after."""
    root = _filesystem_root_from_yaml()
    root.mkdir(parents=True, exist_ok=True)
    yield
    if root.exists():
        for name in (
            "e2e_approve.txt",
            "reject_e2e.txt",
            "edited_name.txt",
            "wrong_name.txt",
            "multi1.txt",
            "multi2.txt",
            "mismatch_e2e.txt",
        ):
            (root / name).unlink(missing_ok=True)


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
                        "decisions": [{"type": "approve"}],
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
                        "decisions": [{"type": "approve"}],
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
class TestHitLBuiltinFlow:
    """Built-in HumanInTheLoopMiddleware-backed HitL matrix."""

    async def test_normal_chat_no_hitl_request(self, e2e_session):
        """Normal chat without tool calls produces no hitl_request events."""
        ws = await _connect_and_authorize(e2e_session["ws_url"])
        try:
            await ws.send(_send_chat(SAFE_CHAT_PROMPT))
            events = await _collect_until_terminal(ws)
            assert "hitl_request" not in [e["type"] for e in events]
            assert any(e["type"] == "stream_end" for e in events)
        finally:
            await ws.close()

    async def test_safe_tool_no_hitl_request(self, e2e_session):
        """Built-in safe tool calls (e.g. search_memory) bypass HitL gate."""
        ws = await _connect_and_authorize(e2e_session["ws_url"])
        try:
            await ws.send(_send_chat(SAFE_TOOL_PROMPT))
            events = await _collect_until_terminal(ws)
            if "hitl_request" in [e["type"] for e in events]:
                pytest.skip("LLM chose an MCP/dangerous tool instead of search_memory")
            assert any(e["type"] == "stream_end" for e in events)
        finally:
            await ws.close()

    async def test_write_file_approve(self, e2e_session):
        """Approve a write_file tool call and verify the file is written."""
        ws = await _connect_and_authorize(e2e_session["ws_url"])
        try:
            prompt = (
                "Please write 'hello-e2e' to a file named e2e_approve.txt "
                "using write_file."
            )
            await ws.send(_send_chat(prompt))
            events = await _collect_until_terminal(ws)
            hitl = next((e for e in events if e["type"] == "hitl_request"), None)
            if hitl is None:
                pytest.skip("LLM did not choose write_file")
            assert len(hitl["action_requests"]) == 1
            assert hitl["action_requests"][0]["name"] == "write_file"

            await ws.send(
                json.dumps(
                    {
                        "type": "hitl_response",
                        "decisions": [{"type": "approve"}],
                    }
                )
            )
            final = await _collect_until_terminal(
                ws, terminal_types={"stream_end", "error"}
            )
            assert any(e["type"] == "stream_end" for e in final)

            sandbox = _filesystem_root_from_yaml() / "e2e_approve.txt"
            assert sandbox.exists()
            assert "hello-e2e" in sandbox.read_text()
            sandbox.unlink(missing_ok=True)
        finally:
            await ws.close()

    async def test_write_file_reject_with_message(self, e2e_session):
        """Reject a write_file tool call with a message; file must not exist."""
        ws = await _connect_and_authorize(e2e_session["ws_url"])
        try:
            prompt = "Please write 'x' to reject_e2e.txt using write_file."
            await ws.send(_send_chat(prompt))
            events = await _collect_until_terminal(ws)
            hitl = next((e for e in events if e["type"] == "hitl_request"), None)
            if hitl is None:
                pytest.skip("LLM did not choose write_file")

            await ws.send(
                json.dumps(
                    {
                        "type": "hitl_response",
                        "decisions": [{"type": "reject", "message": "path is unsafe"}],
                    }
                )
            )
            final = await _collect_until_terminal(
                ws, terminal_types={"stream_end", "error"}
            )
            # Agent handles rejection with alternate response — LLM-dependent
            if not any(e["type"] == "stream_end" for e in final):
                pytest.skip(
                    "LLM did not produce stream_end after rejection (nondeterministic)"
                )

            sandbox = _filesystem_root_from_yaml() / "reject_e2e.txt"
            assert not sandbox.exists()
        finally:
            await ws.close()

    async def test_write_file_edit(self, e2e_session):
        """Edit a write_file tool call's arguments before executing."""
        ws = await _connect_and_authorize(e2e_session["ws_url"])
        try:
            prompt = "Please write 'yuri' to wrong_name.txt using write_file."
            await ws.send(_send_chat(prompt))
            events = await _collect_until_terminal(ws)
            hitl = next((e for e in events if e["type"] == "hitl_request"), None)
            if hitl is None:
                pytest.skip("LLM did not choose write_file")

            edited_args = dict(hitl["action_requests"][0]["arguments"])
            edited_args["file_path"] = "edited_name.txt"
            await ws.send(
                json.dumps(
                    {
                        "type": "hitl_response",
                        "decisions": [
                            {
                                "type": "edit",
                                "edited_action": {
                                    "name": "write_file",
                                    "args": edited_args,
                                },
                            }
                        ],
                    }
                )
            )
            final = await _collect_until_terminal(
                ws, terminal_types={"stream_end", "error"}
            )
            assert any(e["type"] == "stream_end" for e in final)

            root = _filesystem_root_from_yaml()
            assert (root / "edited_name.txt").exists()
            assert not (root / "wrong_name.txt").exists()
            (root / "edited_name.txt").unlink(missing_ok=True)
        finally:
            await ws.close()

    async def test_multi_parallel_tool_calls(self, e2e_session):
        """Mixed approve/reject decisions for 2 parallel write_file calls."""
        ws = await _connect_and_authorize(e2e_session["ws_url"])
        try:
            prompt = (
                "In one turn, call write_file to create multi1.txt='a' AND "
                "write_file to create multi2.txt='b'. "
                "Both calls in a single response."
            )
            await ws.send(_send_chat(prompt))
            events = await _collect_until_terminal(ws)
            hitl = next((e for e in events if e["type"] == "hitl_request"), None)
            if hitl is None or len(hitl["action_requests"]) != 2:
                pytest.skip("LLM did not emit 2 parallel tool calls")

            await ws.send(
                json.dumps(
                    {
                        "type": "hitl_response",
                        "decisions": [
                            {"type": "approve"},
                            {"type": "reject", "message": "skip second"},
                        ],
                    }
                )
            )
            final = await _collect_until_terminal(
                ws, terminal_types={"stream_end", "error"}
            )
            assert any(e["type"] == "stream_end" for e in final)

            root = _filesystem_root_from_yaml()
            assert (root / "multi1.txt").exists()
            assert not (root / "multi2.txt").exists()
            (root / "multi1.txt").unlink(missing_ok=True)
        finally:
            await ws.close()

    async def test_decisions_count_mismatch_returns_error(self, e2e_session):
        """Sending wrong-sized decisions list returns 4004 error and allows retry."""
        ws = await _connect_and_authorize(e2e_session["ws_url"])
        try:
            prompt = "Please write 'x' to mismatch_e2e.txt using write_file."
            await ws.send(_send_chat(prompt))
            events = await _collect_until_terminal(ws)
            hitl = next((e for e in events if e["type"] == "hitl_request"), None)
            if hitl is None:
                pytest.skip("LLM did not choose write_file")
            assert len(hitl["action_requests"]) == 1

            # Send 0 decisions — mismatch
            await ws.send(
                json.dumps(
                    {
                        "type": "hitl_response",
                        "decisions": [],
                    }
                )
            )
            err = await _recv_skip_ping(ws, timeout=15.0)
            assert err["type"] == "error"
            assert err.get("code") == 4004

            # Retry with correct count
            await ws.send(
                json.dumps(
                    {
                        "type": "hitl_response",
                        "decisions": [{"type": "reject"}],
                    }
                )
            )
            final = await _collect_until_terminal(
                ws, terminal_types={"stream_end", "error"}
            )
            assert any(e["type"] == "stream_end" for e in final)

            (_filesystem_root_from_yaml() / "mismatch_e2e.txt").unlink(missing_ok=True)
        finally:
            await ws.close()
