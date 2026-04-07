"""E2E tests for WebSocket chat streaming endpoint.

Requires: FASTAPI_URL env var pointing to a running backend.
    FASTAPI_URL=http://127.0.0.1:7123 uv run pytest -m e2e tests/e2e/test_websocket_e2e.py --tb=long
"""

import asyncio
import json

import pytest
import websockets

TOKEN = "demo-token"
AGENT_ID = "e2e-agent"
USER_ID = "e2e-user"
PERSONA_ID = "yuri"
TURN1_MSG = "안녕! 한 문장으로 짧게 인사해줘."
TURN2_MSG = "방금 뭐라고 했어? 한 문장으로 다시 말해줘."
CONNECT_TIMEOUT = 10
RECV_TIMEOUT = 60.0


async def _run_ws_turn(
    ws_url: str,
    session_id: str | None,
    message: str,
    *,
    tts_enabled: bool = False,
) -> dict:
    """Run one WebSocket conversation turn and return collected events."""
    events: list[dict] = []
    captured_session_id: str | None = session_id
    authorized = False

    try:
        async with websockets.connect(
            ws_url,
            open_timeout=CONNECT_TIMEOUT,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        ) as ws:
            await ws.send(json.dumps({"type": "authorize", "token": TOKEN}))

            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=RECV_TIMEOUT)
                data = json.loads(raw)
                event_type = data.get("type")

                if event_type == "ping":
                    await ws.send(json.dumps({"type": "pong"}))
                    continue

                events.append(data)

                if event_type == "authorize_error":
                    pytest.fail(f"WebSocket authorization failed: {data.get('error')}")

                if event_type == "authorize_success" and not authorized:
                    authorized = True
                    payload = {
                        "type": "chat_message",
                        "content": message,
                        "session_id": session_id,
                        "agent_id": AGENT_ID,
                        "user_id": USER_ID,
                        "persona_id": PERSONA_ID,
                        "tts_enabled": tts_enabled,
                    }
                    await ws.send(json.dumps(payload))
                    continue

                if event_type == "stream_start":
                    captured_session_id = data.get("session_id") or captured_session_id
                    continue

                if event_type == "stream_end":
                    captured_session_id = data.get("session_id") or captured_session_id
                    break

                if event_type == "error":
                    pytest.fail(f"Backend returned error event: {data.get('error')}")

    except TimeoutError:
        received = [e.get("type") for e in events]
        pytest.fail(
            f"WebSocket timed out after {RECV_TIMEOUT}s waiting for stream_end. "
            f"session_id={captured_session_id!r}, events received: {received}"
        )

    return {"events": events, "session_id": captured_session_id}


@pytest.mark.e2e
class TestWebSocketE2E:
    async def test_full_ws_turn_stream_lifecycle(self, e2e_session):
        """Connect → authorize → send chat_message → verify stream_start/token/end."""
        result = await _run_ws_turn(e2e_session["ws_url"], None, TURN1_MSG)

        event_types = [e["type"] for e in result["events"]]

        assert "authorize_success" in event_types, "Missing authorize_success event"
        assert "stream_start" in event_types, "Missing stream_start event"
        assert "stream_end" in event_types, "Missing stream_end event"
        assert result["session_id"] is not None, "No session_id returned from server"

    async def test_stream_tokens_present(self, e2e_session):
        """Verify at least one stream_token is emitted during a turn."""
        result = await _run_ws_turn(e2e_session["ws_url"], None, TURN1_MSG)

        token_events = [e for e in result["events"] if e["type"] == "stream_token"]
        assert len(token_events) > 0, "Expected at least one stream_token event"

    async def test_stream_end_content_matches_tokens(self, e2e_session):
        """stream_end content should match the concatenation of stream_token deltas."""
        result = await _run_ws_turn(e2e_session["ws_url"], None, TURN1_MSG)

        token_events = [e for e in result["events"] if e["type"] == "stream_token"]
        stream_end_events = [e for e in result["events"] if e["type"] == "stream_end"]
        assert stream_end_events, "No stream_end event found in received events"
        stream_end = stream_end_events[0]

        concatenated = "".join(e.get("content", "") for e in token_events)
        end_content = stream_end.get("content", "")

        assert end_content, "stream_end has no content field"
        assert end_content == concatenated, (
            f"stream_end content does not match concatenated tokens.\n"
            f"  stream_end: {end_content!r}\n"
            f"  concatenated: {concatenated!r}"
        )

    async def test_tts_chunks_when_tts_enabled(self, e2e_session):
        """When tts_enabled=True, tts_chunk events must be present with ordered seq and audio_base64."""
        result = await _run_ws_turn(
            e2e_session["ws_url"], None, TURN1_MSG, tts_enabled=True
        )

        tts_events = [e for e in result["events"] if e["type"] == "tts_chunk"]
        if not tts_events:
            pytest.fail(
                "Expected tts_chunk events when tts_enabled=True, but none received. "
                "If TTS server is unavailable, ensure the backend is configured before running e2e tests."
            )

        # Verify all chunks have audio_base64 and seq
        for chunk in tts_events:
            assert "audio_base64" in chunk, f"tts_chunk missing audio_base64: {chunk}"
            assert "seq" in chunk, f"tts_chunk missing seq: {chunk}"

        # Verify sequence numbers are ordered (monotonically non-decreasing)
        seq_numbers = [e["seq"] for e in tts_events]
        assert seq_numbers == sorted(seq_numbers), (
            f"tts_chunk sequence numbers are not ordered: {seq_numbers}"
        )

    async def test_two_turn_session_continuity(self, e2e_session):
        """Turn 1 assigns session_id; Turn 2 reuses it and also completes stream_end."""
        result1 = await _run_ws_turn(e2e_session["ws_url"], None, TURN1_MSG)
        session_id = result1["session_id"]
        assert session_id is not None, "Turn 1 did not return a session_id"

        result2 = await _run_ws_turn(e2e_session["ws_url"], session_id, TURN2_MSG)

        event_types2 = [e["type"] for e in result2["events"]]
        assert "stream_end" in event_types2, "Turn 2 did not receive stream_end"
        assert result2["session_id"] == session_id, (
            f"Turn 2 session_id mismatch: expected {session_id!r}, got {result2['session_id']!r}"
        )
