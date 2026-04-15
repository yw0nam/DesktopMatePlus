"""Tests for ProactiveService — the main orchestrator."""

import json
import time
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.services.proactive_service.config import ProactiveConfig
from src.services.proactive_service.proactive_service import ProactiveService


def _make_connection(idle_seconds: float = 400.0):
    conn = MagicMock()
    conn.connection_id = uuid4()
    conn.is_authenticated = True
    conn.is_closing = False
    conn.last_user_message_at = time.time() - idle_seconds
    conn.user_id = "test_user"
    conn.persona_id = "yuri"
    conn.message_processor = MagicMock()
    conn.message_processor._current_turn_id = None
    conn.websocket = AsyncMock()
    return conn


@pytest.fixture
def proactive_service(tmp_path):
    prompts_file = tmp_path / "proactive_prompts.yml"
    prompts_file.write_text(
        "idle: |\n  유저가 {idle_seconds}초 동안 조용합니다.\n"
        "webhook: |\n  컨텍스트: {context}\n"
    )
    config = ProactiveConfig(
        idle_timeout_seconds=300,
        cooldown_seconds=10,
        watcher_interval_seconds=60,
    )
    ws_manager = MagicMock()
    ws_manager.connections = {}
    agent_service = AsyncMock()

    async def mock_stream(**kwargs):
        yield {"type": "stream_start", "turn_id": "t1", "session_id": "s1"}
        yield {"type": "stream_token", "chunk": "Hello!"}
        yield {
            "type": "stream_end",
            "turn_id": "t1",
            "session_id": "s1",
            "content": "Hello!",
            "new_chats": [],
        }

    agent_service.stream = mock_stream
    svc = ProactiveService(
        config=config,
        ws_manager=ws_manager,
        agent_service=agent_service,
        prompts_path=prompts_file,
    )
    return svc


class TestTriggerProactive:
    async def test_trigger_succeeds(self, proactive_service):
        conn = _make_connection(idle_seconds=400.0)
        proactive_service._ws_manager.connections = {conn.connection_id: conn}
        result = await proactive_service.trigger_proactive(
            connection_id=conn.connection_id,
            trigger_type="idle",
            idle_seconds=400,
        )
        assert result["status"] == "triggered"
        assert result["turn_id"] == "t1"

    async def test_trigger_skipped_when_connection_not_found(self, proactive_service):
        result = await proactive_service.trigger_proactive(
            connection_id=uuid4(), trigger_type="idle"
        )
        assert result["status"] == "skipped"
        assert "not found" in result["reason"]

    async def test_trigger_skipped_when_connection_closing(self, proactive_service):
        conn = _make_connection(idle_seconds=400.0)
        conn.is_closing = True
        proactive_service._ws_manager.connections = {conn.connection_id: conn}
        result = await proactive_service.trigger_proactive(
            connection_id=conn.connection_id, trigger_type="idle"
        )
        assert result["status"] == "skipped"
        assert "not found" in result["reason"]

    async def test_cooldown_blocks_repeated_trigger(self, proactive_service):
        conn = _make_connection(idle_seconds=400.0)
        proactive_service._ws_manager.connections = {conn.connection_id: conn}
        result1 = await proactive_service.trigger_proactive(
            connection_id=conn.connection_id,
            trigger_type="idle",
            idle_seconds=400,
        )
        assert result1["status"] == "triggered"
        result2 = await proactive_service.trigger_proactive(
            connection_id=conn.connection_id,
            trigger_type="idle",
            idle_seconds=400,
        )
        assert result2["status"] == "skipped"
        assert "cooldown" in result2["reason"]

    async def test_trigger_skipped_when_active_turn(self, proactive_service):
        conn = _make_connection(idle_seconds=400.0)
        conn.message_processor._current_turn_id = "active-turn"
        proactive_service._ws_manager.connections = {conn.connection_id: conn}
        result = await proactive_service.trigger_proactive(
            connection_id=conn.connection_id,
            trigger_type="idle",
        )
        assert result["status"] == "skipped"
        assert "active turn" in result["reason"]

    async def test_trigger_skipped_when_no_message_processor(self, proactive_service):
        conn = _make_connection(idle_seconds=400.0)
        conn.message_processor = None
        proactive_service._ws_manager.connections = {conn.connection_id: conn}
        result = await proactive_service.trigger_proactive(
            connection_id=conn.connection_id,
            trigger_type="idle",
        )
        assert result["status"] == "skipped"
        assert "active turn" in result["reason"]

    async def test_idle_recheck_skips_if_became_active(self, proactive_service):
        conn = _make_connection(idle_seconds=100.0)  # Less than 300s timeout
        proactive_service._ws_manager.connections = {conn.connection_id: conn}
        result = await proactive_service.trigger_proactive(
            connection_id=conn.connection_id,
            trigger_type="idle",
        )
        assert result["status"] == "skipped"
        assert "became active" in result["reason"]

    async def test_non_idle_trigger_skips_idle_recheck(self, proactive_service):
        """Non-idle triggers (e.g. scheduled) should not do idle recheck."""
        conn = _make_connection(idle_seconds=100.0)  # Recently active
        proactive_service._ws_manager.connections = {conn.connection_id: conn}
        result = await proactive_service.trigger_proactive(
            connection_id=conn.connection_id,
            trigger_type="scheduled",
            prompt_key="webhook",
            context="test context",
        )
        assert result["status"] == "triggered"

    async def test_proactive_flag_injected_in_events(self, proactive_service):
        conn = _make_connection(idle_seconds=400.0)
        proactive_service._ws_manager.connections = {conn.connection_id: conn}
        await proactive_service.trigger_proactive(
            connection_id=conn.connection_id,
            trigger_type="idle",
            idle_seconds=400,
        )
        # Verify all events sent to websocket have proactive=True
        for call_args in conn.websocket.send_text.call_args_list:
            event = json.loads(call_args[0][0])
            assert event.get("proactive") is True

    async def test_trigger_handles_stream_error(self, proactive_service):
        conn = _make_connection(idle_seconds=400.0)
        proactive_service._ws_manager.connections = {conn.connection_id: conn}

        async def failing_stream(**kwargs):
            raise RuntimeError("agent exploded")
            yield

        proactive_service._agent_service.stream = failing_stream
        result = await proactive_service.trigger_proactive(
            connection_id=conn.connection_id,
            trigger_type="idle",
            idle_seconds=400,
        )
        assert result["status"] == "skipped"
        assert "error" in result["reason"]

    async def test_prompt_key_override(self, proactive_service):
        """When prompt_key is provided, it should be used instead of trigger_type."""
        conn = _make_connection(idle_seconds=400.0)
        proactive_service._ws_manager.connections = {conn.connection_id: conn}
        result = await proactive_service.trigger_proactive(
            connection_id=conn.connection_id,
            trigger_type="scheduled",
            prompt_key="webhook",
            context="important event",
        )
        assert result["status"] == "triggered"

    async def test_persona_id_from_connection(self, proactive_service):
        conn = _make_connection(idle_seconds=400.0)
        conn.persona_id = "custom_persona"
        proactive_service._ws_manager.connections = {conn.connection_id: conn}

        stream_kwargs: list[dict] = []

        async def recording_stream(**kwargs):
            stream_kwargs.append(kwargs)
            yield {"type": "stream_start", "turn_id": "t1", "session_id": "s1"}
            yield {
                "type": "stream_end",
                "turn_id": "t1",
                "session_id": "s1",
                "content": "",
                "new_chats": [],
            }

        proactive_service._agent_service.stream = recording_stream

        await proactive_service.trigger_proactive(
            connection_id=conn.connection_id, trigger_type="idle", idle_seconds=400
        )
        assert stream_kwargs[0]["persona_id"] == "custom_persona"


class TestOnUserMessage:
    def test_on_user_message_resets_idle_watcher(self, proactive_service):
        cid = uuid4()
        proactive_service._idle_watcher._triggered_connections.add(cid)
        proactive_service.on_user_message(cid)
        assert cid not in proactive_service._idle_watcher._triggered_connections


class TestLifecycle:
    async def test_start_stop(self, proactive_service):
        await proactive_service.start()
        assert proactive_service._idle_watcher._task is not None
        await proactive_service.stop()
