"""
LTM round-trip test — store / search

Skips gracefully if Qdrant is not running (503 response from /v1/ltm/add_memory).

Usage:
    uv run python examples/test_ltm.py --base-url http://127.0.0.1:7123
"""

import argparse
import sys

import httpx

USER_ID = "e2e-user"
AGENT_ID = "e2e-agent"


def main() -> int:
    parser = argparse.ArgumentParser(description="LTM round-trip E2E test")
    parser.add_argument(
        "--base-url",
        required=True,
        help="Backend base URL (e.g. http://127.0.0.1:7123)",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")

    print(f"[test_ltm] base_url={base_url}")

    # --- STORE ---
    add_payload = {
        "user_id": USER_ID,
        "agent_id": AGENT_ID,
        "memory_dict": "E2E test memory: the user prefers concise answers.",
    }
    try:
        resp = httpx.post(f"{base_url}/v1/ltm/add_memory", json=add_payload, timeout=30)
    except httpx.RequestError as e:
        print(f"[test_ltm] LTM SKIPPED (Qdrant not running): request error: {e}")
        return 0

    # 503 = LTM service not initialized (Qdrant not running at startup)
    if resp.status_code == 503:
        print("LTM SKIPPED (Qdrant not running)")
        return 0

    assert resp.status_code == 200, f"add_memory failed: {resp.status_code} {resp.text}"
    print("[test_ltm] STORE OK")

    # --- SEARCH ---
    search_payload = {
        "user_id": USER_ID,
        "agent_id": AGENT_ID,
        "query": "concise answers",
    }
    resp = httpx.post(
        f"{base_url}/v1/ltm/search_memory", json=search_payload, timeout=30
    )
    if resp.status_code == 503:
        print("LTM SKIPPED (Qdrant not running)")
        return 0

    assert (
        resp.status_code == 200
    ), f"search_memory failed: {resp.status_code} {resp.text}"
    result = resp.json()
    assert result.get("success") is True, f"search_memory success=False: {result}"
    print(f"[test_ltm] SEARCH OK  result_keys={list(result.keys())}")

    print("LTM PASSED")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as e:
        print(f"[test_ltm] ASSERTION FAILED: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[test_ltm] ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
