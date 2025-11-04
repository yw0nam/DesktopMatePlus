# config_manager/tts.py
from typing import Literal, Optional

from pydantic import BaseModel, Field


class FishLocalTTSConfig(BaseModel):
    """Configuration for Fish Local TTS."""

    base_url: str = Field(..., description="Base URL for local Fish TTS server")
    api_key: Optional[str] = Field(
        None, description="API key for authentication (optional for local usage)"
    )
    seed: Optional[int] = Field(
        None, description="Seed for deterministic generation (None = randomized)"
    )
    streaming: bool = Field(
        False, description="Whether to enable streaming audio synthesis"
    )
    use_memory_cache: Literal["on", "off"] = Field(
        "off", description="Whether to cache reference encodings in memory"
    )
    chunk_length: int = Field(
        200, description="Chunk size for audio synthesis (in tokens)"
    )
    max_new_tokens: int = Field(
        1024, description="Maximum number of tokens to generate"
    )
    top_p: float = Field(0.7, description="Top-p sampling value (for diversity)")
    repetition_penalty: float = Field(
        1.2, description="Penalty to avoid repeating phrases"
    )
    temperature: float = Field(
        0.7, description="Sampling temperature (controls creativity)"
    )


class TTSConfig(BaseModel):
    """Configuration for Text-to-Speech."""

    tts_model: Literal["fish_local_tts",] = Field(
        ..., description="Text-to-speech model to use"
    )

    fish_local_tts: Optional[FishLocalTTSConfig] = Field(
        None, description="Configuration for Fish local TTS"
    )
