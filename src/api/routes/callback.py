"""NanoClaw callback API routes."""

import asyncio

from fastapi import APIRouter, HTTPException, status
from langchain_core.messages import SystemMessage
from loguru import logger

from src.models.callback import NanoClawCallbackRequest, NanoClawCallbackResponse
from src.services import get_agent_service

router = APIRouter(prefix="/v1/callback", tags=["Callback"])


@router.post(
    "/nanoclaw/{session_id}",
    response_model=NanoClawCallbackResponse,
    summary="Receive task result from NanoClaw",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Task not found"},
        503: {"description": "Agent service not initialized or state update failed"},
    },
)
async def nanoclaw_callback(session_id: str, payload: NanoClawCallbackRequest):
    """Inject synthetic message into agent state; route result to originating channel."""
    agent_svc = get_agent_service()
    if agent_svc is None:
        raise HTTPException(503, "Agent service not initialized")

    config = {"configurable": {"thread_id": session_id}}
    state = (await agent_svc.agent.aget_state(config)).values
    pending_tasks = list(state.get("pending_tasks", []))

    task_record = next(
        (t for t in pending_tasks if t.get("task_id") == payload.task_id), None
    )
    if task_record is None:
        raise HTTPException(
            404, f"Task {payload.task_id} not found in session {session_id}"
        )

    task_record["status"] = payload.status
    prefix = "TaskResult" if payload.status == "done" else "TaskFailed"
    synthetic_msg = SystemMessage(
        content=f"[{prefix}:{payload.task_id}] {payload.summary}"
    )

    try:
        await agent_svc.agent.aupdate_state(
            config, {"messages": [synthetic_msg], "pending_tasks": pending_tasks}
        )
    except Exception as e:
        logger.error(f"State update failed for session {session_id}: {e}")
        raise HTTPException(503, "State update failed") from e

    # Route to originating channel via task-level reply_channel
    reply_channel = task_record.get("reply_channel")
    if reply_channel:
        from src.services import get_ltm_service
        from src.services.channel_service import process_message

        asyncio.create_task(
            process_message(
                text="",
                session_id=session_id,
                provider=reply_channel["provider"],
                channel_id=reply_channel["channel_id"],
                user_id=state.get("user_id", "default"),
                agent_id=state.get("agent_id", "yuri"),
                agent_service=agent_svc,
                ltm=get_ltm_service(),
            )
        )
        logger.info(f"Callback routing to {reply_channel['provider']} for {session_id}")

    logger.info(f"Callback processed: task={payload.task_id} status={payload.status}")
    return NanoClawCallbackResponse(
        task_id=payload.task_id,
        status=payload.status,
        message=f"Task {payload.task_id} updated to {payload.status}",
    )
