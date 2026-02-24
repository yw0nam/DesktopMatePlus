"""Vision-Language Model configuration package."""

from .openai import OpenAIVLMConfig
from .vlm import VLMConfig

__all__ = ["VLMConfig", "OpenAIVLMConfig"]
