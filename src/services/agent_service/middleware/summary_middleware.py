"""Summary middleware — pre-hook for injection, post-hook for consolidation.

Both hooks are wired in openai_chat_agent.py via:
  before_model(summary_inject_hook)       — inject stored summaries before model call
  after_model(summary_consolidation_hook) — fire-and-forget consolidation every N turns
"""

import asyncio
import os

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from src.services.service_manager import get_summary_service

_SUMMARY_TURN_THRESHOLD = int(os.getenv("SUMMARY_TURN_THRESHOLD", "20"))
_SUMMARY_SECTION_HEADER = "\n\nPrevious Conversation Summary:"

_background_tasks: set[asyncio.Task[None]] = set()


async def summary_inject_hook(state, runtime):
    """Retrieve stored summaries and inject as SystemMessage context before the model call."""
    svc = get_summary_service()
    if not svc:
        return None

    user_id = state.get("user_id", "")
    agent_id = state.get("agent_id", "")
    if not user_id:
        return None

    session_id = f"{user_id}:{agent_id}"

    try:
        summaries = await asyncio.to_thread(svc.get_summaries, session_id)
    except Exception:
        logger.exception(f"Summary inject failed (session={session_id})")
        return None

    if not summaries:
        return None

    latest = summaries[-1]
    summary_section = f"{_SUMMARY_SECTION_HEADER} {latest.summary_text}"

    msgs = state.get("messages", [])
    if (
        msgs
        and isinstance(msgs[0], SystemMessage)
        and isinstance(msgs[0].content, str)
        and msgs[0].id
    ):
        base_content = msgs[0].content.split(_SUMMARY_SECTION_HEADER)[0].rstrip()
        return {
            "messages": [
                SystemMessage(
                    id=msgs[0].id,
                    content=f"{base_content}{summary_section}",
                )
            ]
        }
    return None


def summary_consolidation_hook(state, runtime):
    """Fire-and-forget summary consolidation when HumanMessage turn threshold is reached."""
    last = state.get("summary_last_consolidated_at_turn", 0)
    current = sum(1 for m in state.get("messages", []) if isinstance(m, HumanMessage))

    if current - last < _SUMMARY_TURN_THRESHOLD:
        return None

    svc = get_summary_service()
    if not svc:
        return None

    user_id = state.get("user_id", "")
    agent_id = state.get("agent_id", "")
    session_id = f"{user_id}:{agent_id}"

    task = asyncio.create_task(
        _safe_summarize(
            svc=svc,
            messages=list(state["messages"]),
            session_id=session_id,
            turn_range_start=last,
            turn_range_end=current,
        )
    )
    if task is not None:
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    return {"summary_last_consolidated_at_turn": current}


async def _safe_summarize(svc, messages, session_id, turn_range_start, turn_range_end):
    """Ensures summarization failures are logged and never swallowed silently."""
    try:
        summary = await svc.summarize(
            messages=messages,
            session_id=session_id,
            turn_range_start=turn_range_start,
            turn_range_end=turn_range_end,
        )
        await asyncio.to_thread(svc.store_summary, summary)
    except Exception as e:
        logger.error(f"Summary consolidation failed (session={session_id}): {e}")
