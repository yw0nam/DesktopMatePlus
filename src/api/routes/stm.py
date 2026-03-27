"""STM-compatible API routes — backed by LangGraph checkpointer + session_registry."""


from fastapi import APIRouter, HTTPException
from langchain_core.messages import convert_to_messages, convert_to_openai_messages

from src.models.stm import (
    AddChatHistoryRequest,
    AddChatHistoryResponse,
    DeleteSessionResponse,
    GetChatHistoryResponse,
    ListSessionsResponse,
    MessageResponse,
    SessionMetadata,
    UpdateSessionMetadataRequest,
    UpdateSessionMetadataResponse,
)
from src.services import get_agent_service
from src.services.service_manager import get_session_registry

router = APIRouter(prefix="/v1/stm", tags=["STM"])

_ALLOWED_METADATA_KEYS = {
    "user_id",
    "agent_id",
    "knowledge_saved",
    "ltm_last_consolidated_at_turn",
}


def _agent_or_raise():
    svc = get_agent_service()
    if svc is None:
        raise HTTPException(503, "Agent service not initialized")
    return svc


@router.get(
    "/get-chat-history",
    response_model=GetChatHistoryResponse,
    summary="Get chat history for a session",
    status_code=200,
    responses={
        500: {"description": "Error retrieving chat history"},
        503: {"description": "Agent service not initialized"},
    },
)
async def get_chat_history(
    session_id: str, user_id: str, agent_id: str, limit: int | None = None
):
    svc = _agent_or_raise()
    config = {"configurable": {"thread_id": session_id}}
    try:
        messages = svc.agent.get_state(config).values.get("messages", [])
        if limit:
            messages = messages[-limit:]
        openai_msgs = convert_to_openai_messages(messages)
        return GetChatHistoryResponse(
            session_id=session_id,
            messages=[MessageResponse(**m) for m in openai_msgs],
        )
    except Exception as e:
        raise HTTPException(500, f"Error retrieving chat history: {e}") from e


@router.post(
    "/add-chat-history",
    response_model=AddChatHistoryResponse,
    summary="Add messages to chat history",
    status_code=201,
    responses={
        500: {"description": "Error adding chat history"},
        503: {"description": "Agent service not initialized"},
    },
)
async def add_chat_history(request: AddChatHistoryRequest):
    svc = _agent_or_raise()
    config = {"configurable": {"thread_id": request.session_id}}
    try:
        messages = convert_to_messages(request.messages)
        svc.agent.update_state(config, {"messages": messages})
        return AddChatHistoryResponse(
            session_id=request.session_id, message_count=len(messages)
        )
    except Exception as e:
        raise HTTPException(500, f"Error adding chat history: {e}") from e


@router.get(
    "/sessions",
    response_model=ListSessionsResponse,
    summary="List all sessions for a user/agent",
    status_code=200,
    responses={
        500: {"description": "Error listing sessions"},
        503: {"description": "Session registry not initialized"},
    },
)
async def list_sessions(user_id: str, agent_id: str):
    registry = get_session_registry()
    if registry is None:
        raise HTTPException(503, "Session registry not initialized")
    try:
        sessions = registry.list_sessions(user_id=user_id, agent_id=agent_id)
        return ListSessionsResponse(
            sessions=[
                SessionMetadata(
                    session_id=s["thread_id"],
                    user_id=s["user_id"],
                    agent_id=s["agent_id"],
                    created_at=(
                        s["created_at"].isoformat()
                        if hasattr(s["created_at"], "isoformat")
                        else str(s["created_at"])
                    ),
                    updated_at=(
                        s["updated_at"].isoformat()
                        if hasattr(s["updated_at"], "isoformat")
                        else str(s["updated_at"])
                    ),
                    metadata={},
                )
                for s in sessions
            ]
        )
    except Exception as e:
        raise HTTPException(500, f"Error listing sessions: {e}") from e


@router.delete(
    "/sessions/{session_id}",
    response_model=DeleteSessionResponse,
    summary="Delete a session and its chat history",
    status_code=200,
    responses={
        404: {"description": "Session not found"},
        503: {"description": "Agent service not initialized"},
    },
)
async def delete_session(session_id: str, user_id: str, agent_id: str):
    _agent_or_raise()
    registry = get_session_registry()
    if not (registry and registry.delete(session_id)):
        raise HTTPException(404, "Session not found")
    return DeleteSessionResponse(success=True, message="Session deleted successfully")


@router.patch(
    "/sessions/{session_id}/metadata",
    response_model=UpdateSessionMetadataResponse,
    summary="Update session metadata",
    status_code=200,
    responses={
        500: {"description": "Error updating metadata"},
        503: {"description": "Agent service not initialized"},
    },
)
async def update_session_metadata(
    session_id: str, request: UpdateSessionMetadataRequest
):
    svc = _agent_or_raise()
    config = {"configurable": {"thread_id": session_id}}
    try:
        update = {
            k: v for k, v in request.metadata.items() if k in _ALLOWED_METADATA_KEYS
        }
        if update:
            svc.agent.update_state(config, update)
        return UpdateSessionMetadataResponse(success=True, message="Metadata updated")
    except Exception as e:
        raise HTTPException(500, f"Error updating metadata: {e}") from e


@router.get(
    "/{session_id}/messages",
    response_model=GetChatHistoryResponse,
    summary="Fetch all messages — NanoClaw Option B fetch endpoint",
    status_code=200,
    responses={
        500: {"description": "Error retrieving messages"},
        503: {"description": "Agent service not initialized"},
    },
)
async def get_session_messages(session_id: str):
    svc = _agent_or_raise()
    config = {"configurable": {"thread_id": session_id}}
    try:
        messages = svc.agent.get_state(config).values.get("messages", [])
        openai_msgs = convert_to_openai_messages(messages)
        return GetChatHistoryResponse(
            session_id=session_id,
            messages=[MessageResponse(**m) for m in openai_msgs],
        )
    except Exception as e:
        raise HTTPException(500, f"Error retrieving messages: {e}") from e
