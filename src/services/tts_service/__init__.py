"""
TTS Service Package

Provides text-to-speech synthesis capabilities with support for multiple providers.
Currently supports Fish Speech TTS.
"""

from .service import (
    FishSpeechProvider,
    TTSProvider,
    TTSService,
    get_tts_service,
    initialize_tts_service,
    synthesize_speech,
)
from .tts_client import (
    TTSClient,
    get_tts_client,
    initialize_tts_client,
)

__all__ = [
    # Main service classes
    "TTSProvider",
    "FishSpeechProvider",
    "TTSService",
    # Service functions
    "initialize_tts_service",
    "get_tts_service",
    "synthesize_speech",
    # Client interface
    "TTSClient",
    "initialize_tts_client",
    "get_tts_client",
]
