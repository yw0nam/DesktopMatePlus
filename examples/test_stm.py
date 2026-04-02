"""
STM round-trip test — add / get / clear

Usage:
    uv run python examples/test_stm.py --base-url http://127.0.0.1:7123
"""

import argparse
import sys
import uuid

import httpx

USER_ID = "e2e-user"
AGENT_ID = "e2e-agent"


def main() -> int:
    parser = argparse.ArgumentParser(description="STM round-trip E2E test")
    parser.add_argument(
        "--base-url",
        required=True,
        help="Backend base URL (e.g. http://127.0.0.1:7123)",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    session_id = str(uuid.uuid4())

    print(f"[test_stm] base_url={base_url}  session_id={session_id}")

    # --- ADD ---
    add_payload = {
        "user_id": USER_ID,
        "agent_id": AGENT_ID,
        "session_id": session_id,
        "messages": [
            {"role": "user", "content": "E2E test message"},
            {"role": "assistant", "content": "E2E test reply"},
        ],
    }
    resp = httpx.post(
        f"{base_url}/v1/stm/add-chat-history", json=add_payload, timeout=10
    )
    assert (
        resp.status_code == 201
    ), f"add-chat-history failed: {resp.status_code} {resp.text}"
    returned_session_id = resp.json().get("session_id")
    assert (
        returned_session_id == session_id
    ), f"session_id mismatch: {returned_session_id!r} != {session_id!r}"
    print(f"[test_stm] ADD OK  message_count={resp.json().get('message_count')}")

    # --- GET ---
    resp = httpx.get(
        f"{base_url}/v1/stm/get-chat-history",
        params={"session_id": session_id, "user_id": USER_ID, "agent_id": AGENT_ID},
        timeout=10,
    )
    assert (
        resp.status_code == 200
    ), f"get-chat-history failed: {resp.status_code} {resp.text}"
    messages = resp.json().get("messages", [])
    assert len(messages) >= 2, f"Expected >=2 messages, got {len(messages)}"
    print(f"[test_stm] GET OK  messages={len(messages)}")

    # --- CLEAR (delete session) ---
    resp = httpx.delete(
        f"{base_url}/v1/stm/sessions/{session_id}",
        params={"user_id": USER_ID, "agent_id": AGENT_ID},
        timeout=10,
    )
    assert (
        resp.status_code == 200
    ), f"delete session failed: {resp.status_code} {resp.text}"
    print("[test_stm] CLEAR OK")

    # Verify deleted — get-chat-history should return empty messages
    resp = httpx.get(
        f"{base_url}/v1/stm/get-chat-history",
        params={"session_id": session_id, "user_id": USER_ID, "agent_id": AGENT_ID},
        timeout=10,
    )
    assert resp.status_code == 200, f"get after delete failed: {resp.status_code}"
    messages_after = resp.json().get("messages", [])
    assert (
        len(messages_after) == 0
    ), f"Expected 0 messages after delete, got {len(messages_after)}"
    print("[test_stm] VERIFY-CLEAR OK")

    print("[test_stm] STM PASSED")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as e:
        print(f"[test_stm] ASSERTION FAILED: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[test_stm] ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
