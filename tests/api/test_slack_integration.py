"""Slack 전체 흐름 통합 테스트.

가짜 Slack payload → SlackService.parse_event → process_message → SlackService.send_message
NanoClaw는 모킹하여 Callback을 직접 트리거한다.
"""

import hashlib
import hmac
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage


def _make_headers(body: str, secret: str = "test-secret") -> dict:
    ts = str(int(time.time()))
    sig = (
        "v0="
        + hmac.new(
            secret.encode(), f"v0:{ts}:{body}".encode(), hashlib.sha256
        ).hexdigest()
    )
    return {
        "x-slack-request-timestamp": ts,
        "x-slack-signature": sig,
        "content-type": "application/json",
    }


MESSAGE_BODY = (
    '{"type":"event_callback","team_id":"T1",'
    '"event":{"type":"message","text":"안녕 유리","channel":"C1","user":"U1"}}'
)

CALLBACK_PAYLOAD = {
    "task_id": "task-123",
    "status": "done",
    "summary": "개발 완료",
}


async def _run_process_message_directly(
    text: str,
    session_id: str,
    provider: str,
    channel_id: str,
    mock_agent: MagicMock,
    mock_stm: MagicMock,
    mock_ltm: MagicMock,
    mock_slack_svc: MagicMock,
) -> None:
    """process_message를 직접 실행하여 send_message 호출 여부를 검증한다."""
    from src.services.channel_service import process_message

    with (
        patch(
            "src.services.channel_service.get_slack_service",
            return_value=mock_slack_svc,
        ),
        patch(
            "src.services.channel_service.load_context", new=AsyncMock(return_value=[])
        ),
        patch("src.services.channel_service.save_turn", new=AsyncMock()),
    ):
        await process_message(
            text=text,
            session_id=session_id,
            provider=provider,
            channel_id=channel_id,
            agent_service=mock_agent,
            stm=mock_stm,
            ltm=mock_ltm,
        )


class TestSlackFullFlow:
    @pytest.mark.asyncio
    async def test_simple_message_reaches_slack_send(self, client):
        """Slack 메시지 → process_message → SlackService.send_message 까지 전달된다."""
        mock_slack_svc = MagicMock()
        mock_slack_svc.verify_signature.return_value = True
        mock_slack_svc.parse_event = AsyncMock(
            return_value=MagicMock(
                session_id="slack:T1:C1:default",
                channel_id="C1",
                provider="slack",
                text="안녕 유리",
            )
        )
        mock_slack_svc.send_message = AsyncMock()

        mock_agent = MagicMock()
        mock_agent.invoke = AsyncMock(
            return_value={"content": "안녕!", "new_chats": [AIMessage("안녕!")]}
        )

        mock_stm = MagicMock()
        mock_stm.upsert_session = MagicMock(return_value=True)
        mock_stm.update_session_metadata = MagicMock(return_value=True)
        mock_stm.get_chat_history = MagicMock(return_value=[])
        mock_stm.get_session_metadata = MagicMock(return_value={})

        mock_ltm = MagicMock()
        mock_ltm.search_memory = MagicMock(return_value={"results": []})

        # Step 1: Webhook 엔드포인트가 200을 반환하고 process_message를 스케줄링하는지 확인
        with (
            patch(
                "src.api.routes.slack.get_slack_service", return_value=mock_slack_svc
            ),
            patch("src.api.routes.slack.get_agent_service", return_value=mock_agent),
            patch("src.api.routes.slack.get_stm_service", return_value=mock_stm),
            patch("src.api.routes.slack.get_ltm_service", return_value=mock_ltm),
            patch("src.api.routes.slack.process_message", new=AsyncMock()) as mock_pm,
        ):
            response = client.post(
                "/v1/channels/slack/events",
                content=MESSAGE_BODY,
                headers=_make_headers(MESSAGE_BODY),
            )
            assert response.status_code == 200
            mock_pm.assert_called_once()

        # Step 2: process_message 자체가 send_message를 호출하는지 직접 테스트
        await _run_process_message_directly(
            text="안녕 유리",
            session_id="slack:T1:C1:default",
            provider="slack",
            channel_id="C1",
            mock_agent=mock_agent,
            mock_stm=mock_stm,
            mock_ltm=mock_ltm,
            mock_slack_svc=mock_slack_svc,
        )

        mock_slack_svc.send_message.assert_called_once_with("C1", "안녕!")

    @pytest.mark.asyncio
    async def test_callback_triggers_final_slack_response(self, client):
        """NanoClaw 콜백 → process_message(text="") → SlackService.send_message."""
        session_id = "slack:T1:C1:default"
        task_id = "task-123"

        mock_stm = MagicMock()
        mock_stm.get_session_metadata.return_value = {
            "pending_tasks": [{"task_id": task_id, "status": "running"}],
            "user_id": "default",
            "agent_id": "yuri",
            "reply_channel": {"provider": "slack", "channel_id": "C1"},
        }
        mock_stm.update_session_metadata.return_value = True
        mock_stm.add_chat_history.return_value = session_id
        mock_stm.upsert_session = MagicMock(return_value=True)
        mock_stm.get_chat_history = MagicMock(return_value=[])

        mock_agent = MagicMock()
        mock_agent.invoke = AsyncMock(
            return_value={
                "content": "결과 받았어!",
                "new_chats": [AIMessage("결과 받았어!")],
            }
        )
        mock_ltm = MagicMock()
        mock_ltm.search_memory = MagicMock(return_value={"results": []})
        mock_slack_svc = MagicMock()
        mock_slack_svc.send_message = AsyncMock()

        # Step 1: 콜백 엔드포인트가 200을 반환하고 process_message를 스케줄링하는지 확인
        with (
            patch("src.api.routes.callback.get_stm_service", return_value=mock_stm),
            patch("src.api.routes.callback.get_agent_service", return_value=mock_agent),
            patch("src.api.routes.callback.get_ltm_service", return_value=mock_ltm),
            patch(
                "src.api.routes.callback.process_message", new=AsyncMock()
            ) as mock_pm,
        ):
            response = client.post(
                f"/v1/callback/nanoclaw/{session_id}",
                json=CALLBACK_PAYLOAD,
            )
            assert response.status_code == 200
            mock_pm.assert_called_once()
            call_kwargs = mock_pm.call_args[1]
            assert call_kwargs["text"] == ""
            assert call_kwargs["provider"] == "slack"
            assert call_kwargs["channel_id"] == "C1"

        # Step 2: process_message(text="") 자체가 send_message를 호출하는지 직접 테스트
        await _run_process_message_directly(
            text="",
            session_id=session_id,
            provider="slack",
            channel_id="C1",
            mock_agent=mock_agent,
            mock_stm=mock_stm,
            mock_ltm=mock_ltm,
            mock_slack_svc=mock_slack_svc,
        )

        mock_slack_svc.send_message.assert_called_once_with("C1", "결과 받았어!")
