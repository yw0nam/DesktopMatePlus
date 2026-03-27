"""Fish Local TTS configuration."""

import os
from typing import Literal

from pydantic import BaseModel, Field


class VLLMOmniTTSConfig(BaseModel):
    """Configuration for VLLM Omni TTS."""

    base_url: str = Field(..., description="Base URL for local VLLM Omni TTS server")
    api_key: str | None = Field(default_factory=lambda: os.getenv("TTS_API_KEY"))
    model: str = Field("chat_model", description="Model name to use for synthesis")
    task_type: str = Field(
        "Base", description="Task type for the TTS request (e.g. 'Base')"
    )
    response_format: Literal["mp3", "wav"] = Field(
        "mp3",
        description="Audio output format ('mp3' or 'wav')",
    )
    ref_audio_dir: str = Field(
        "./resources/references_voices",
        description="Directory containing reference voice subdirectories",
    )
    timeout: float = Field(300.0, description="Request timeout in seconds")
