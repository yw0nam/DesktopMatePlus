"""Disconnect-time delegate trigger for knowledge summary."""

import os
from collections.abc import Awaitable, Callable

from loguru import logger

from src.services.stm_service.service import STMService

# Knowledge summary trigger constants
MIN_TURNS_FOR_SUMMARY: int = 3
STM_INLINE_MAX_TURNS: int = 30
NANOCLAW_URL: str = os.getenv("NANOCLAW_URL", "http://localhost:3000")
BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")


def build_delegate_payload(
    session_id: str,
    user_id: str,
    agent_id: str,
    stm: STMService,
    messages: list | None = None,
) -> dict:
    """Build NanoClaw delegate payload with Option A (inline) or B (fetch URL) STM.

    Args:
        messages: Pre-fetched chat history. If None, fetched from stm.
    """
    from langchain_core.messages import HumanMessage as HMsg
    from langchain_core.messages import convert_to_openai_messages

    if messages is None:
        messages = stm.get_chat_history(
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            limit=None,
        )
    human_count = sum(1 for m in messages if isinstance(m, HMsg))

    base_payload: dict = {
        "task": "knowledge_summary",
        "session_id": session_id,
        "user_id": user_id,
        "agent_id": agent_id,
    }

    if human_count < STM_INLINE_MAX_TURNS:
        # Option A: inline messages
        base_payload["stm_messages"] = convert_to_openai_messages(messages)
    else:
        # Option B: provide fetch URL
        base_payload["stm_fetch_url"] = f"{BACKEND_URL}/v1/stm/{session_id}/messages"

    return base_payload


async def on_disconnect_handler(
    session_id: str,
    user_id: str,
    agent_id: str,
    stm_service: STMService,
    delegate: Callable[[dict], Awaitable[None]],
) -> None:
    """Trigger knowledge summary delegation on session disconnect.

    Fires when:
    - knowledge_saved is not True in session metadata
    - human message count >= MIN_TURNS_FOR_SUMMARY
    """
    from langchain_core.messages import HumanMessage as HMsg

    try:
        metadata = stm_service.get_session_metadata(session_id)
        if metadata.get("knowledge_saved"):
            logger.debug(f"Session {session_id}: knowledge already saved, skipping")
            return

        messages = stm_service.get_chat_history(
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            limit=None,
        )
        human_count = sum(1 for m in messages if isinstance(m, HMsg))
        if human_count < MIN_TURNS_FOR_SUMMARY:
            logger.debug(
                f"Session {session_id}: only {human_count} turns, skipping summary"
            )
            return

        payload = build_delegate_payload(
            session_id=session_id,
            user_id=user_id,
            agent_id=agent_id,
            stm=stm_service,
            messages=messages,
        )
        logger.info(f"Session {session_id}: triggering knowledge summary delegation")
        await delegate(payload)

    except Exception as e:  # noqa: BLE001
        logger.error(f"Session {session_id}: on_disconnect_handler error: {e}")
