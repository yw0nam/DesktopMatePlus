"""Text-to-Speech configuration package."""

from .irodori import IrodoriTTSConfig
from .vllm_omni import VLLMOmniTTSConfig

__all__ = ["IrodoriTTSConfig", "VLLMOmniTTSConfig"]
