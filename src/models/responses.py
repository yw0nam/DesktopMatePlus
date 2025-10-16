"""Response models for API endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ModuleStatus(BaseModel):
    """Status of an individual module."""

    name: str = Field(..., description="Module name (VLM, TTS, or Agent)")
    ready: bool = Field(..., description="Whether the module is ready")
    error: Optional[str] = Field(
        None, description="Error message if module is not ready"
    )


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str = Field(..., description="Overall status: 'healthy' or 'unhealthy'")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Time of health check"
    )
    modules: list[ModuleStatus] = Field(..., description="Status of individual modules")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "timestamp": "2025-10-16T12:00:00",
                "modules": [
                    {"name": "VLM", "ready": True, "error": None},
                    {"name": "TTS", "ready": True, "error": None},
                    {"name": "Agent", "ready": True, "error": None},
                ],
            }
        }
    )
