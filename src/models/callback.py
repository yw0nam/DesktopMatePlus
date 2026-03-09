"""Pydantic models for NanoClaw callback endpoint."""

from typing import Literal

from pydantic import BaseModel, Field


class NanoClawCallbackRequest(BaseModel):
    """Payload received from NanoClaw when a task completes or fails."""

    task_id: str = Field(..., description="Unique task identifier")
    status: Literal["done", "failed"] = Field(
        ..., description="Task completion status"
    )
    summary: str = Field(..., description="Result summary or failure reason")


class NanoClawCallbackResponse(BaseModel):
    """Response returned to NanoClaw after processing callback."""

    task_id: str
    status: str
    message: str
