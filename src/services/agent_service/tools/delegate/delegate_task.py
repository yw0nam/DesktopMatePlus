"""DelegateTaskTool — async, uses ToolRuntime to read/write agent state."""

import asyncio
from uuid import uuid4

import httpx
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from langgraph.types import Command
from loguru import logger

from src.services.agent_service.tools.delegate.schemas import DelegateTaskInput

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
        from src.configs.settings import get_settings
        from src.services.pending_task_repository import PendingTaskDocument
        from src.services.service_manager import get_pending_task_repo

        task_id = str(uuid4())

        state = getattr(runtime, "state", {}) or {}
        context = getattr(runtime, "context", {}) or {}
        reply_channel = context.get("reply_channel")

        session_id = runtime.config["configurable"]["thread_id"]
        user_id = state.get("user_id", "default")
        agent_id = state.get("agent_id", "yuri")

        repo = get_pending_task_repo()
        if repo is None:
            logger.warning(
                f"PendingTaskRepo not available, skipping DB insert for task_id={task_id}"
            )
        else:
            task_doc = PendingTaskDocument(
                task_id=task_id,
                session_id=session_id,
                user_id=user_id,
                agent_id=agent_id,
                description=task,
                status="running",
                reply_channel=reply_channel,
            )
            try:
                await asyncio.to_thread(repo.insert, task_doc)
            except Exception as e:
                logger.error(
                    f"Failed to insert pending task to DB: task_id={task_id}, error={e}"
                )

        _settings = get_settings()
        payload = {
            "task": task,
            "task_id": task_id,
            "callback_url": f"{_settings.backend_url}{CALLBACK_PATH}/{task_id}",
        }
        msg_content = f"팀에 작업을 지시했습니다. (task_id: {task_id})"

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                await client.post(
                    f"{_settings.nanoclaw_url}{NANOCLAW_WEBHOOK_PATH}", json=payload
                )
        except Exception:
            msg_content = f"작업을 팀에 지시했지만, NanoClaw과의 통신에 실패했습니다. (task_id: {task_id})"

        return Command(
            update={
                "messages": [ToolMessage(content=msg_content, tool_call_id=task_id)],
            }
        )
