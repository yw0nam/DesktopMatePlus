import hashlib
import hmac
import re
import time
from dataclasses import dataclass

from loguru import logger
from pydantic import BaseModel
from slack_sdk.web.async_client import AsyncWebClient

STM_USER_ID = "default"  # TODO: multi-user support requires auth system

_SLACK_TIMESTAMP_TOLERANCE = 300  # 5분


class SlackSettings(BaseModel):
    enabled: bool = False
    bot_token: str = ""
    signing_secret: str = ""
    bot_name: str = "yuri"


@dataclass
class SlackMessage:
    session_id: str  # "slack:{team_id}:{channel_id}:{STM_USER_ID}"
    channel_id: str  # 응답을 보낼 채널 ID
    provider: str  # "slack"
    text: str


class SlackService:
    """Slack Events API 검증, 이벤트 파싱, 메시지 전송을 담당한다."""

    def __init__(self, settings: SlackSettings) -> None:
        self._signing_secret = settings.signing_secret
        self._client = AsyncWebClient(token=settings.bot_token)
        self._bot_user_id: str | None = None
        self._bot_name: str = settings.bot_name

    async def initialize(self) -> None:
        """Slack auth.test를 호출해 봇의 user_id를 가져온다.
        실패 시 경고만 기록하고 이름 기반 매칭으로 폴백한다.
        """
        try:
            result = await self._client.auth_test()
            self._bot_user_id = result["user_id"]
            logger.info(f"SlackService bot_user_id resolved: {self._bot_user_id}")
        except Exception as e:
            logger.warning(
                f"SlackService auth.test failed, falling back to name-only matching: {e}"
            )

    def verify_signature(self, *, body: str, timestamp: str, signature: str) -> bool:
        """Slack request signature를 검증한다. Replay attack 방지를 위해 5분 이상 오래된 요청은 거부."""
        try:
            age = abs(time.time() - float(timestamp))
            if age > _SLACK_TIMESTAMP_TOLERANCE:
                logger.warning(f"Slack request too old: {age:.0f}s")
                return False
            base = f"v0:{timestamp}:{body}"
            expected = (
                "v0="
                + hmac.new(
                    self._signing_secret.encode(), base.encode(), hashlib.sha256
                ).hexdigest()
            )
            return hmac.compare_digest(expected, signature)
        except Exception:
            return False

    def _is_dm(self, channel_id: str) -> bool:
        """Slack DM channel ID는 'D'로 시작한다."""
        return channel_id.startswith("D")

    def _is_mentioned(self, text: str) -> bool:
        """텍스트에 봇에 대한 mention이 포함되어 있는지 확인한다."""
        if self._bot_user_id and re.search(rf"<@{re.escape(self._bot_user_id)}>", text):
            return True
        return bool(re.search(rf"(?i)@{re.escape(self._bot_name)}", text))

    def _clean_text(self, text: str) -> str:
        """mention 태그를 제거하고 공백을 정규화한다."""
        if self._bot_user_id:
            text = re.sub(rf"<@{re.escape(self._bot_user_id)}>", "", text)
        text = re.sub(rf"(?i)@{re.escape(self._bot_name)}", "", text)
        return " ".join(text.split())

    async def parse_event(self, payload: dict) -> SlackMessage | None:
        """Webhook payload에서 메시지를 추출한다.

        - DM 채널: 항상 응답
        - 공개/그룹 채널: mention 있을 때만 응답
        - 무시할 이벤트(봇 메시지, 비메시지 이벤트 등): None 반환
        """
        event = payload.get("event", {})
        if event.get("type") != "message":
            return None
        if event.get("bot_id"):
            return None
        if event.get("subtype"):
            return None

        text = event.get("text", "").strip()
        channel_id = event.get("channel", "")
        team_id = payload.get("team_id", "")
        if not text or not channel_id or not team_id:
            return None

        # DM은 mention 없이도 항상 응답; 공개 채널은 mention 필요
        if not self._is_dm(channel_id):
            if not self._is_mentioned(text):
                return None
            text = self._clean_text(text)
            if not text:
                return None

        session_id = f"slack:{team_id}:{channel_id}:{STM_USER_ID}"
        return SlackMessage(
            session_id=session_id,
            channel_id=channel_id,
            provider="slack",
            text=text,
        )

    async def cleanup(self) -> None:
        """Gracefully clean up Slack client resources."""
        try:
            if hasattr(self._client, "session") and self._client.session is not None:
                await self._client.session.close()
            logger.info("SlackService client closed")
        except Exception as e:
            logger.warning(f"SlackService cleanup error (ignored): {e}")

    async def send_message(self, channel_id: str, text: str) -> None:
        """Slack Web API로 메시지를 전송한다. 실패 시 로그만 기록한다."""
        try:
            await self._client.chat_postMessage(channel=channel_id, text=text)
            logger.info(f"Slack message sent to {channel_id}")
        except Exception as e:
            logger.error(f"Failed to send Slack message to {channel_id}: {e}")
