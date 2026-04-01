"""
TTS Service Package

Provides text-to-speech synthesis capabilities with support for multiple providers.
Supports Irodori TTS and VLLM Omni TTS.
"""

from .service import TTSService
from .tts_factory import TTSFactory

__all__ = [
    "TTSFactory",
    "TTSService",
]
