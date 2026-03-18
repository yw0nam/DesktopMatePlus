"""Tests for Slack Events API webhook route."""

import hashlib
import hmac
import time
from unittest.mock import AsyncMock, MagicMock, patch


def _make_slack_signature(secret: str, body: str, timestamp: str) -> str:
    base = f"v0:{timestamp}:{body}"
    return "v0=" + hmac.new(secret.encode(), base.encode(), hashlib.sha256).hexdigest()


URL_VERIFICATION_PAYLOAD = (
    '{"type":"url_verification","challenge":"test-challenge-abc"}'
)

MESSAGE_PAYLOAD = (
    '{"type":"event_callback","team_id":"T1",'
    '"event":{"type":"message","text":"hello","channel":"C1","user":"U1"}}'
)

TEST_SECRET = "test-signing-secret"


def _headers(body: str, secret: str = TEST_SECRET) -> dict:
    ts = str(int(time.time()))
    sig = _make_slack_signature(secret, body, ts)
    return {
        "x-slack-request-timestamp": ts,
        "x-slack-signature": sig,
        "content-type": "application/json",
    }


class TestSlackWebhook:
    def test_url_verification_returns_challenge(self, client):
        body = URL_VERIFICATION_PAYLOAD
        mock_slack_svc = MagicMock()
        mock_slack_svc.verify_signature.return_value = True

        with patch(
            "src.api.routes.slack.get_slack_service", return_value=mock_slack_svc
        ):
            response = client.post(
                "/v1/channels/slack/events",
                content=body,
                headers=_headers(body),
            )

        assert response.status_code == 200
        assert response.json() == {"challenge": "test-challenge-abc"}

    def test_invalid_signature_returns_403(self, client):
        body = MESSAGE_PAYLOAD
        mock_slack_svc = MagicMock()
        mock_slack_svc.verify_signature.return_value = False

        with patch(
            "src.api.routes.slack.get_slack_service", return_value=mock_slack_svc
        ):
            response = client.post(
                "/v1/channels/slack/events",
                content=body,
                headers={
                    "x-slack-request-timestamp": "0",
                    "x-slack-signature": "v0=invalid",
                    "content-type": "application/json",
                },
            )

        assert response.status_code == 403

    def test_valid_message_returns_200_immediately(self, client):
        body = MESSAGE_PAYLOAD
        mock_slack_svc = MagicMock()
        mock_slack_svc.verify_signature.return_value = True
        mock_slack_svc.parse_event = AsyncMock(
            return_value=MagicMock(
                session_id="slack:T1:C1:default",
                channel_id="C1",
                provider="slack",
                text="hello",
            )
        )

        with (
            patch(
                "src.api.routes.slack.get_slack_service", return_value=mock_slack_svc
            ),
            patch("src.api.routes.slack.get_agent_service", return_value=MagicMock()),
            patch("src.api.routes.slack.get_stm_service", return_value=MagicMock()),
            patch("src.api.routes.slack.get_ltm_service", return_value=MagicMock()),
            patch("src.api.routes.slack.process_message", new=AsyncMock()) as mock_pm,
        ):
            response = client.post(
                "/v1/channels/slack/events",
                content=body,
                headers=_headers(body),
            )

        assert response.status_code == 200
        mock_pm.assert_called_once()  # 백그라운드 태스크가 실제로 예약됐는지 검증

    def test_slack_service_not_initialized_returns_503(self, client):
        body = MESSAGE_PAYLOAD
        with patch("src.api.routes.slack.get_slack_service", return_value=None):
            response = client.post(
                "/v1/channels/slack/events",
                content=body,
                headers=_headers(body),
            )
        assert response.status_code == 503
