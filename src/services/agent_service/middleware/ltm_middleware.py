"""LTM middleware — pre-hook for retrieval, post-hook for consolidation.

Both hooks are wired in openai_chat_agent.py via:
  before_model(ltm_retrieve_hook)   — inject LTM context before each model call
  after_model(ltm_consolidation_hook) — fire-and-forget consolidation every N turns
"""

import asyncio
import json

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from src.services.service_manager import get_ltm_service

_LTM_CONSOLIDATION_INTERVAL = 10


async def ltm_retrieve_hook(state, runtime):
    """Retrieve LTM memories and inject as SystemMessage before the model call."""
    ltm = get_ltm_service()
    if not ltm:
        return None

    user_id = state.get("user_id", "")
    agent_id = state.get("agent_id", "")
    if not user_id:
        return None

    # Extract text query from the latest HumanMessage
    query = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            content = msg.content
            if isinstance(content, str):
                query = content
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        query = item["text"]
                        break
            break

    if not query:
        return None

    try:
        result = await asyncio.to_thread(
            ltm.search_memory,
            query=query,
            user_id=user_id,
            agent_id=agent_id,
        )
        if result.get("results"):
            return {
                "messages": [
                    SystemMessage(content=f"Long-term memories: {json.dumps(result)}")
                ]
            }
    except Exception as e:
        logger.error(f"LTM retrieve failed (user={user_id}): {e}")
    return None


def ltm_consolidation_hook(state, runtime):
    """Fire-and-forget LTM consolidation when HumanMessage turn threshold is reached."""
    last = state.get("ltm_last_consolidated_at_turn", 0)
    current = sum(1 for m in state.get("messages", []) if isinstance(m, HumanMessage))

    if current - last < _LTM_CONSOLIDATION_INTERVAL:
        return None

    ltm = get_ltm_service()
    if not ltm:
        return None

    asyncio.create_task(
        _safe_consolidate_ltm(
            ltm_service=ltm,
            messages=list(state["messages"]),
            user_id=state.get("user_id", ""),
            agent_id=state.get("agent_id", ""),
            last_consolidated=last,
        )
    )
    return {"ltm_last_consolidated_at_turn": current}


async def _safe_consolidate_ltm(
    ltm_service,
    messages: list,
    user_id: str,
    agent_id: str,
    last_consolidated: int,
) -> None:
    """Ensures consolidation failures are logged and never swallowed silently."""
    try:
        await _consolidate_ltm(
            ltm_service, messages, user_id, agent_id, last_consolidated
        )
    except Exception as e:
        logger.error(
            f"LTM consolidation failed (user={user_id}, agent={agent_id}): {e}"
        )


async def _consolidate_ltm(
    ltm_service,
    messages: list,
    user_id: str,
    agent_id: str,
    last_consolidated: int,
) -> None:
    slice_start = len(messages)
    human_count = 0
    for idx, msg in enumerate(messages):
        if isinstance(msg, HumanMessage):
            if human_count == last_consolidated:
                slice_start = idx
                break
            human_count += 1

    await asyncio.to_thread(
        ltm_service.add_memory,
        messages=messages[slice_start:],
        user_id=user_id,
        agent_id=agent_id,
    )
    total = sum(1 for m in messages if isinstance(m, HumanMessage))
    logger.info(f"LTM consolidated at turn {total} (user={user_id})")
