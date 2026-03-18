import asyncio
import json

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from loguru import logger

from src.services.ltm_service import LTMService
from src.services.stm_service import STMService

_LTM_CONSOLIDATION_INTERVAL = 10


async def load_context(
    stm_service: STMService | None,
    ltm_service: LTMService | None,
    user_id: str,
    agent_id: str,
    session_id: str,
    query: str,
    limit: int = 10,
) -> list[BaseMessage]:
    """Load conversation context: optional LTM prefix + STM chat history.

    STM/LTM calls are synchronous; wrapped in asyncio.to_thread to avoid
    blocking the event loop.
    """
    ltm_prefix: list[BaseMessage] = []

    if ltm_service:
        search_result = await asyncio.to_thread(
            ltm_service.search_memory,
            query=query,
            user_id=user_id,
            agent_id=agent_id,
        )
        if search_result.get("results"):
            ltm_prefix = [
                SystemMessage(
                    content=f"Long-term memories: {json.dumps(search_result)}"
                )
            ]

    stm_history: list[BaseMessage] = []
    if stm_service:
        stm_history = await asyncio.to_thread(
            stm_service.get_chat_history,
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            limit=limit,
        )

    return ltm_prefix + stm_history


async def save_turn(
    new_chats: list[BaseMessage],
    stm_service: STMService | None,
    ltm_service: LTMService | None,
    user_id: str,
    agent_id: str,
    session_id: str,
) -> None:
    """Persist new messages to STM; conditionally consolidate to LTM.

    Intended to run as a fire-and-forget background task via asyncio.create_task().
    STM/LTM calls are synchronous; wrapped in asyncio.to_thread.
    """
    try:
        if not new_chats or not stm_service:
            return

        await asyncio.to_thread(
            stm_service.add_chat_history,
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            messages=new_chats,
        )
        logger.info(f"Chat history saved to STM: {session_id}")

        if not ltm_service:
            return

        metadata = await asyncio.to_thread(stm_service.get_session_metadata, session_id)
        last_consolidated = metadata.get("ltm_last_consolidated_at_turn", 0)

        history = await asyncio.to_thread(
            stm_service.get_chat_history,
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
        )
        current_turn = sum(1 for m in history if isinstance(m, HumanMessage))

        if current_turn - last_consolidated < _LTM_CONSOLIDATION_INTERVAL:
            return

        slice_start = 0
        human_count = 0
        for idx, msg in enumerate(history):
            if isinstance(msg, HumanMessage):
                if human_count == last_consolidated:
                    slice_start = idx
                    break
                human_count += 1
        else:
            slice_start = len(history)

        ltm_result = await asyncio.to_thread(
            ltm_service.add_memory,
            messages=history[slice_start:],
            user_id=user_id,
            agent_id=agent_id,
        )
        await asyncio.to_thread(
            stm_service.update_session_metadata,
            session_id,
            {"ltm_last_consolidated_at_turn": current_turn},
        )
        logger.info(f"LTM consolidation at turn {current_turn}: {ltm_result}")

    except Exception as e:
        logger.error(f"Background memory save failed for session {session_id}: {e}")
