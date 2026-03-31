"""Disconnect-time delegate trigger for knowledge summary."""

import os
from collections.abc import Awaitable, Callable

from langchain_core.messages import HumanMessage as HMsg
from loguru import logger

MIN_TURNS_FOR_SUMMARY: int = 3
STM_INLINE_MAX_TURNS: int = 30
BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")


def build_delegate_payload(
    session_id: str,
    user_id: str,
    agent_id: str,
    messages: list,
) -> dict:
    """Build NanoClaw knowledge_summary payload (inline or fetch-URL)."""
    from langchain_core.messages import convert_to_openai_messages

    human_count = sum(1 for m in messages if isinstance(m, HMsg))
    base: dict = {
        "task": "knowledge_summary",
        "session_id": session_id,
        "user_id": user_id,
        "agent_id": agent_id,
    }
    if human_count < STM_INLINE_MAX_TURNS:
        base["stm_messages"] = convert_to_openai_messages(messages)
    else:
        base["stm_fetch_url"] = f"{BACKEND_URL}/v1/stm/{session_id}/messages"
    return base


async def on_disconnect_handler(
    session_id: str,
    user_id: str,
    agent_id: str,
    agent_service,
    delegate: Callable[[dict], Awaitable[None]],
) -> None:
    """Trigger knowledge summary on session disconnect via agent state."""
    try:
        config = {"configurable": {"thread_id": session_id}}
        state = (await agent_service.agent.aget_state(config)).values

        if state.get("knowledge_saved"):
            logger.debug(f"Session {session_id}: knowledge already saved, skipping")
            return

        messages = state.get("messages", [])
        if sum(1 for m in messages if isinstance(m, HMsg)) < MIN_TURNS_FOR_SUMMARY:
            logger.debug(f"Session {session_id}: too few turns, skipping summary")
            return

        payload = build_delegate_payload(
            session_id=session_id,
            user_id=user_id,
            agent_id=agent_id,
            messages=messages,
        )
        logger.info(f"Session {session_id}: triggering knowledge summary delegation")
        await delegate(payload)
        await agent_service.agent.aupdate_state(config, {"knowledge_saved": True})

    except Exception as e:
        logger.error(f"Session {session_id}: on_disconnect_handler error: {e}")
