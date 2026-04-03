"""
WebSocket 2-turn conversation E2E test

Sends two consecutive chat messages over the same session and verifies
stream_end is received for each turn within 30 seconds.

Usage:
    uv run python examples/test_websocket.py --ws-url ws://127.0.0.1:7123/v1/chat/stream
"""

import argparse
import asyncio
import json
import sys

import websockets

TOKEN = "demo-token"
AGENT_ID = "e2e-agent"
USER_ID = "e2e-user"
PERSONA_ID = "yuri"
TURN1_MSG = "안녕! 한 문장으로 짧게 인사해줘."
TURN2_MSG = "방금 뭐라고 했어? 한 문장으로 다시 말해줘."


async def run_turn(
    ws_url: str,
    session_id: str | None,
    message: str,
    label: str,
) -> tuple[bool, str | None]:
    """Run one conversation turn. Returns (success, session_id)."""
    async with websockets.connect(
        ws_url, open_timeout=10, ping_interval=20, ping_timeout=10, close_timeout=5
    ) as ws:
        await ws.send(json.dumps({"type": "authorize", "token": TOKEN}))

        captured_session_id: str | None = None
        authorized = False

        async def _recv() -> dict:
            raw = await asyncio.wait_for(ws.recv(), timeout=30.0)
            return json.loads(raw)

        while True:
            data = await _recv()
            event_type = data.get("type")

            if event_type == "ping":
                await ws.send(json.dumps({"type": "pong"}))
                continue

            if event_type == "authorize_error":
                print(f"[{label}] Auth failed: {data.get('error')}", file=sys.stderr)
                return False, None

            if event_type == "authorize_success" and not authorized:
                authorized = True
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
                print(f"[{label}] chat_message sent  session={session_id!r}")
                continue

            if event_type == "stream_start":
                captured_session_id = data.get("session_id") or captured_session_id
                print(f"[{label}] stream_start  session={captured_session_id!r}")
                continue

            if event_type in ("stream_token", "tts_chunk", "tool_call", "tool_result"):
                continue

            if event_type == "stream_end":
                captured_session_id = data.get("session_id") or captured_session_id
                print(f"[{label}] stream_end OK  session={captured_session_id!r}")
                return True, captured_session_id

            if event_type == "error":
                err = data.get("error", "unknown error")
                print(f"[{label}] error event: {err}", file=sys.stderr)
                return False, captured_session_id


async def main() -> int:
    parser = argparse.ArgumentParser(description="WebSocket 2-turn E2E test")
    parser.add_argument(
        "--ws-url",
        required=True,
        help="WebSocket URL (e.g. ws://127.0.0.1:7123/v1/chat/stream)",
    )
    args = parser.parse_args()

    ws_url = args.ws_url
    print(f"[test_websocket] ws_url={ws_url}")

    try:
        ok1, session_id = await run_turn(ws_url, None, TURN1_MSG, "Turn1")
        if not ok1 or not session_id:
            print("[test_websocket] FAILED — Turn 1 did not complete", file=sys.stderr)
            return 1

        ok2, _ = await run_turn(ws_url, session_id, TURN2_MSG, "Turn2")
        if not ok2:
            print("[test_websocket] FAILED — Turn 2 did not complete", file=sys.stderr)
            return 1
    except TimeoutError:
        print(
            "[test_websocket] FAILED — timeout waiting for stream_end", file=sys.stderr
        )
        return 1

    print("[test_websocket] WebSocket PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
