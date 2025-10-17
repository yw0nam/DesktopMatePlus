"""
TTS Service - Handles text-to-speech synthesis with multiple providers.

This module provides a unified interface for TTS services like Fish Speech, OpenAI, etc.
"""

import logging
from abc import ABC, abstractmethod
from typing import Literal, Optional

from .fish_speech import FishSpeechTTS

logger = logging.getLogger(__name__)


class TTSProvider(ABC):
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


class FishSpeechProvider(TTSProvider):
    """Fish Speech TTS provider implementation."""

    def __init__(
        self, url: str = "http://localhost:8080/v1/tts", api_key: Optional[str] = None
    ):
        self.client = FishSpeechTTS(url=url, api_key=api_key)
        self.url = url

    def generate_speech(
        self,
        text: str,
        reference_id: Optional[str] = None,
        output_format: Literal["bytes", "base64", "file"] = "bytes",
        output_filename: Optional[str] = None,
    ) -> Optional[bytes | str | bool]:
        """Generate speech using Fish Speech API."""
        try:
            return self.client.generate_speech(
                raw_text=text,
                reference_id=reference_id,
                output_format=output_format,
                output_filename=output_filename,
            )
        except Exception as e:
            logger.error(f"Fish Speech TTS generation failed: {e}")
            return None

    def is_healthy(self) -> tuple[bool, str]:
        """Check Fish Speech TTS health by attempting a minimal synthesis."""
        try:
            # Try a simple synthesis as a health check
            result = self.client.generate_speech(raw_text="test", output_format="bytes")
            if result:
                return True, "Fish Speech TTS is healthy"
            else:
                return False, "Fish Speech TTS returned empty result"
        except Exception as e:
            return False, f"Fish Speech TTS health check failed: {str(e)}"


class TTSService:
    """
    Unified TTS service that manages multiple TTS providers.

    This service acts as a facade for different TTS providers and handles
    provider selection, fallback, and error handling.
    """

    def __init__(
        self,
        primary_provider: TTSProvider,
        fallback_provider: Optional[TTSProvider] = None,
    ):
        self.primary_provider = primary_provider
        self.fallback_provider = fallback_provider

    def synthesize_speech(
        self,
        text: str,
        reference_id: Optional[str] = None,
        output_format: Literal["bytes", "base64", "file"] = "bytes",
        output_filename: Optional[str] = None,
    ) -> Optional[bytes | str | bool]:
        """
        Main interface for speech synthesis with fallback support.

        Args:
            text: Text to synthesize
            reference_id: Voice reference ID
            output_format: Output format
            output_filename: Output filename for 'file' format

        Returns:
            Audio data in requested format or None on failure
        """
        if not text or not text.strip():
            logger.info("Empty text provided, skipping synthesis")
            return None

        # Try primary provider first
        logger.info(
            f"Attempting synthesis with primary provider: {type(self.primary_provider).__name__}"
        )
        result = self.primary_provider.generate_speech(
            text=text,
            reference_id=reference_id,
            output_format=output_format,
            output_filename=output_filename,
        )

        if result is not None:
            logger.info("Primary provider synthesis successful")
            return result

        # Fallback to secondary provider if available
        if self.fallback_provider:
            logger.warning("Primary provider failed, attempting fallback provider")
            result = self.fallback_provider.generate_speech(
                text=text,
                reference_id=reference_id,
                output_format=output_format,
                output_filename=output_filename,
            )
            if result is not None:
                logger.info("Fallback provider synthesis successful")
                return result

        logger.error("All TTS providers failed")
        return None

    def is_healthy(self) -> dict[str, dict[str, object]]:
        """
        Check health of all configured TTS providers.

        Returns:
            Dict with provider health status information
        """
        health_status = {}

        # Check primary provider
        primary_healthy, primary_message = self.primary_provider.is_healthy()
        health_status["primary"] = {
            "healthy": primary_healthy,
            "message": primary_message,
            "provider": type(self.primary_provider).__name__,
        }

        # Check fallback provider if available
        if self.fallback_provider:
            fallback_healthy, fallback_message = self.fallback_provider.is_healthy()
            health_status["fallback"] = {
                "healthy": fallback_healthy,
                "message": fallback_message,
                "provider": type(self.fallback_provider).__name__,
            }

        return health_status


# Global TTS service instance
_tts_service: Optional[TTSService] = None


def initialize_tts_service(
    fish_speech_url: str = "http://localhost:8080/v1/tts",
    fish_speech_api_key: Optional[str] = None,
) -> TTSService:
    """
    Initialize the global TTS service with Fish Speech as primary provider.

    Args:
        fish_speech_url: Fish Speech API URL
        fish_speech_api_key: Optional API key

    Returns:
        Initialized TTSService instance
    """
    global _tts_service

    fish_provider = FishSpeechProvider(
        url=fish_speech_url,
        api_key=fish_speech_api_key,
    )

    _tts_service = TTSService(primary_provider=fish_provider)
    logger.info(f"TTS Service initialized with Fish Speech at {fish_speech_url}")
    return _tts_service


def get_tts_service() -> TTSService:
    """
    Get the global TTS service instance.

    Returns:
        TTSService instance

    Raises:
        RuntimeError: If TTS service hasn't been initialized
    """
    if _tts_service is None:
        raise RuntimeError(
            "TTS service not initialized. Call initialize_tts_service() first."
        )
    return _tts_service


def synthesize_speech(text: str, reference_id: Optional[str] = None) -> Optional[bytes]:
    """
    Convenience function for speech synthesis that returns bytes.

    This is the main function expected by task 8: synthesize_speech(text: str) -> bytes

    Args:
        text: Text to synthesize
        reference_id: Optional voice reference ID

    Returns:
        Audio bytes or None on failure
    """
    service = get_tts_service()
    result = service.synthesize_speech(
        text=text, reference_id=reference_id, output_format="bytes"
    )

    # Ensure we return bytes or None (not other formats)
    if isinstance(result, bytes):
        return result
    return None
