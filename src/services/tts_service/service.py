"""
TTS Service - Handles text-to-speech synthesis with multiple providers.

This module provides a unified interface for TTS services like Fish Speech, OpenAI, etc.
"""

from abc import ABC, abstractmethod
from typing import Literal, Optional


class TTSService(ABC):
    """Abstract base class for TTS providers."""

    @abstractmethod
    def generate_speech(
        self,
        text: str,
        reference_id: Optional[str] = None,
        output_format: Literal["bytes", "base64", "file"] = "bytes",
        output_filename: Optional[str] = None,
    ) -> Optional[bytes | str | bool]:
        """
        Generate speech from text.

        Args:
            text: The text to synthesize
            reference_id: Reference voice ID (provider-specific)
            output_format: Output format ('bytes', 'base64', 'file')
            output_filename: Filename when output_format is 'file'

        Returns:
            Audio data in requested format or None on failure
        """
        pass

    @abstractmethod
    def is_healthy(self) -> tuple[bool, str]:
        """
        Check if the TTS provider is healthy and ready.

        Returns:
            Tuple of (is_healthy: bool, message: str)
        """
        pass
