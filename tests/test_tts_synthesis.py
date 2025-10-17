"""
Tests for TTS synthesis functionality.

Tests the main synthesize_speech function and TTS service integration.
"""

from unittest.mock import Mock, patch

import pytest

from src.services.tts_service.service import (
    FishSpeechProvider,
    TTSService,
    initialize_tts_service,
)
from src.services.tts_service.tts_client import (
    TTSClient,
    get_tts_client,
    initialize_tts_client,
    synthesize_speech,
)


class TestTTSClient:
    """Test TTS client functionality."""

    def test_initialize_tts_client(self):
        """Test TTS client initialization."""
        client = initialize_tts_client(fish_speech_url="http://localhost:8080/v1/tts")
        assert isinstance(client, TTSClient)

        # Verify we can get the same client instance
        same_client = get_tts_client()
        assert same_client is client

    def test_get_tts_client_not_initialized(self):
        """Test getting TTS client when not initialized raises error."""
        # Clear the global client
        import src.services.tts_service.tts_client as tts_client_module

        tts_client_module._tts_client = None

        with pytest.raises(RuntimeError, match="TTS client not initialized"):
            get_tts_client()

    @patch("src.services.tts_service.service.FishSpeechTTS")
    def test_tts_client_synthesize_speech(self, mock_fish_speech_class):
        """Test TTS client speech synthesis."""
        # Mock the Fish Speech TTS
        mock_fish_instance = Mock()
        mock_fish_instance.generate_speech.return_value = b"fake_audio_data"
        mock_fish_speech_class.return_value = mock_fish_instance

        # Initialize client
        client = initialize_tts_client()

        # Test synthesis
        result = client.synthesize_speech("Hello world")
        assert result == b"fake_audio_data"

        # Verify the underlying service was called
        mock_fish_instance.generate_speech.assert_called_once()

    @patch("src.services.tts_service.service.FishSpeechTTS")
    def test_tts_client_health_check(self, mock_fish_speech_class):
        """Test TTS client health check."""
        # Mock the Fish Speech TTS
        mock_fish_instance = Mock()
        mock_fish_instance.generate_speech.return_value = b"test_audio"
        mock_fish_speech_class.return_value = mock_fish_instance

        # Initialize client
        client = initialize_tts_client()

        # Test health check
        health = client.is_healthy()
        assert isinstance(health, dict)
        assert "primary" in health


class TestTTSService:
    """Test TTS service functionality."""

    @patch("src.services.tts_service.service.FishSpeechTTS")
    def test_initialize_tts_service(self, mock_fish_speech_class):
        """Test TTS service initialization."""
        mock_fish_instance = Mock()
        mock_fish_speech_class.return_value = mock_fish_instance

        service = initialize_tts_service(
            fish_speech_url="http://test.com/v1/tts", fish_speech_api_key="test_key"
        )

        assert isinstance(service, TTSService)

        # Verify Fish Speech was initialized with correct parameters
        mock_fish_speech_class.assert_called_once_with(
            url="http://test.com/v1/tts", api_key="test_key"
        )

    @patch("src.services.tts_service.service.FishSpeechTTS")
    def test_synthesize_speech_success(self, mock_fish_speech_class):
        """Test successful speech synthesis."""
        # Mock the Fish Speech TTS
        mock_fish_instance = Mock()
        mock_fish_instance.generate_speech.return_value = b"fake_audio_data"
        mock_fish_speech_class.return_value = mock_fish_instance

        # Initialize service
        service = initialize_tts_service()

        # Test synthesis
        result = service.synthesize_speech("Hello world")
        assert result == b"fake_audio_data"

        # Verify the Fish Speech client was called correctly
        mock_fish_instance.generate_speech.assert_called_once_with(
            raw_text="Hello world",
            reference_id=None,
            output_format="bytes",
            output_filename=None,
        )

    @patch("src.services.tts_service.service.FishSpeechTTS")
    def test_synthesize_speech_empty_text(self, mock_fish_speech_class):
        """Test synthesis with empty text."""
        mock_fish_instance = Mock()
        mock_fish_speech_class.return_value = mock_fish_instance

        service = initialize_tts_service()

        # Test with empty text
        result = service.synthesize_speech("")
        assert result is None

        # Test with whitespace only
        result = service.synthesize_speech("   ")
        assert result is None

        # Verify Fish Speech was not called
        mock_fish_instance.generate_speech.assert_not_called()

    @patch("src.services.tts_service.service.FishSpeechTTS")
    def test_synthesize_speech_provider_failure(self, mock_fish_speech_class):
        """Test synthesis when provider fails."""
        # Mock the Fish Speech TTS to return None (failure)
        mock_fish_instance = Mock()
        mock_fish_instance.generate_speech.return_value = None
        mock_fish_speech_class.return_value = mock_fish_instance

        service = initialize_tts_service()

        # Test synthesis
        result = service.synthesize_speech("Hello world")
        assert result is None

    @patch("src.services.tts_service.service.FishSpeechTTS")
    def test_tts_service_health_check(self, mock_fish_speech_class):
        """Test TTS service health check."""
        # Mock healthy Fish Speech TTS
        mock_fish_instance = Mock()
        mock_fish_instance.generate_speech.return_value = b"test_audio"
        mock_fish_speech_class.return_value = mock_fish_instance

        service = initialize_tts_service()

        # Test health check
        health = service.is_healthy()

        assert "primary" in health
        assert health["primary"]["healthy"] is True
        assert "Fish Speech TTS is healthy" in health["primary"]["message"]
        assert health["primary"]["provider"] == "FishSpeechProvider"

    @patch("src.services.tts_service.service.FishSpeechTTS")
    def test_tts_service_health_check_unhealthy(self, mock_fish_speech_class):
        """Test TTS service health check when unhealthy."""
        # Mock unhealthy Fish Speech TTS
        mock_fish_instance = Mock()
        mock_fish_instance.generate_speech.return_value = None
        mock_fish_speech_class.return_value = mock_fish_instance

        service = initialize_tts_service()

        # Test health check
        health = service.is_healthy()

        assert "primary" in health
        assert health["primary"]["healthy"] is False
        assert "returned empty result" in health["primary"]["message"]


class TestFishSpeechProvider:
    """Test Fish Speech provider functionality."""

    @patch("src.services.tts_service.service.FishSpeechTTS")
    def test_fish_speech_provider_init(self, mock_fish_speech_class):
        """Test Fish Speech provider initialization."""
        mock_fish_instance = Mock()
        mock_fish_speech_class.return_value = mock_fish_instance

        provider = FishSpeechProvider(url="http://test.com/v1/tts", api_key="test_key")

        assert provider.url == "http://test.com/v1/tts"
        mock_fish_speech_class.assert_called_once_with(
            url="http://test.com/v1/tts", api_key="test_key"
        )

    @patch("src.services.tts_service.service.FishSpeechTTS")
    def test_fish_speech_provider_generate_speech(self, mock_fish_speech_class):
        """Test Fish Speech provider speech generation."""
        mock_fish_instance = Mock()
        mock_fish_instance.generate_speech.return_value = b"audio_data"
        mock_fish_speech_class.return_value = mock_fish_instance

        provider = FishSpeechProvider()

        result = provider.generate_speech(
            text="Hello", reference_id="voice1", output_format="bytes"
        )

        assert result == b"audio_data"
        mock_fish_instance.generate_speech.assert_called_once_with(
            raw_text="Hello",
            reference_id="voice1",
            output_format="bytes",
            output_filename=None,
        )

    @patch("src.services.tts_service.service.FishSpeechTTS")
    def test_fish_speech_provider_generate_speech_exception(
        self, mock_fish_speech_class
    ):
        """Test Fish Speech provider handling exceptions."""
        mock_fish_instance = Mock()
        mock_fish_instance.generate_speech.side_effect = Exception("Connection error")
        mock_fish_speech_class.return_value = mock_fish_instance

        provider = FishSpeechProvider()

        result = provider.generate_speech("Hello")
        assert result is None


class TestGlobalFunctions:
    """Test global convenience functions."""

    @patch("src.services.tts_service.service.FishSpeechTTS")
    def test_global_synthesize_speech_function(self, mock_fish_speech_class):
        """Test the global synthesize_speech function."""
        # Mock the Fish Speech TTS
        mock_fish_instance = Mock()
        mock_fish_instance.generate_speech.return_value = b"audio_bytes"
        mock_fish_speech_class.return_value = mock_fish_instance

        # Initialize service
        initialize_tts_service()

        # Test the global function
        result = synthesize_speech("Test text")
        assert result == b"audio_bytes"

    @patch("src.services.tts_service.service.FishSpeechTTS")
    def test_global_synthesize_speech_function_non_bytes_result(
        self, mock_fish_speech_class
    ):
        """Test global function returns None for non-bytes results."""
        # Mock the Fish Speech TTS to return base64 string
        mock_fish_instance = Mock()
        mock_fish_instance.generate_speech.return_value = "base64_string"
        mock_fish_speech_class.return_value = mock_fish_instance

        # Initialize service
        initialize_tts_service()

        # Test the global function - should return None since result is not bytes
        result = synthesize_speech("Test text")
        assert result is None

    def test_global_synthesize_speech_not_initialized(self):
        """Test global function when service not initialized."""
        # Clear the global service
        import src.services.tts_service.service as service_module

        service_module._tts_service = None

        with pytest.raises(RuntimeError, match="TTS service not initialized"):
            synthesize_speech("Test text")


# Integration test
class TestTTSIntegration:
    """Integration tests for the complete TTS system."""

    @patch("src.services.tts_service.fish_speech.requests.Session.post")
    def test_full_integration_mock_api(self, mock_post):
        """Test full integration with mocked Fish Speech API."""
        # Mock the HTTP response
        mock_response = Mock()
        mock_response.content = b"fake_wav_audio_data"
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Initialize the service
        client = initialize_tts_client(fish_speech_url="http://localhost:8080/v1/tts")

        # Test synthesis
        result = client.synthesize_speech("Hello, this is a test!")

        # Verify result
        assert result == b"fake_wav_audio_data"

        # Verify API call was made
        mock_post.assert_called_once()

        # Verify health check works
        health = client.is_healthy()
        assert "primary" in health
