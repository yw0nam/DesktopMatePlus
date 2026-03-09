import os
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from langchain_core.tools import BaseTool
from pydantic import ConfigDict

from src.services.agent_service.tools.delegate.schemas import DelegateTaskInput
from src.services.stm_service.service import STMService

NANOCLAW_URL = os.getenv("NANOCLAW_URL", "http://localhost:3000")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
NANOCLAW_WEBHOOK_PATH = "/api/webhooks/fastapi"
CALLBACK_PATH = "/v1/callback/nanoclaw"
HTTP_TIMEOUT = 5.0


class DelegateTaskTool(BaseTool):
    """Delegates a heavy task to NanoClaw for asynchronous processing."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = "delegate_task"
    description: str = (
        "Delegate a heavy or long-running task to the team. "
        "Use this when the task requires deep research, code review, "
        "code generation, or any work that should not block the conversation."
    )
    args_schema: type[DelegateTaskInput] = DelegateTaskInput
    stm_service: STMService
    session_id: str

    def _run(self, task: str) -> str:
        task_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # 1. Record pending task in STM metadata
        task_record = {
            "task_id": task_id,
            "description": task,
            "status": "running",
            "created_at": now,
        }
        metadata = self.stm_service.get_session_metadata(self.session_id)
        pending = metadata.get("pending_tasks", [])
        pending.append(task_record)
        self.stm_service.update_session_metadata(
            self.session_id, {"pending_tasks": pending}
        )

        # 2. Fire-and-forget POST to NanoClaw
        callback_url = f"{BACKEND_URL}{CALLBACK_PATH}/{self.session_id}"
        payload = {
            "task": task,
            "task_id": task_id,
            "session_id": self.session_id,
            "callback_url": callback_url,
        }
        return_text = f"팀에 작업을 지시했습니다. (task_id: {task_id})"
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                client.post(
                    f"{NANOCLAW_URL}{NANOCLAW_WEBHOOK_PATH}",
                    json=payload,
                )
        except httpx.HTTPError:
            return_text = (
                f"작업을 팀에 지시했지만, NanoClaw과의 통신에 실패했습니다. (task_id: {task_id})"
            )
            pass

        return return_text
