"""Text-to-Speech configuration package."""

from .fish_local import FishLocalTTSConfig
from .vllm_omni import VLLMOmniTTSConfig

__all__ = ["FishLocalTTSConfig", "VLLMOmniTTSConfig"]
