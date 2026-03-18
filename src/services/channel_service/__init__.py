import asyncio

from langchain_core.messages import HumanMessage
from loguru import logger

from src.services.agent_service.service import AgentService
from src.services.channel_service.session_lock import session_lock
from src.services.channel_service.slack_service import SlackService, SlackSettings
from src.services.ltm_service.service import LTMService
from src.services.stm_service.service import STMService
from src.services.websocket_service.manager.memory_orchestrator import (
    load_context,
    save_turn,
)

_slack_service: SlackService | None = None


def init_channel_service(settings: SlackSettings | None) -> None:
    """main.py lifespan에서 호출. SlackService 싱글톤을 초기화한다."""
    global _slack_service
    if settings and settings.enabled and settings.bot_token:
        _slack_service = SlackService(settings)
        logger.info("SlackService initialized")
    else:
        logger.info("SlackService disabled (enabled=false or bot_token missing)")


def get_slack_service() -> SlackService | None:
    return _slack_service


async def process_message(
    *,
    text: str,
    session_id: str,
    provider: str,
    channel_id: str,
    user_id: str = "default",  # TODO: multi-user support — 상수에서 읽도록 교체
    agent_id: str = "yuri",
    agent_service: AgentService,
    stm: STMService,
    ltm: LTMService,
) -> None:
    """외부 채널 메시지를 처리하고 응답을 전송한다.

    Webhook 라우트(text 있음)와 Callback 핸들러(text="") 양쪽에서 호출된다.
    text가 비어있으면 STM에 이미 TaskResult가 주입된 상태이므로 HumanMessage를 추가하지 않는다.
    """
    async with session_lock(session_id):
        # 1. STM 세션 upsert (세션이 없으면 생성)
        await asyncio.to_thread(stm.upsert_session, session_id, user_id, agent_id)
        # 2. reply_channel 메타데이터 저장
        await asyncio.to_thread(
            stm.update_session_metadata,
            session_id,
            {
                "user_id": user_id,
                "agent_id": agent_id,
                "reply_channel": {"provider": provider, "channel_id": channel_id},
            },
        )
        # 3. 컨텍스트 로드
        context = await load_context(
            stm_service=stm,
            ltm_service=ltm,
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            query=text,
        )
        # 4. 에이전트 실행
        # text가 비어있으면 콜백 경로 — STM에 TaskResult가 이미 주입된 상태이므로
        # HumanMessage를 추가하지 않고 context만으로 invoke 호출.
        messages = context + [HumanMessage(text)] if text else context
        slack = get_slack_service() if provider == "slack" else None
        try:
            result = await agent_service.invoke(
                messages=messages,
                session_id=session_id,
                persona_id=agent_id,
                user_id=user_id,
                agent_id=agent_id,
            )
            final_text = result["content"]
            # new_chats에는 AgentService가 생성한 AIMessage(+tool messages)가 담겨 있다.
            # HumanMessage는 agent가 반환하지 않으므로 save_turn 시 별도로 prepend한다.
            new_chats = result["new_chats"]

            # 5. STM/LTM 저장 (fire-and-forget)
            chats_to_save = ([HumanMessage(text)] if text else []) + list(new_chats)
            asyncio.create_task(
                save_turn(
                    new_chats=chats_to_save,
                    stm_service=stm,
                    ltm_service=ltm,
                    user_id=user_id,
                    agent_id=agent_id,
                    session_id=session_id,
                )
            )

            # 6. 응답 전송
            if slack:
                await slack.send_message(channel_id, final_text)

        except Exception as e:
            logger.error(f"process_message failed for session {session_id}: {e}")
            if slack:
                await slack.send_message(channel_id, "처리 중 오류가 발생했어. 다시 시도해줘")
