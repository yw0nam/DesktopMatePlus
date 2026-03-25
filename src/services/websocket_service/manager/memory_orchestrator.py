"""Memory orchestrator — LTM prefix loading only.

STM persistence is automatic via LangGraph MongoDBSaver checkpointer.
LTM consolidation is handled by LTMConsolidationMiddleware (@after_model).
"""

import asyncio
import json

from langchain_core.messages import BaseMessage, SystemMessage
from loguru import logger

from src.services.ltm_service import LTMService


async def load_ltm_prefix(
    ltm_service: LTMService | None,
    user_id: str,
    agent_id: str,
    query: str,
) -> list[BaseMessage]:
    """Return LTM search results as a SystemMessage prefix, or [] if unavailable."""
    if not ltm_service:
        return []
    try:
        result = await asyncio.to_thread(
            ltm_service.search_memory,
            query=query,
            user_id=user_id,
            agent_id=agent_id,
        )
        if result.get("results"):
            return [SystemMessage(content=f"Long-term memories: {json.dumps(result)}")]
    except Exception as e:
        logger.error(f"LTM prefix load failed (user={user_id}): {e}")
    return []
