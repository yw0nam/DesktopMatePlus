"""
TTS Service Package

Provides text-to-speech synthesis capabilities with support for multiple providers.
Currently supports Fish Speech TTS.
"""

from .fish_speech import FishSpeechTTS
from .service import TTSService
from .tts_factory import TTSFactory

__all__ = [
    "TTSService",
    "FishSpeechTTS",
    "TTSFactory",
]
