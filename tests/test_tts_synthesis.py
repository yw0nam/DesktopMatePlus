"""
Tests for TTS synthesis functionality.

Tests the TTS service integration with new factory pattern.
"""

from unittest.mock import Mock, patch

import pytest

from src.services.tts_service.fish_speech import FishSpeechTTS
from src.services.tts_service.service import TTSService
from src.services.tts_service.tts_factory import TTSFactory


class TestTTSFactory:
    """Test TTS factory functionality."""

    def test_get_fish_local_tts_engine(self):
        """Test creating Fish TTS engine via factory."""
        tts_engine = TTSFactory.get_tts_engine(
            "fish_local_tts",
            base_url="http://localhost:8080/v1/tts",
            api_key="test_key",
        )
        assert isinstance(tts_engine, FishSpeechTTS)
        assert isinstance(tts_engine, TTSService)

    def test_get_unknown_engine_type(self):
        """Test factory raises error for unknown engine type."""
        with pytest.raises(ValueError, match="Unknown TTS engine type"):
            TTSFactory.get_tts_engine("unknown_engine")

    def test_factory_with_all_params(self):
        """Test factory with all configuration parameters."""
        tts_engine = TTSFactory.get_tts_engine(
            "fish_local_tts",
            base_url="http://test.com/v1/tts",
            api_key="key123",
            seed=42,
            streaming=True,
            use_memory_cache="on",
            chunk_length=250,
            max_new_tokens=2048,
            top_p=0.9,
            repetition_penalty=1.5,
            temperature=0.8,
        )
        assert isinstance(tts_engine, FishSpeechTTS)
        assert tts_engine.url == "http://test.com/v1/tts"
        assert tts_engine.api_key == "key123"
        assert tts_engine.seed == 42
        assert tts_engine.streaming is True


class TestFishSpeechTTS:
    """Test Fish Speech TTS functionality."""

    @patch("src.services.tts_service.fish_speech.requests.post")
    def test_generate_speech_success(self, mock_post):
        """Test successful speech synthesis."""
        # Mock the HTTP response
        mock_response = Mock()
        mock_response.content = b"fake_audio_data"
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Create TTS instance
        tts = FishSpeechTTS(url="http://localhost:8080/v1/tts")

        # Test synthesis
        result = tts.generate_speech("Hello world", output_format="bytes")
        assert result == b"fake_audio_data"

        # Verify the API was called
        assert mock_post.called

    def test_generate_speech_empty_text(self):
        """Test synthesis with empty text."""
        tts = FishSpeechTTS(url="http://localhost:8080/v1/tts")

        # Test with empty text
        result = tts.generate_speech("")
        assert result is None

        # Test with whitespace only
        result = tts.generate_speech("   ")
        assert result is None

    @patch("src.services.tts_service.fish_speech.requests.post")
    def test_generate_speech_base64_format(self, mock_post):
        """Test synthesis with base64 output format."""
        # Mock the HTTP response
        mock_response = Mock()
        mock_response.content = b"audio_data"
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        tts = FishSpeechTTS(url="http://localhost:8080/v1/tts")

        # Test synthesis with base64 format
        result = tts.generate_speech("Hello", output_format="base64")
        assert isinstance(result, str)
        assert result  # Should be a non-empty base64 string

    @patch("src.services.tts_service.fish_speech.requests.post")
    def test_generate_speech_api_failure(self, mock_post):
        """Test synthesis when API fails."""
        # Mock the HTTP response to raise an exception
        mock_post.side_effect = Exception("Connection error")

        tts = FishSpeechTTS(url="http://localhost:8080/v1/tts")

        # Test synthesis
        result = tts.generate_speech("Hello world")
        assert result is None

    @patch("src.services.tts_service.fish_speech.requests.post")
    def test_health_check_healthy(self, mock_post):
        """Test health check when TTS is healthy."""
        # Mock successful response
        mock_response = Mock()
        mock_response.content = b"test_audio"
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        tts = FishSpeechTTS(url="http://localhost:8080/v1/tts")

        # Test health check
        is_healthy, message = tts.is_healthy()
        assert is_healthy is True
        assert "healthy" in message.lower()

    @patch("src.services.tts_service.fish_speech.requests.post")
    def test_health_check_unhealthy(self, mock_post):
        """Test health check when TTS is unhealthy."""
        # Mock failed response
        mock_post.side_effect = Exception("Service unavailable")

        tts = FishSpeechTTS(url="http://localhost:8080/v1/tts")

        # Test health check
        is_healthy, message = tts.is_healthy()
        assert is_healthy is False
        assert "empty result" in message.lower() or "failed" in message.lower()


class TestTTSConfiguration:
    """Test TTS configuration integration."""

    def test_fish_speech_with_custom_params(self):
        """Test Fish Speech TTS with custom parameters."""
        tts = FishSpeechTTS(
            url="http://custom.com/tts",
            api_key="custom_key",
            seed=42,
            streaming=True,
            use_memory_cache="on",
            chunk_length=250,
            max_new_tokens=2048,
            top_p=0.9,
            repetition_penalty=1.5,
            temperature=0.8,
        )

        assert tts.url == "http://custom.com/tts"
        assert tts.api_key == "custom_key"
        assert tts.seed == 42
        assert tts.streaming is True
        assert tts.use_memory_cache == "on"
        assert tts.chunk_length == 250
        assert tts.max_new_tokens == 2048
        assert tts.top_p == 0.9
        assert tts.repetition_penalty == 1.5
        assert tts.temperature == 0.8


# Integration test
class TestTTSIntegration:
    """Integration tests for the complete TTS system."""

    @patch("src.services.tts_service.fish_speech.requests.post")
    def test_full_integration_mock_api(self, mock_post):
        """Test full integration with mocked Fish Speech API."""
        # Mock the HTTP response
        mock_response = Mock()
        mock_response.content = b"fake_wav_audio_data"
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Initialize the service via factory
        tts_engine = TTSFactory.get_tts_engine(
            "fish_local_tts", base_url="http://localhost:8080/v1/tts"
        )

        # Test synthesis
        result = tts_engine.generate_speech("Hello, this is a test!")

        # Verify result
        assert result == b"fake_wav_audio_data"

        # Verify API call was made
        mock_post.assert_called_once()

        # Verify health check works
        is_healthy, message = tts_engine.is_healthy()
        assert is_healthy is True
