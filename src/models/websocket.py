"""WebSocket message models and schemas."""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
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
    STREAM_START = "stream_start"
    STREAM_TOKEN = "stream_token"
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


# =================================================================================
# Client -> Server Messages
# =================================================================================


class AuthorizeMessage(BaseMessage):
    """Client authorization message."""

    type: MessageType = MessageType.AUTHORIZE
    token: str = Field(..., description="Authentication token")


class PongMessage(BaseMessage):
    """Client pong response for heartbeat."""

    type: MessageType = MessageType.PONG


class ChatMessage(BaseMessage):
    """Client chat message."""

    type: MessageType = MessageType.CHAT_MESSAGE
    content: str = Field(..., description="Chat message content")
    agent_id: str = Field(..., description="Persistent agent identifier")
    user_id: str = Field(..., description="Persistent user/client identifier")
    persona: str = Field(
        default="You are a helpful 3D desktop assistant, Yuri who is the friendly but sometimes mischievous AI companion integrated into a 3D desktop environment. You assist users with various tasks, provide information, and engage in casual conversation, all while maintaining a playful and witty demeanor.",
        description="Persona or behavior profile for the agent",
    )
    images: Optional[List[str]] = Field(
        default=None,
        description="Optional images included in the message, each as a URL or base64 string",
    )
    limit: Optional[int] = Field(
        default=10,
        description="Optional limit for short-term memory messages",
    )
    conversation_id: Optional[UUID] = Field(
        default=None,
        description="Persistent conversation identifier, First message in a new conversation if None, Note should be None or UUID",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional metadata for the message"
    )


class InterruptStreamMessage(BaseMessage):
    """Client message to interrupt active stream."""

    type: MessageType = MessageType.INTERRUPT_STREAM
    turn_id: Optional[str] = Field(
        default=None,
        description="Specific turn ID to interrupt, or None for all active turns",
    )


# =================================================================================
# Server -> Client Messages
# =================================================================================


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


class StreamStartMessage(BaseMessage):
    """Server message indicating the start of a stream."""

    type: MessageType = MessageType.STREAM_START
    turn_id: str
    conversation_id: str


class StreamTokenMessage(BaseMessage):
    """Server message for a streaming response token."""

    type: MessageType = MessageType.STREAM_TOKEN
    chunk: str
    node: Optional[str] = None


class ToolCallMessage(BaseMessage):
    """Server message for a tool call."""

    type: MessageType = MessageType.TOOL_CALL
    tool_name: str
    args: str
    node: Optional[str] = None


class ToolResultMessage(BaseMessage):
    """Server message for a tool result."""

    type: MessageType = MessageType.TOOL_RESULT
    result: str
    node: Optional[str] = None


class StreamEndMessage(BaseMessage):
    """Server message indicating the end of a stream."""

    type: MessageType = MessageType.STREAM_END
    turn_id: str
    conversation_id: str
    content: str


class TTSReadyChunkMessage(BaseMessage):
    """Server message with a chunk of text ready for TTS."""

    type: MessageType = MessageType.TTS_READY_CHUNK
    chunk: str
    emotion: Optional[str] = None


class ErrorMessage(BaseMessage):
    """Server error message."""

    type: MessageType = MessageType.ERROR
    error: str
    code: Optional[int] = None


# =================================================================================
# Union Types
# =================================================================================

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
    StreamStartMessage,
    StreamTokenMessage,
    ToolCallMessage,
    ToolResultMessage,
    StreamEndMessage,
    TTSReadyChunkMessage,
    ErrorMessage,
]

# Union type for all messages
WebSocketMessage = Union[ClientMessage, ServerMessage]
