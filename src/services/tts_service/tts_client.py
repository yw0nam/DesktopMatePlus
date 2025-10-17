"""
TTS Client - Public interface for Text-to-Speech functionality.

This module provides the public API expected by the rest of the application,
including the functions specified in task 8.
"""

from typing import Optional

from .service import (
    TTSService,
    initialize_tts_service,
    synthesize_speech,
)

# Re-export the main classes and functions for external use
__all__ = [
    "TTSClient",
    "synthesize_speech",
    "initialize_tts_client",
    "get_tts_client",
]


class TTSClient:
    """
    Client wrapper for TTS service operations.

    Provides a simple interface for external modules to interact with TTS functionality.
    """

    def __init__(self, service: TTSService):
        self._service = service

    def synthesize_speech(
        self, text: str, reference_id: Optional[str] = None
    ) -> Optional[bytes]:
        """
        Synthesize speech from text and return audio bytes.

        Args:
            text: Text to synthesize
            reference_id: Optional voice reference ID

        Returns:
            Audio bytes or None on failure
        """
        return synthesize_speech(text=text, reference_id=reference_id)

    def is_healthy(self) -> dict:
        """Check TTS service health."""
        return self._service.is_healthy()


# Global client instance
_tts_client: Optional[TTSClient] = None


def initialize_tts_client(
    fish_speech_url: str = "http://localhost:8080/v1/tts",
    fish_speech_api_key: Optional[str] = None,
) -> TTSClient:
    """
    Initialize the global TTS client.

    Args:
        fish_speech_url: Fish Speech API URL
        fish_speech_api_key: Optional API key

    Returns:
        Initialized TTSClient instance
    """
    global _tts_client

    service = initialize_tts_service(
        fish_speech_url=fish_speech_url,
        fish_speech_api_key=fish_speech_api_key,
    )

    _tts_client = TTSClient(service)
    return _tts_client


def get_tts_client() -> TTSClient:
    """
    Get the global TTS client instance.

    Returns:
        TTSClient instance

    Raises:
        RuntimeError: If TTS client hasn't been initialized
    """
    if _tts_client is None:
        raise RuntimeError(
            "TTS client not initialized. Call initialize_tts_client() first."
        )
    return _tts_client
