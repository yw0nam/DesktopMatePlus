"""
TTS Service - Handles text-to-speech synthesis with multiple providers.

This module provides a unified interface for TTS services like Fish Speech, OpenAI, etc.
"""

from abc import ABC, abstractmethod
from typing import Literal


class TTSService(ABC):
    """Abstract base class for TTS providers."""

    @abstractmethod
    def generate_speech(
        self,
        text: str,
        reference_id: str | None = None,
        output_format: Literal["bytes", "base64", "file"] = "bytes",
        output_filename: str | None = None,
        audio_format: Literal["wav", "mp3"] = "mp3",
    ) -> bytes | str | bool | None:
        """
        Generate speech from text.

        Args:
            text: The text to synthesize
            reference_id: Reference voice ID (provider-specific)
            output_format: Output format ('bytes', 'base64', 'file')
            output_filename: Filename when output_format is 'file'
            audio_format: Audio codec format ('wav' or 'mp3')

        Returns:
            Audio data in requested format or None on failure
        """
        pass

    @abstractmethod
    def list_voices(self) -> list[str]:
        """Return available reference voice IDs."""
        pass

    @abstractmethod
    def is_healthy(self) -> tuple[bool, str]:
        """
        Check if the TTS provider is healthy and ready.

        Returns:
            Tuple of (is_healthy: bool, message: str)
        """
        pass
