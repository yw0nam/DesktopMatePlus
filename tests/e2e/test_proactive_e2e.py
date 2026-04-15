"""E2E tests for proactive talking feature.

Requires: FASTAPI_URL env var pointing to a running backend.
    FASTAPI_URL=http://127.0.0.1:7123 uv run pytest -m e2e tests/e2e/test_proactive_e2e.py --tb=long
"""

import asyncio
import json

import httpx
import pytest
import websockets

TOKEN = "demo-token"
CONNECT_TIMEOUT = 10
RECV_TIMEOUT = 30.0


@pytest.mark.e2e
class TestProactiveWebhookE2E:
    async def test_webhook_trigger_sends_proactive_message(self, e2e_session):
        """POST /v1/proactive/trigger → WS receives proactive-tagged events."""
        base_url = e2e_session["base_url"]
        ws_url = e2e_session["ws_url"]

        async with websockets.connect(
            ws_url,
            open_timeout=CONNECT_TIMEOUT,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        ) as ws:
            await ws.send(json.dumps({"type": "authorize", "token": TOKEN}))
            connection_id = None

            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=RECV_TIMEOUT)
                data = json.loads(raw)
                if data.get("type") == "ping":
                    await ws.send(json.dumps({"type": "pong"}))
                    continue
                if data.get("type") == "authorize_success":
                    connection_id = data.get("connection_id")
                    break
                if data.get("type") == "authorize_error":
                    pytest.fail(f"Auth failed: {data}")

            assert connection_id is not None

            async with httpx.AsyncClient() as http:
                resp = await http.post(
                    f"{base_url}/v1/proactive/trigger",
                    json={
                        "session_id": connection_id,
                        "trigger_type": "webhook",
                        "context": "E2E test trigger",
                    },
                )
                assert resp.status_code == 200
                trigger_result = resp.json()

            if trigger_result.get("status") == "skipped":
                pytest.skip(f"Trigger skipped: {trigger_result.get('reason')}")

            events = []
            try:
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=RECV_TIMEOUT)
                    data = json.loads(raw)
                    if data.get("type") == "ping":
                        await ws.send(json.dumps({"type": "pong"}))
                        continue
                    events.append(data)
                    if data.get("type") == "stream_end":
                        break
            except TimeoutError:
                pytest.fail(
                    f"Timed out waiting for proactive stream_end. Events: {events}"
                )

            event_types = [e["type"] for e in events]
            assert "stream_start" in event_types
            assert "stream_end" in event_types
            stream_start = next(e for e in events if e["type"] == "stream_start")
            assert stream_start.get("proactive") is True


@pytest.mark.e2e
class TestProactiveIdleE2E:
    async def test_idle_triggers_proactive_message(self, e2e_session):
        """Connect → wait idle_timeout → receive proactive message."""
        ws_url = e2e_session["ws_url"]

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
                if data.get("type") == "ping":
                    await ws.send(json.dumps({"type": "pong"}))
                    continue
                if data.get("type") == "authorize_success":
                    break

            events = []
            try:
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=15.0)
                    data = json.loads(raw)
                    if data.get("type") == "ping":
                        await ws.send(json.dumps({"type": "pong"}))
                        continue
                    events.append(data)
                    if data.get("type") == "stream_end":
                        break
            except TimeoutError:
                if not events:
                    pytest.fail("No proactive message received within 15s idle period")

            if events:
                event_types = [e["type"] for e in events]
                assert "stream_start" in event_types
                stream_start = next(e for e in events if e["type"] == "stream_start")
                assert stream_start.get("proactive") is True
