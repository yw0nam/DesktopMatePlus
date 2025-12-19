"""TTS API request and response models."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    """Request model for TTS synthesis."""

    text: str = Field(
        ...,
        description="Text to synthesize into speech",
        min_length=1,
    )
    reference_id: Optional[str] = Field(
        default=None,
        description="Reference voice ID for voice cloning (provider-specific)",
    )
    output_format: Literal["bytes", "base64"] = Field(
        default="base64",
        description="Output format for audio data",
    )
    audio_format: Literal["wav", "mp3"] = Field(
        default="mp3",
        description="Audio codec format (wav or mp3)",
    )


class TTSResponse(BaseModel):
    """Response model for TTS synthesis."""

    audio_data: str = Field(
        ...,
        description="Audio data in base64 format or bytes representation",
    )
    format: str = Field(
        ...,
        description="Format of the audio data (base64 or bytes)",
    )


__all__ = ["TTSRequest", "TTSResponse"]
