"""Text-to-Speech configuration package."""

from .fish_local import FishLocalTTSConfig
from .irodori import IrodoriTTSConfig
from .vllm_omni import VLLMOmniTTSConfig

__all__ = ["FishLocalTTSConfig", "IrodoriTTSConfig", "VLLMOmniTTSConfig"]
