"""WebSocket message models and schemas."""

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# Max base64 image size: ~6MB corresponds to ~4.5MB binary file
_MAX_IMAGE_BASE64_BYTES = 6 * 1024 * 1024


class MessageType(StrEnum):
    """WebSocket message types."""

    # Client -> Server
    AUTHORIZE = "authorize"
    PONG = "pong"
    CHAT_MESSAGE = "chat_message"
    INTERRUPT_STREAM = "interrupt_stream"
    HITL_RESPONSE = "hitl_response"

    # Server -> Client
    AUTHORIZE_SUCCESS = "authorize_success"
    AUTHORIZE_ERROR = "authorize_error"
    PING = "ping"
    STREAM_START = "stream_start"
    STREAM_TOKEN = "stream_token"
    STREAM_END = "stream_end"
    TTS_CHUNK = "tts_chunk"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    AVATAR_CONFIG_FILES = "avatar_config_files"
    AVATAR_CONFIG_SWITCHED = "avatar_config_switched"
    HITL_REQUEST = "hitl_request"
    SET_MODEL_AND_CONF = "set_model_and_conf"


class BaseMessage(BaseModel):
    """Base WebSocket message structure."""

    type: MessageType
    id: str | None = Field(default=None, description="Message ID for tracking")
    timestamp: float | None = Field(default=None, description="Message timestamp")


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


class ImageUrl(BaseModel):
    """OpenAI-compatible image URL object."""

    url: str = Field(..., description="Image URL or base64 data URI")
    detail: str = Field(
        default="auto", description="Image detail level: auto, low, or high"
    )


class ImageContent(BaseModel):
    """OpenAI-compatible image content block."""

    type: str = Field(
        default="image_url", description="Content type, must be 'image_url'"
    )
    image_url: ImageUrl = Field(..., description="Image URL object")

    @field_validator("image_url")
    @classmethod
    def validate_image_size(cls, v: ImageUrl) -> ImageUrl:
        if v.url.startswith("data:"):
            parts = v.url.split(",", 1)
            if len(parts) == 2 and len(parts[1]) > _MAX_IMAGE_BASE64_BYTES:
                size_mb = len(parts[1]) / 1024 / 1024
                max_mb = _MAX_IMAGE_BASE64_BYTES // 1024 // 1024
                raise ValueError(
                    f"Image too large ({size_mb:.1f}MB base64, max {max_mb}MB). "
                    "Please resize the image before sending."
                )
        return v


class ChatMessage(BaseMessage):
    """Client chat message."""

    type: MessageType = MessageType.CHAT_MESSAGE
    content: str = Field(..., description="Chat message content")
    agent_id: str = Field(..., description="Persistent agent identifier")
    user_id: str = Field(..., description="Persistent user/client identifier")
    persona_id: str = Field(
        default="yuri",
        description="Persona identifier — matches a key in yaml_files/personas.yml",
    )
    images: list[ImageContent] | None = Field(
        default=None,
        description="Optional images in OpenAI-compatible format",
    )
    limit: int | None = Field(
        default=10,
        description="Optional limit for short-term memory messages",
    )
    tts_enabled: bool = Field(
        default=True,
        description="Whether TTS synthesis is enabled for this message",
    )
    reference_id: str | None = Field(
        default=None,
        description="TTS voice reference identifier",
    )
    session_id: UUID | None = Field(
        default=None,
        description="Persistent conversation identifier, First message in a new conversation if None, Note should be None or UUID",
    )
    metadata: dict[str, Any] | None = Field(
        default=None, description="Additional metadata for the message"
    )


class InterruptStreamMessage(BaseMessage):
    """Client message to interrupt active stream."""

    type: MessageType = MessageType.INTERRUPT_STREAM
    turn_id: str | None = Field(
        default=None,
        description="Specific turn ID to interrupt, or None for all active turns",
    )


class HitLResponseMessage(BaseMessage):
    """Client message with approval decision."""

    type: MessageType = MessageType.HITL_RESPONSE
    request_id: str = Field(..., description="Must match the hitl_request request_id")
    approved: bool = Field(..., description="True to execute, False to deny")


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
    session_id: str


class StreamTokenMessage(BaseMessage):
    """Server message for a streaming response token."""

    type: MessageType = MessageType.STREAM_TOKEN
    chunk: str
    node: str | None = None


class ToolCallMessage(BaseMessage):
    """Server message for a tool call."""

    type: MessageType = MessageType.TOOL_CALL
    tool_name: str
    args: str
    node: str | None = None


class ToolResultMessage(BaseMessage):
    """Server message for a tool result."""

    type: MessageType = MessageType.TOOL_RESULT
    result: str
    node: str | None = None


class StreamEndMessage(BaseMessage):
    """Server message indicating the end of a stream."""

    type: MessageType = MessageType.STREAM_END
    turn_id: str
    session_id: str
    content: str


class HitLRequestMessage(BaseMessage):
    """Server message requesting user approval for a tool call."""

    type: MessageType = MessageType.HITL_REQUEST
    request_id: str = Field(..., description="Unique ID linking request/response")
    tool_name: str = Field(..., description="Name of the tool requiring approval")
    tool_args: dict[str, str] = Field(..., description="Tool call arguments")
    session_id: str = Field(..., description="Session ID for graph resume")


# TimelineKeyframe matches desktop-homunculus POST /vrm/{entity}/speech/timeline format.
# { "duration": float, "targets": { "expression_name": weight } }
TimelineKeyframe = dict[str, float | dict[str, float]]


class TtsChunkMessage(BaseMessage):
    """Server message with TTS synthesis result and keyframe animation metadata.

    Backend → desktop-homunculus. Sent after TTS synthesis completes for each sentence.
    audio_base64 is None when TTS is disabled (tts_enabled=False) or synthesis failed.
    keyframes drives the VRM expression timeline via POST /vrm/{entity}/speech/timeline.
    """

    type: MessageType = MessageType.TTS_CHUNK
    sequence: int = Field(
        ..., description="Sequence number within the turn, starting from 0"
    )
    text: str = Field(..., description="Text used for TTS synthesis")
    audio_base64: str | None = Field(
        default=None,
        description="WAV audio encoded as base64. None means skip audio playback.",
    )
    emotion: str | None = Field(default=None, description="Detected emotion tag")
    keyframes: list[TimelineKeyframe] = Field(
        ...,
        description=(
            "Expression timeline keyframes for desktop-homunculus VRM animation. "
            "Each entry: {duration: float, targets: {expression_name: weight}}."
        ),
    )


class ErrorMessage(BaseMessage):
    """Server error message."""

    type: MessageType = MessageType.ERROR
    error: str
    code: int | None = None


# =================================================================================
# Union Types
# =================================================================================

# Union type for all possible client messages
ClientMessage = (
    AuthorizeMessage
    | PongMessage
    | ChatMessage
    | InterruptStreamMessage
    | HitLResponseMessage
)

# Union type for all possible server messages
ServerMessage = (
    AuthorizeSuccessMessage
    | AuthorizeErrorMessage
    | PingMessage
    | StreamStartMessage
    | StreamTokenMessage
    | ToolCallMessage
    | ToolResultMessage
    | StreamEndMessage
    | HitLRequestMessage
    | TtsChunkMessage
    | ErrorMessage
)

# Union type for all messages
WebSocketMessage = ClientMessage | ServerMessage
