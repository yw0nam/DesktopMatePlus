"""Main Text-to-Speech configuration."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

from .fish_local import FishLocalTTSConfig


class TTSConfig(BaseModel):
    """Configuration for Text-to-Speech."""

    tts_model: Literal["fish_local_tts",] = Field(
        ..., description="Text-to-speech model to use"
    )

    fish_local_tts: Optional[FishLocalTTSConfig] = Field(
        None, description="Configuration for Fish local TTS"
    )
