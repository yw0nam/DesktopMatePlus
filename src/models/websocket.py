"""WebSocket message models and schemas."""

from enum import Enum
from typing import Any, Dict, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """WebSocket message types."""

    # Client -> Server
    AUTHORIZE = "authorize"
    PONG = "pong"
    CHAT_MESSAGE = "chat_message"
    INTERRUPT_STREAM = "interrupt_stream"

    # Server -> Client
    AUTHORIZE_SUCCESS = "authorize_success"
    AUTHORIZE_ERROR = "authorize_error"
    PING = "ping"
    CHAT_RESPONSE = "chat_response"
    STREAM_START = "stream_start"
    STREAM_END = "stream_end"
    TTS_READY_CHUNK = "tts_ready_chunk"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"


class BaseMessage(BaseModel):
    """Base WebSocket message structure."""

    type: MessageType
    id: Optional[str] = Field(default=None, description="Message ID for tracking")
    timestamp: Optional[float] = Field(default=None, description="Message timestamp")


class AuthorizeMessage(BaseMessage):
    """Client authorization message."""

    type: MessageType = MessageType.AUTHORIZE
    token: str = Field(..., description="Authentication token")


class AuthorizeSuccessMessage(BaseMessage):
    """Server authorization success response."""

    type: MessageType = MessageType.AUTHORIZE_SUCCESS
    connection_id: UUID = Field(..., description="Unique connection identifier")


class AuthorizeErrorMessage(BaseMessage):
    """Server authorization error response."""

    type: MessageType = MessageType.AUTHORIZE_ERROR
    error: str = Field(..., description="Error message")


class PingMessage(BaseMessage):
    """Server ping message for heartbeat."""

    type: MessageType = MessageType.PING


class PongMessage(BaseMessage):
    """Client pong response for heartbeat."""

    type: MessageType = MessageType.PONG


class ChatMessage(BaseMessage):
    """Client chat message."""

    type: MessageType = MessageType.CHAT_MESSAGE
    content: str = Field(..., description="Chat message content")
    agent_id: str = Field(..., description="Persistent agent identifier")
    user_id: str = Field(..., description="Persistent user/client identifier")
    conversation_id: Optional[UUID] = Field(
        default=None,
        description="Persistent conversation identifier, First message in a new conversation if None, Note should be None or UUID",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata for the message available option: {'limit': int} to limit short-term memory messages",
    )


class InterruptStreamMessage(BaseMessage):
    """Client message to interrupt active stream."""

    type: MessageType = MessageType.INTERRUPT_STREAM
    turn_id: Optional[str] = Field(
        default=None,
        description="Specific turn ID to interrupt, or None for all active turns",
    )


class ChatResponseMessage(BaseMessage):
    """Server chat response message."""

    type: MessageType = MessageType.CHAT_RESPONSE
    content: str = Field(..., description="Response content")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional metadata"
    )


class ErrorMessage(BaseMessage):
    """Server error message."""

    type: MessageType = MessageType.ERROR
    error: str = Field(..., description="Error message")
    code: Optional[int] = Field(default=None, description="Error code")


# Union type for all possible client messages
ClientMessage = Union[
    AuthorizeMessage,
    PongMessage,
    ChatMessage,
    InterruptStreamMessage,
]

# Union type for all possible server messages
ServerMessage = Union[
    AuthorizeSuccessMessage,
    AuthorizeErrorMessage,
    PingMessage,
    ChatResponseMessage,
    ErrorMessage,
]

# Union type for all messages
WebSocketMessage = Union[ClientMessage, ServerMessage]
