"""TTS API response models."""

from pydantic import BaseModel


class VoicesResponse(BaseModel):
    """Response model for the list-voices endpoint."""

    voices: list[str]


__all__ = ["VoicesResponse"]
