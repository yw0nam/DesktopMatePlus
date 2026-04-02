# DEPRECATED: Use examples/test_websocket.py instead.
# This file uses a hardcoded port and is not suitable for e2e.sh.
"""
Multi-turn Session Continuity Test

Verifies that the same session_id can be used for consecutive messages
without triggering an error on the second turn.

Expected behavior:
  Turn 1: session_id=None → server assigns a session_id → stream_end received
  Turn 2: same session_id → stream_end received again (PASS)
  If either turn receives an "error" event → FAIL

Usage:
  cd backend
  uv run python examples/multiturn_session_test.py
"""

import asyncio
import json
import sys

import websockets

WEBSOCKET_URL = "ws://localhost:5600/v1/chat/stream"
TOKEN = "demo-token"
AGENT_ID = "agent-001"
USER_ID = "user-001"
PERSONA_ID = "yuri"
TURN1_MESSAGE = "안녕! 짧게 한 문장으로 인사해줘."
TURN2_MESSAGE = "방금 뭐라고 했어? 한 문장으로 다시 말해줘."


async def run_turn(
    websocket_url: str,
    session_id: str | None,
    message: str,
    turn_label: str,
) -> tuple[bool, str | None, str | None]:
    """Run a single conversation turn.

    Returns:
        (success, captured_session_id, error_message)
    """
    print(f"\n[{turn_label}] Connecting to {websocket_url}")
    print(f"[{turn_label}] session_id={session_id!r}, message={message!r}")

    try:
        async with websockets.connect(
            websocket_url,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        ) as ws:
            # Authorize
            await ws.send(json.dumps({"type": "authorize", "token": TOKEN}))

            captured_session_id: str | None = None
            authorized = False

            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=60.0)
                except asyncio.TimeoutError:
                    print(f"[{turn_label}] ⚠️  Timeout waiting for message")
                    return False, captured_session_id, "Timeout"

                data = json.loads(raw)
                event_type = data.get("type")

                if event_type == "ping":
                    await ws.send(json.dumps({"type": "pong"}))
                    continue

                if event_type == "authorize_error":
                    err = data.get("error", "Unknown authorization error")
                    print(f"[{turn_label}] ❌ Auth failed: {err}")
                    return False, None, err

                if event_type == "authorize_success" and not authorized:
                    authorized = True
                    connection_id = data.get("connection_id", "?")
                    print(f"[{turn_label}] ✓ Authorized (conn={connection_id})")
                    payload = {
                        "type": "chat_message",
                        "content": message,
                        "session_id": session_id,
                        "agent_id": AGENT_ID,
                        "user_id": USER_ID,
                        "persona_id": PERSONA_ID,
                        "tts_enabled": False,
                    }
                    await ws.send(json.dumps(payload))
                    print(f"[{turn_label}] >> chat_message sent")
                    continue

                if event_type == "stream_start":
                    srv_sid = data.get("session_id", "")
                    captured_session_id = srv_sid
                    print(f"[{turn_label}] 🚀 stream_start (session={srv_sid})")
                    continue

                if event_type in ("stream_token", "tts_chunk", "tool_call", "tool_result"):
                    continue

                if event_type == "stream_end":
                    srv_sid = data.get("session_id", "")
                    if not captured_session_id:
                        captured_session_id = srv_sid
                    print(f"[{turn_label}] ✅ stream_end received (session={srv_sid})")
                    return True, captured_session_id, None

                if event_type == "error":
                    err = data.get("error", "Unknown error")
                    print(f"[{turn_label}] ❌ error event: {err}")
                    return False, captured_session_id, err

    except Exception as e:
        print(f"[{turn_label}] ❌ Exception: {type(e).__name__}: {e}")
        return False, None, str(e)


async def main() -> int:
    """Run two-turn session test. Returns 0 on PASS, 1 on FAIL."""
    print("=" * 60)
    print("Multi-turn Session Continuity Test")
    print("=" * 60)

    # Turn 1: new session
    ok1, session_id, err1 = await run_turn(
        WEBSOCKET_URL, None, TURN1_MESSAGE, "Turn 1"
    )
    if not ok1:
        print(f"\n❌ FAIL — Turn 1 failed: {err1}")
        return 1

    if not session_id:
        print("\n❌ FAIL — server did not return a session_id in Turn 1")
        return 1

    print(f"\n↪ Captured session_id: {session_id}")

    # Turn 2: reuse the same session_id
    ok2, _, err2 = await run_turn(
        WEBSOCKET_URL, session_id, TURN2_MESSAGE, "Turn 2"
    )
    if not ok2:
        print(f"\n❌ FAIL — Turn 2 failed with same session_id: {err2}")
        return 1

    print("\n" + "=" * 60)
    print("✅ PASS — Both turns completed successfully")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
