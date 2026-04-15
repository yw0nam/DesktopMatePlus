"""Pydantic models for proactive talking webhook API."""

from pydantic import BaseModel, Field


class ProactiveTriggerRequest(BaseModel):
    session_id: str = Field(..., description="Target session/connection ID")
    trigger_type: str = Field(default="webhook", description="Trigger type identifier")
    prompt_key: str | None = Field(
        default=None, description="Prompt template key override"
    )
    context: str | None = Field(
        default=None, description="Additional context injected into prompt"
    )


class ProactiveTriggerResponse(BaseModel):
    status: str = Field(..., description="'triggered' or 'skipped'")
    turn_id: str | None = Field(default=None, description="Turn ID if triggered")
    reason: str | None = Field(default=None, description="Skip reason if skipped")
