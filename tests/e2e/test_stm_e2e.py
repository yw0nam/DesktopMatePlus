"""E2E tests for STM (Short-Term Memory) HTTP API.

Requires: FASTAPI_URL env var pointing to a running backend.
    FASTAPI_URL=http://127.0.0.1:7123 uv run pytest -m e2e tests/e2e/test_stm_e2e.py --tb=long
"""

import uuid

import httpx
import pytest

USER_ID = "e2e-user"
AGENT_ID = "e2e-agent"


@pytest.mark.e2e
class TestStmE2E:
    async def test_stm_add_chat_history(self, e2e_session):
        """POST /v1/stm/add-chat-history returns 201 with session_id and message_count."""
        base_url = e2e_session["base_url"]
        session_id = str(uuid.uuid4())

        async with httpx.AsyncClient(base_url=base_url, timeout=15) as client:
            resp = await client.post(
                "/v1/stm/add-chat-history",
                json={
                    "user_id": USER_ID,
                    "agent_id": AGENT_ID,
                    "session_id": session_id,
                    "messages": [
                        {"role": "user", "content": "E2E test message"},
                        {"role": "assistant", "content": "E2E test reply"},
                    ],
                },
            )

        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body.get("session_id") == session_id, (
            f"session_id mismatch: {body.get('session_id')!r} != {session_id!r}"
        )
        assert body.get("message_count", 0) >= 2, (
            f"Expected message_count >= 2, got {body.get('message_count')}"
        )

    async def test_stm_get_chat_history(self, e2e_session):
        """GET /v1/stm/get-chat-history returns the added messages."""
        base_url = e2e_session["base_url"]
        session_id = str(uuid.uuid4())

        async with httpx.AsyncClient(base_url=base_url, timeout=15) as client:
            # Add first
            add_resp = await client.post(
                "/v1/stm/add-chat-history",
                json={
                    "user_id": USER_ID,
                    "agent_id": AGENT_ID,
                    "session_id": session_id,
                    "messages": [
                        {"role": "user", "content": "Hello from e2e"},
                        {"role": "assistant", "content": "Hello back"},
                    ],
                },
            )
            assert add_resp.status_code == 201, f"Setup add failed: {add_resp.status_code} {add_resp.text}"

            # Then get
            resp = await client.get(
                "/v1/stm/get-chat-history",
                params={
                    "session_id": session_id,
                    "user_id": USER_ID,
                    "agent_id": AGENT_ID,
                },
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        messages = resp.json().get("messages", [])
        assert len(messages) >= 2, f"Expected >= 2 messages, got {len(messages)}"

    async def test_stm_delete_session(self, e2e_session):
        """DELETE /v1/stm/sessions/{session_id} removes the session."""
        base_url = e2e_session["base_url"]
        session_id = str(uuid.uuid4())

        async with httpx.AsyncClient(base_url=base_url, timeout=15) as client:
            # Add
            add_resp = await client.post(
                "/v1/stm/add-chat-history",
                json={
                    "user_id": USER_ID,
                    "agent_id": AGENT_ID,
                    "session_id": session_id,
                    "messages": [
                        {"role": "user", "content": "To be deleted"},
                    ],
                },
            )
            assert add_resp.status_code == 201, f"Setup add failed: {add_resp.status_code} {add_resp.text}"

            # Delete
            resp = await client.delete(
                f"/v1/stm/sessions/{session_id}",
                params={"user_id": USER_ID, "agent_id": AGENT_ID},
            )
            assert resp.status_code == 200, (
                f"DELETE failed: {resp.status_code} {resp.text}"
            )

            # Verify empty after delete
            resp = await client.get(
                "/v1/stm/get-chat-history",
                params={
                    "session_id": session_id,
                    "user_id": USER_ID,
                    "agent_id": AGENT_ID,
                },
            )

        assert resp.status_code == 200
        messages_after = resp.json().get("messages", [])
        assert len(messages_after) == 0, (
            f"Expected 0 messages after delete, got {len(messages_after)}"
        )

    async def test_stm_full_crud_cycle(self, e2e_session):
        """Full STM CRUD: add → get → clear → verify empty."""
        base_url = e2e_session["base_url"]
        session_id = str(uuid.uuid4())

        async with httpx.AsyncClient(base_url=base_url, timeout=15) as client:
            # ADD
            add_resp = await client.post(
                "/v1/stm/add-chat-history",
                json={
                    "user_id": USER_ID,
                    "agent_id": AGENT_ID,
                    "session_id": session_id,
                    "messages": [
                        {"role": "user", "content": "CRUD test message"},
                        {"role": "assistant", "content": "CRUD test reply"},
                    ],
                },
            )
            assert add_resp.status_code == 201, f"CRUD add failed: {add_resp.status_code} {add_resp.text}"

            # GET
            get_resp = await client.get(
                "/v1/stm/get-chat-history",
                params={
                    "session_id": session_id,
                    "user_id": USER_ID,
                    "agent_id": AGENT_ID,
                },
            )
            assert get_resp.status_code == 200, f"CRUD get failed: {get_resp.status_code} {get_resp.text}"
            assert len(get_resp.json().get("messages", [])) >= 2

            # CLEAR
            del_resp = await client.delete(
                f"/v1/stm/sessions/{session_id}",
                params={"user_id": USER_ID, "agent_id": AGENT_ID},
            )
            assert del_resp.status_code == 200, f"CRUD delete failed: {del_resp.status_code} {del_resp.text}"

            # VERIFY empty
            verify_resp = await client.get(
                "/v1/stm/get-chat-history",
                params={
                    "session_id": session_id,
                    "user_id": USER_ID,
                    "agent_id": AGENT_ID,
                },
            )
            assert verify_resp.status_code == 200
            assert len(verify_resp.json().get("messages", [])) == 0
