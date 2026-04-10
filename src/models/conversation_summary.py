"""Conversation summary model."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ConversationSummary(BaseModel):
    """Summary of a conversation slice for STM compression."""

    session_id: str = Field(..., description="Session identifier")
    summary_text: str = Field(..., description="LLM-generated summary of the slice")
    turn_range_start: int = Field(
        ..., description="First human turn index in the slice"
    )
    turn_range_end: int = Field(..., description="Last human turn index in the slice")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when the summary was created",
    )
