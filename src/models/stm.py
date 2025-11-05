"""STM (Short-Term Memory) API request and response models."""

from typing import Optional

from pydantic import BaseModel, Field


class AddChatHistoryRequest(BaseModel):
    """Request model for adding chat history."""

    user_id: str = Field(
        ...,
        description="User identifier",
        min_length=1,
    )
    agent_id: str = Field(
        ...,
        description="Agent identifier",
        min_length=1,
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session identifier (optional, will create new if None)",
    )
    messages: list[dict] = Field(
        ...,
        description="List of messages to add (format: [{type: 'human'|'ai'|'system', content: 'text'}])",
        min_length=1,
    )


class AddChatHistoryResponse(BaseModel):
    """Response model for adding chat history."""

    session_id: str = Field(
        ...,
        description="Session identifier (created or existing)",
    )
    message_count: int = Field(
        ...,
        description="Number of messages added",
    )


class GetChatHistoryRequest(BaseModel):
    """Request model for getting chat history."""

    user_id: str = Field(
        ...,
        description="User identifier",
        min_length=1,
    )
    agent_id: str = Field(
        ...,
        description="Agent identifier",
        min_length=1,
    )
    session_id: str = Field(
        ...,
        description="Session identifier",
        min_length=1,
    )
    limit: Optional[int] = Field(
        default=None,
        description="Maximum number of recent messages to retrieve",
        gt=0,
    )


class MessageResponse(BaseModel):
    """Response model for a single message."""

    type: str = Field(..., description="Message type (human, ai, system)")
    content: str = Field(..., description="Message content")


class GetChatHistoryResponse(BaseModel):
    """Response model for getting chat history."""

    session_id: str = Field(..., description="Session identifier")
    messages: list[MessageResponse] = Field(..., description="Chat history messages")


class ListSessionsRequest(BaseModel):
    """Request model for listing sessions."""

    user_id: str = Field(
        ...,
        description="User identifier",
        min_length=1,
    )
    agent_id: str = Field(
        ...,
        description="Agent identifier",
        min_length=1,
    )


class SessionMetadata(BaseModel):
    """Session metadata model."""

    session_id: str = Field(..., description="Session identifier")
    user_id: str = Field(..., description="User identifier")
    agent_id: str = Field(..., description="Agent identifier")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


class ListSessionsResponse(BaseModel):
    """Response model for listing sessions."""

    sessions: list[SessionMetadata] = Field(..., description="List of sessions")


class DeleteSessionRequest(BaseModel):
    """Request model for deleting a session."""

    session_id: str = Field(
        ...,
        description="Session identifier",
        min_length=1,
    )
    user_id: str = Field(
        ...,
        description="User identifier",
        min_length=1,
    )
    agent_id: str = Field(
        ...,
        description="Agent identifier",
        min_length=1,
    )


class DeleteSessionResponse(BaseModel):
    """Response model for deleting a session."""

    success: bool = Field(..., description="Whether the deletion was successful")
    message: str = Field(..., description="Status message")


class UpdateSessionMetadataRequest(BaseModel):
    """Request model for updating session metadata."""

    session_id: str = Field(
        ...,
        description="Session identifier",
        min_length=1,
    )
    metadata: dict = Field(
        ...,
        description="Metadata to update or add",
    )


class UpdateSessionMetadataResponse(BaseModel):
    """Response model for updating session metadata."""

    success: bool = Field(..., description="Whether the update was successful")
    message: str = Field(..., description="Status message")
