"""TTS API response models."""

from pydantic import BaseModel


class VoicesResponse(BaseModel):
    """Response model for the list-voices endpoint."""

    voices: list[str]


class SpeakRequest(BaseModel):
    """Request model for the speak endpoint."""

    text: str
    reference_id: str | None = None


class SpeakResponse(BaseModel):
    """Response model for the speak endpoint."""

    audio_base64: str


__all__ = ["SpeakRequest", "SpeakResponse", "VoicesResponse"]
