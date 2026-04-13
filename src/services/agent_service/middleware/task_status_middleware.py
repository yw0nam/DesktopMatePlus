"""Inject delegated-task status into the system prompt before each model call."""

import asyncio
from datetime import UTC, datetime

from langchain_core.messages import SystemMessage
from langgraph.config import get_config
from loguru import logger

from src.services.service_manager import get_pending_task_repo

_TASK_STATUS_SECTION_HEADER = "\n\nDelegated Task Status:"
_RECENT_WINDOW_SECONDS = 600  # show done/failed tasks for 10 minutes


async def task_status_inject_hook(state, runtime):
    """Read pending tasks from MongoDB and inject status into system prompt."""
    repo = get_pending_task_repo()
    if not repo:
        return None

    try:
        config = get_config()
        session_id = config["configurable"]["thread_id"]
    except Exception:
        return None

    try:
        tasks = await asyncio.to_thread(repo.find_by_session_id, session_id)
    except Exception:
        logger.error(f"Task status middleware: MongoDB query failed for {session_id}")
        return None

    if not tasks:
        return None

    # Filter: show all running tasks + recently completed/failed (within 10 min)
    now = datetime.now(UTC)
    visible: list[dict] = []
    for t in tasks:
        if t["status"] == "running":
            visible.append(t)
        elif t["status"] in ("done", "failed"):
            created = t.get("created_at")
            if isinstance(created, datetime):
                if created.tzinfo is None:
                    created = created.replace(tzinfo=UTC)
                if (now - created).total_seconds() < _RECENT_WINDOW_SECONDS:
                    visible.append(t)

    if not visible:
        return None

    # Format task status section
    lines: list[str] = []
    for t in visible:
        tid_short = t["task_id"][:8]
        desc = t.get("description", "")
        status = t["status"]
        if status == "running":
            created = t.get("created_at")
            time_str = (
                created.strftime("%H:%M") if isinstance(created, datetime) else "?"
            )
            lines.append(f"- [{tid_short}] {desc} — running (since {time_str})")
        elif status == "done":
            summary = t.get("result_summary", "")
            lines.append(f"- [{tid_short}] {desc} — done: {summary}")
        elif status == "failed":
            summary = t.get("result_summary", "")
            lines.append(f"- [{tid_short}] {desc} — failed: {summary}")

    task_section = _TASK_STATUS_SECTION_HEADER + "\n" + "\n".join(lines)

    # Inject into SystemMessage at position 0 (same pattern as ltm/summary middleware)
    msgs = state.get("messages", [])
    if (
        msgs
        and isinstance(msgs[0], SystemMessage)
        and isinstance(msgs[0].content, str)
        and msgs[0].id
    ):
        base_content = msgs[0].content.split(_TASK_STATUS_SECTION_HEADER)[0]
        return {
            "messages": [
                SystemMessage(
                    id=msgs[0].id,
                    content=f"{base_content}{task_section}",
                )
            ]
        }
    return None
