import hashlib
import hmac
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.channel_service.slack_service import (
    SlackMessage,
    SlackService,
    SlackSettings,
)


def _make_settings(**kwargs):
    defaults = {
        "enabled": True,
        "bot_token": "xoxb-test",
        "signing_secret": "test-secret",
    }
    return SlackSettings(**(defaults | kwargs))


def _make_signature(secret: str, body: str, timestamp: str) -> str:
    base = f"v0:{timestamp}:{body}"
    return "v0=" + hmac.new(secret.encode(), base.encode(), hashlib.sha256).hexdigest()


class TestSlackServiceInit:
    def test_bot_name_default_is_yuri(self):
        settings = _make_settings()
        assert settings.bot_name == "yuri"

    def test_bot_name_can_be_overridden(self):
        settings = _make_settings(bot_name="nari")
        assert settings.bot_name == "nari"

    def test_initial_bot_user_id_is_none(self):
        svc = SlackService(_make_settings())
        assert svc._bot_user_id is None

    def test_bot_name_stored_from_settings(self):
        svc = SlackService(_make_settings(bot_name="nari"))
        assert svc._bot_name == "nari"


class TestSlackServiceSignature:
    def test_valid_signature_returns_true(self):
        svc = SlackService(_make_settings())
        ts = str(int(time.time()))
        body = '{"type":"event_callback"}'
        sig = _make_signature("test-secret", body, ts)
        assert svc.verify_signature(body=body, timestamp=ts, signature=sig) is True

    def test_invalid_signature_returns_false(self):
        svc = SlackService(_make_settings())
        ts = str(int(time.time()))
        assert (
            svc.verify_signature(body="body", timestamp=ts, signature="v0=bad") is False
        )

    def test_stale_timestamp_returns_false(self):
        svc = SlackService(_make_settings())
        old_ts = str(int(time.time()) - 400)  # 6+ minutes ago
        body = "body"
        sig = _make_signature("test-secret", body, old_ts)
        assert svc.verify_signature(body=body, timestamp=old_ts, signature=sig) is False


class TestParseEvent:
    @pytest.mark.asyncio
    async def test_returns_none_for_bot_message(self):
        svc = SlackService(_make_settings())
        payload = {
            "type": "event_callback",
            "team_id": "T1",
            "event": {
                "type": "message",
                "bot_id": "B1",
                "text": "bot said this",
                "channel": "C1",
                "user": "U1",
            },
        }
        result = await svc.parse_event(payload)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_slack_message_for_valid_event(self):
        svc = SlackService(_make_settings())
        payload = {
            "type": "event_callback",
            "team_id": "T1",
            "event": {
                "type": "message",
                "text": "hello yuri",
                "channel": "C1",
                "user": "U1",
            },
        }
        result = await svc.parse_event(payload)
        assert result is not None
        assert isinstance(result, SlackMessage)
        assert result.text == "hello yuri"
        assert result.channel_id == "C1"
        assert result.session_id == "slack:T1:C1:default"
        assert result.provider == "slack"

    @pytest.mark.asyncio
    async def test_returns_none_for_non_message_event(self):
        svc = SlackService(_make_settings())
        payload = {
            "type": "event_callback",
            "team_id": "T1",
            "event": {"type": "reaction_added"},
        }
        result = await svc.parse_event(payload)
        assert result is None


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_send_message_calls_slack_api(self):
        svc = SlackService(_make_settings())
        mock_client = MagicMock()
        mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})
        svc._client = mock_client

        await svc.send_message("C123", "hello!")
        mock_client.chat_postMessage.assert_called_once_with(
            channel="C123", text="hello!"
        )
