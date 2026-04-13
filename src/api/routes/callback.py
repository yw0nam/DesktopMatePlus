"""NanoClaw callback API routes."""

import asyncio

from fastapi import APIRouter, HTTPException, status
from loguru import logger

from src.models.callback import NanoClawCallbackRequest, NanoClawCallbackResponse
from src.services.service_manager import get_pending_task_repo

router = APIRouter(prefix="/v1/callback", tags=["Callback"])


@router.post(
    "/nanoclaw/{task_id}",
    response_model=NanoClawCallbackResponse,
    summary="Receive task result from NanoClaw",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Task not found"},
        503: {"description": "Task repository not initialized"},
    },
)
async def nanoclaw_callback(task_id: str, payload: NanoClawCallbackRequest):
    """Update task status in MongoDB; route result to originating channel."""
    repo = get_pending_task_repo()
    if repo is None:
        raise HTTPException(503, "Task repository not initialized")

    task_record = await asyncio.to_thread(repo.find_by_task_id, payload.task_id)
    if task_record is None:
        raise HTTPException(404, f"Task {payload.task_id} not found")

    await asyncio.to_thread(
        repo.update_status, payload.task_id, payload.status, payload.summary
    )

    # Route to originating channel via task-level reply_channel
    reply_channel = task_record.get("reply_channel")
    if reply_channel:
        from src.services import get_agent_service
        from src.services.channel_service import process_message

        agent_svc = get_agent_service()
        if agent_svc is not None:
            asyncio.create_task(
                process_message(
                    text="",
                    session_id=task_record.get("session_id", ""),
                    provider=reply_channel["provider"],
                    channel_id=reply_channel["channel_id"],
                    user_id=task_record.get("user_id", "default"),
                    agent_id=task_record.get("agent_id", "yuri"),
                    agent_service=agent_svc,
                )
            )
            logger.info(f"Callback routing to {reply_channel['provider']}")

    logger.info(f"Callback processed: task={payload.task_id} status={payload.status}")
    return NanoClawCallbackResponse(
        task_id=payload.task_id,
        status=payload.status,
        message=f"Task {payload.task_id} updated to {payload.status}",
    )
