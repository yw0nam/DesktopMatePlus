import asyncio

from langchain_core.messages import HumanMessage
from loguru import logger

from src.services.agent_service.service import AgentService
from src.services.channel_service.session_lock import session_lock
from src.services.channel_service.slack_service import SlackService, SlackSettings
from src.services.service_manager import get_session_registry
from src.services.websocket_service.text_processors import TTSTextProcessor

_tts_processor = TTSTextProcessor()

_slack_service: SlackService | None = None


async def init_channel_service(settings: SlackSettings | None) -> None:
    """main.py lifespan에서 호출. SlackService 싱글톤을 초기화한다."""
    global _slack_service
    if settings and settings.enabled and settings.bot_token:
        _slack_service = SlackService(settings)
        await _slack_service.initialize()
        logger.info("SlackService initialized")
    else:
        logger.info("SlackService disabled (enabled=false or bot_token missing)")


def get_slack_service() -> SlackService | None:
    return _slack_service


async def cleanup_channel_service() -> None:
    """Gracefully close the Slack service during shutdown."""
    global _slack_service
    if _slack_service is not None:
        await _slack_service.cleanup()
        _slack_service = None


async def process_message(
    *,
    text: str,
    session_id: str,
    provider: str,
    channel_id: str,
    user_id: str = "default",
    agent_id: str = "yuri",
    agent_service: AgentService,
) -> None:
    """외부 채널 메시지를 처리하고 응답을 전송한다.

    Webhook 라우트(text 있음)와 Callback 핸들러(text="") 양쪽에서 호출된다.
    text가 비어있으면 checkpointer에 이미 TaskResult가 주입된 상태이므로 HumanMessage를 추가하지 않는다.
    """
    reply_channel = {"provider": provider, "channel_id": channel_id}

    async with session_lock(session_id):
        # 1. session_registry upsert (세션이 없으면 생성)
        registry = get_session_registry()
        is_new_session = False
        if registry:
            is_new_session = await asyncio.to_thread(
                registry.upsert, session_id, user_id, agent_id
            )

        # 2. 에이전트 실행 (LTM retrieval handled by ltm_retrieve_hook middleware)
        messages = [HumanMessage(text)] if text else []
        slack = get_slack_service() if provider == "slack" else None
        try:
            result = await agent_service.invoke(
                messages=messages,
                session_id=session_id,
                persona_id=agent_id,
                user_id=user_id,
                agent_id=agent_id,
                context={"reply_channel": reply_channel},
                is_new_session=is_new_session,
            )
            final_text = _tts_processor.process(result["content"]).filtered_text

            # 4. 응답 전송
            if slack:
                await slack.send_message(channel_id, final_text)

        except Exception as e:
            logger.error(f"process_message failed for session {session_id}: {e}")
            if slack:
                await slack.send_message(
                    channel_id, "처리 중 오류가 발생했어. 다시 시도해줘"
                )
