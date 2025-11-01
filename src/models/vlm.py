"""VLM API request and response models."""

from pydantic import BaseModel, Field


class VLMRequest(BaseModel):
    """Request model for VLM vision analysis."""

    image: str = Field(
        ...,
        description="Image data as base64-encoded string or URL",
    )
    prompt: str = Field(
        default="Describe this image",
        description="Text prompt for image analysis",
    )


class VLMResponse(BaseModel):
    """Response model for VLM vision analysis."""

    description: str = Field(
        ...,
        description="Textual description of the image",
    )


__all__ = ["VLMRequest", "VLMResponse"]
