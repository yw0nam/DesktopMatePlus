"""NanoClaw callback API routes."""

from fastapi import APIRouter, HTTPException, status
from langchain_core.messages import SystemMessage
from loguru import logger

from src.models.callback import NanoClawCallbackRequest, NanoClawCallbackResponse
from src.services import get_stm_service

router = APIRouter(prefix="/v1/callback", tags=["Callback"])


@router.post(
    "/nanoclaw/{session_id}",
    response_model=NanoClawCallbackResponse,
    summary="Receive task result from NanoClaw",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Task not found"},
        503: {"description": "STM service not initialized"},
    },
)
async def nanoclaw_callback(session_id: str, payload: NanoClawCallbackRequest):
    """Receive a task completion or failure callback from NanoClaw.

    Updates the pending task status in session metadata and injects
    a synthetic system message into STM chat history.
    """
    stm_service = get_stm_service()
    if stm_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STM service not initialized",
        )

    task_id = payload.task_id

    # Look up pending tasks for this session
    metadata = stm_service.get_session_metadata(session_id)
    pending_tasks = metadata.get("pending_tasks", [])

    # Find the matching task
    task_record = None
    for task in pending_tasks:
        if task.get("task_id") == task_id:
            task_record = task
            break

    if task_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found in session {session_id}",
        )

    # Update task status
    task_record["status"] = payload.status
    stm_service.update_session_metadata(session_id, {"pending_tasks": pending_tasks})

    # Inject synthetic message into chat history
    prefix = "TaskResult" if payload.status == "done" else "TaskFailed"
    synthetic_content = f"[{prefix}:{task_id}] {payload.summary}"
    synthetic_msg = SystemMessage(content=synthetic_content)

    # Use session metadata for user/agent IDs (set by DelegateTaskTool)
    user_id = metadata.get("user_id", "system")
    agent_id = metadata.get("agent_id", "system")
    stm_service.add_chat_history(
        user_id=user_id,
        agent_id=agent_id,
        session_id=session_id,
        messages=[synthetic_msg],
    )

    logger.info(f"Callback processed: task={task_id} status={payload.status}")

    return NanoClawCallbackResponse(
        task_id=task_id,
        status=payload.status,
        message=f"Task {task_id} updated to {payload.status}",
    )
