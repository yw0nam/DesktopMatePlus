"""STM (Short-Term Memory) API routes."""

from typing import Optional

from fastapi import APIRouter, HTTPException, status
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
from src.services import get_stm_service

router = APIRouter(prefix="/v1/stm", tags=["STM"])


@router.post(
    "/chat-history",
    response_model=AddChatHistoryResponse,
    summary="Add chat history",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Chat history added successfully",
            "model": AddChatHistoryResponse,
        },
        400: {
            "description": "Invalid input",
            "content": {
                "application/json": {"example": {"detail": "Invalid message format"}}
            },
        },
        500: {
            "description": "STM service error",
            "content": {
                "application/json": {
                    "example": {"detail": "Error adding chat history: ..."}
                }
            },
        },
        503: {
            "description": "STM service not initialized",
            "content": {
                "application/json": {
                    "example": {"detail": "STM service not initialized"}
                }
            },
        },
    },
)
async def add_chat_history(request: AddChatHistoryRequest) -> AddChatHistoryResponse:
    """Add chat history to a session.

    This endpoint accepts messages and stores them in the specified session.
    If no session_id is provided, a new session will be created.

    Args:
        request: Add chat history request

    Returns:
        AddChatHistoryResponse: Session ID and message count

    Raises:
        HTTPException: If STM service is not initialized or processing fails
    """
    stm_service = get_stm_service()

    if stm_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STM service not initialized",
        )

    try:
        # Parse messages
        messages = convert_to_messages(request.messages)

        # Add chat history
        session_id = stm_service.add_chat_history(
            user_id=request.user_id,
            agent_id=request.agent_id,
            session_id=request.session_id,
            messages=messages,
        )

        return AddChatHistoryResponse(
            session_id=session_id,
            message_count=len(messages),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding chat history: {str(e)}",
        ) from e


@router.get(
    "/chat-history",
    response_model=GetChatHistoryResponse,
    summary="Get chat history",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Chat history retrieved successfully",
            "model": GetChatHistoryResponse,
        },
        400: {
            "description": "Invalid input",
            "content": {
                "application/json": {"example": {"detail": "Invalid parameters"}}
            },
        },
        404: {
            "description": "Session not found",
            "content": {
                "application/json": {"example": {"detail": "Session not found"}}
            },
        },
        500: {
            "description": "STM service error",
            "content": {
                "application/json": {
                    "example": {"detail": "Error retrieving chat history: ..."}
                }
            },
        },
        503: {
            "description": "STM service not initialized",
            "content": {
                "application/json": {
                    "example": {"detail": "STM service not initialized"}
                }
            },
        },
    },
)
async def get_chat_history(
    user_id: str,
    agent_id: str,
    session_id: str,
    limit: Optional[int] = None,
) -> GetChatHistoryResponse:
    """Get chat history from a session.

    This endpoint retrieves messages from the specified session.

    Args:
        user_id: User identifier
        agent_id: Agent identifier
        session_id: Session identifier
        limit: Maximum number of recent messages to retrieve (optional)

    Returns:
        GetChatHistoryResponse: Chat history messages

    Raises:
        HTTPException: If STM service is not initialized or processing fails
    """
    stm_service = get_stm_service()

    if stm_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STM service not initialized",
        )

    try:
        # Get chat history
        messages = stm_service.get_chat_history(
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            limit=limit,
        )
        messages = convert_to_openai_messages(messages)
        # Convert to response format
        message_responses = []
        for msg in messages:
            message_responses.append(MessageResponse(**msg))

        return GetChatHistoryResponse(
            session_id=session_id,
            messages=message_responses,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving chat history: {str(e)}",
        ) from e


@router.get(
    "/sessions",
    response_model=ListSessionsResponse,
    summary="List sessions",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Sessions retrieved successfully",
            "model": ListSessionsResponse,
        },
        400: {
            "description": "Invalid input",
            "content": {
                "application/json": {"example": {"detail": "Invalid parameters"}}
            },
        },
        500: {
            "description": "STM service error",
            "content": {
                "application/json": {
                    "example": {"detail": "Error listing sessions: ..."}
                }
            },
        },
        503: {
            "description": "STM service not initialized",
            "content": {
                "application/json": {
                    "example": {"detail": "STM service not initialized"}
                }
            },
        },
    },
)
async def list_sessions(
    user_id: str,
    agent_id: str,
) -> ListSessionsResponse:
    """List all sessions for a user and agent.

    This endpoint retrieves all sessions for the specified user and agent.

    Args:
        user_id: User identifier
        agent_id: Agent identifier

    Returns:
        ListSessionsResponse: List of sessions

    Raises:
        HTTPException: If STM service is not initialized or processing fails
    """
    stm_service = get_stm_service()

    if stm_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STM service not initialized",
        )

    try:
        # List sessions
        sessions = stm_service.list_sessions(
            user_id=user_id,
            agent_id=agent_id,
        )

        # Convert to response format
        session_metadata = [
            SessionMetadata(
                session_id=session["session_id"],
                user_id=session["user_id"],
                agent_id=session["agent_id"],
                created_at=session["created_at"].isoformat(),
                updated_at=session["updated_at"].isoformat(),
                metadata=session.get("metadata", {}),
            )
            for session in sessions
        ]

        return ListSessionsResponse(sessions=session_metadata)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing sessions: {str(e)}",
        ) from e


@router.delete(
    "/sessions/{session_id}",
    response_model=DeleteSessionResponse,
    summary="Delete session",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Session deleted successfully",
            "model": DeleteSessionResponse,
        },
        400: {
            "description": "Invalid input",
            "content": {
                "application/json": {"example": {"detail": "Invalid parameters"}}
            },
        },
        404: {
            "description": "Session not found",
            "content": {
                "application/json": {"example": {"detail": "Session not found"}}
            },
        },
        500: {
            "description": "STM service error",
            "content": {
                "application/json": {
                    "example": {"detail": "Error deleting session: ..."}
                }
            },
        },
        503: {
            "description": "STM service not initialized",
            "content": {
                "application/json": {
                    "example": {"detail": "STM service not initialized"}
                }
            },
        },
    },
)
async def delete_session(
    session_id: str,
    user_id: str,
    agent_id: str,
) -> DeleteSessionResponse:
    """Delete a session.

    This endpoint deletes the specified session and all its messages.

    Args:
        session_id: Session identifier
        user_id: User identifier
        agent_id: Agent identifier

    Returns:
        DeleteSessionResponse: Deletion status

    Raises:
        HTTPException: If STM service is not initialized or processing fails
    """
    stm_service = get_stm_service()

    if stm_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STM service not initialized",
        )

    try:
        # Delete session
        success = stm_service.delete_session(
            session_id=session_id,
            user_id=user_id,
            agent_id=agent_id,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )

        return DeleteSessionResponse(
            success=True,
            message="Session deleted successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting session: {str(e)}",
        ) from e


@router.patch(
    "/sessions/{session_id}/metadata",
    response_model=UpdateSessionMetadataResponse,
    summary="Update session metadata",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Session metadata updated successfully",
            "model": UpdateSessionMetadataResponse,
        },
        400: {
            "description": "Invalid input",
            "content": {
                "application/json": {"example": {"detail": "Invalid parameters"}}
            },
        },
        404: {
            "description": "Session not found",
            "content": {
                "application/json": {"example": {"detail": "Session not found"}}
            },
        },
        500: {
            "description": "STM service error",
            "content": {
                "application/json": {
                    "example": {"detail": "Error updating session metadata: ..."}
                }
            },
        },
        503: {
            "description": "STM service not initialized",
            "content": {
                "application/json": {
                    "example": {"detail": "STM service not initialized"}
                }
            },
        },
    },
)
async def update_session_metadata(
    session_id: str,
    request: UpdateSessionMetadataRequest,
) -> UpdateSessionMetadataResponse:
    """Update session metadata.

    This endpoint updates the metadata for the specified session.

    Args:
        session_id: Session identifier
        request: Update session metadata request

    Returns:
        UpdateSessionMetadataResponse: Update status

    Raises:
        HTTPException: If STM service is not initialized or processing fails
    """
    stm_service = get_stm_service()

    if stm_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STM service not initialized",
        )

    try:
        # Update session metadata
        success = stm_service.update_session_metadata(
            session_id=session_id,
            metadata=request.metadata,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )

        return UpdateSessionMetadataResponse(
            success=True,
            message="Session metadata updated successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating session metadata: {str(e)}",
        ) from e
