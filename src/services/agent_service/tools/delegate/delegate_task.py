"""DelegateTaskTool — async, uses ToolRuntime to read/write agent state."""

import os
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from langgraph.types import Command

from src.services.agent_service.state import PendingTask
from src.services.agent_service.tools.delegate.schemas import DelegateTaskInput

NANOCLAW_URL = os.getenv("NANOCLAW_URL", "http://localhost:3000")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
NANOCLAW_WEBHOOK_PATH = "/api/webhooks/fastapi"
CALLBACK_PATH = "/v1/callback/nanoclaw"
HTTP_TIMEOUT = 5.0


class DelegateTaskTool(BaseTool):
    """Delegates a heavy task to NanoClaw for async processing."""

    name: str = "delegate_task"
    description: str = (
        "Delegate a heavy or long-running task to the team. "
        "Use this when the task requires deep research, code review, "
        "code generation, or any work that should not block the conversation."
    )
    args_schema: type[DelegateTaskInput] = DelegateTaskInput

    def _run(self, task: str, **kwargs) -> str:
        raise NotImplementedError("Use _arun")

    async def _arun(self, task: str, runtime=None, **kwargs) -> Command:
        task_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        state = getattr(runtime, "state", {}) or {}
        context = getattr(runtime, "context", {}) or {}
        pending = list(state.get("pending_tasks", []))
        reply_channel = context.get("reply_channel")

        task_record: PendingTask = {
            "task_id": task_id,
            "description": task,
            "status": "running",
            "created_at": now,
            "reply_channel": reply_channel,
        }
        pending.append(task_record)

        payload = {
            "task": task,
            "task_id": task_id,
            "callback_url": f"{BACKEND_URL}{CALLBACK_PATH}/{task_id}",
        }
        msg_content = f"팀에 작업을 지시했습니다. (task_id: {task_id})"

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                await client.post(
                    f"{NANOCLAW_URL}{NANOCLAW_WEBHOOK_PATH}", json=payload
                )
        except Exception:
            msg_content = f"작업을 팀에 지시했지만, NanoClaw과의 통신에 실패했습니다. (task_id: {task_id})"

        return Command(
            update={
                "pending_tasks": pending,
                "messages": [ToolMessage(content=msg_content, tool_call_id=task_id)],
            }
        )
