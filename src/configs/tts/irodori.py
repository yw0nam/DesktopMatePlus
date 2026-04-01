"""Irodori TTS configuration."""

from pydantic import BaseModel, Field


class IrodoriTTSConfig(BaseModel):
    """Configuration for Irodori TTS (Aratako/Irodori-TTS-500M-v2)."""

    base_url: str = Field(
        ..., description="Base URL for Irodori TTS server (e.g. http://localhost:8000)"
    )
    ref_audio_dir: str | None = Field(
        None,
        description="Directory containing voice subdirs ({name}/audio.wav). None = no-reference mode.",
    )
    seconds: float = Field(30.0, description="Duration hint for synthesis in seconds")
    num_steps: int = Field(40, description="Number of diffusion steps")
    cfg_scale_text: float = Field(3.0, description="Text CFG scale")
    cfg_scale_speaker: float = Field(5.0, description="Speaker CFG scale")
    seed: int | None = Field(
        None, description="Random seed for deterministic generation (None = random)"
    )
    timeout: float = Field(60.0, description="HTTP request timeout in seconds")
