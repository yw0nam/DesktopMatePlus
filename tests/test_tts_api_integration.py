"""Tests for TTS API integration."""

from unittest.mock import Mock, patch

import pytest
from fastapi import status


@pytest.fixture
def mock_tts_engine():
    """Create a mock TTS engine."""
    return Mock()


class TestTTSAPIIntegration:
    """Test TTS API endpoint integration."""

    @patch("src.api.routes.tts.get_tts_service")
    def test_synthesize_speech_success(self, mock_get_tts, client):
        """Test successful speech synthesis."""
        # Setup mock
        mock_engine = Mock()
        mock_engine.generate_speech.return_value = "base64encodedaudiodata=="
        mock_get_tts.return_value = mock_engine

        # Make request
        response = client.post(
            "/v1/tts/synthesize",
            json={
                "text": "Hello, world!",
                "output_format": "base64",
            },
        )

        # Assert response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "audio_data" in data
        assert data["audio_data"] == "base64encodedaudiodata=="
        assert data["format"] == "base64"

        # Verify mock was called correctly
        mock_engine.generate_speech.assert_called_once_with(
            text="Hello, world!",
            reference_id=None,
            output_format="base64",
        )

    @patch("src.api.routes.tts.get_tts_service")
    def test_synthesize_speech_with_reference(self, mock_get_tts, client):
        """Test speech synthesis with voice reference."""
        # Setup mock
        mock_engine = Mock()
        mock_engine.generate_speech.return_value = "base64audiowithreferenceVoice=="
        mock_get_tts.return_value = mock_engine

        # Make request
        response = client.post(
            "/v1/tts/synthesize",
            json={
                "text": "This is a test with voice cloning",
                "reference_id": "ナツメ",
                "output_format": "base64",
            },
        )

        # Assert response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["audio_data"] == "base64audiowithreferenceVoice=="

        # Verify mock was called correctly
        mock_engine.generate_speech.assert_called_once_with(
            text="This is a test with voice cloning",
            reference_id="ナツメ",
            output_format="base64",
        )

    @patch("src.api.routes.tts.get_tts_service")
    def test_synthesize_speech_bytes_format(self, mock_get_tts, client):
        """Test speech synthesis with bytes output format."""
        # Setup mock
        mock_engine = Mock()
        mock_engine.generate_speech.return_value = b"raw audio bytes data"
        mock_get_tts.return_value = mock_engine

        # Make request
        response = client.post(
            "/v1/tts/synthesize",
            json={
                "text": "Test with bytes format",
                "output_format": "bytes",
            },
        )

        # Assert response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "audio_data" in data
        assert data["format"] == "bytes"

        # Verify bytes were base64 encoded for JSON transport
        import base64

        expected = base64.b64encode(b"raw audio bytes data").decode("utf-8")
        assert data["audio_data"] == expected

    @patch("src.api.routes.tts.get_tts_service")
    def test_synthesize_speech_service_not_initialized(self, mock_get_tts, client):
        """Test error when TTS service is not initialized."""
        # Setup mock with no engine
        mock_get_tts.return_value = None

        # Make request
        response = client.post(
            "/v1/tts/synthesize",
            json={
                "text": "Test text",
                "output_format": "base64",
            },
        )

        # Assert error response
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert "detail" in data
        assert "TTS service not initialized" in data["detail"]

    @patch("src.api.routes.tts.get_tts_service")
    def test_synthesize_speech_empty_text(self, mock_get_tts, client):
        """Test error when text is empty."""
        # Setup mock
        mock_engine = Mock()
        mock_get_tts.return_value = mock_engine

        # Make request with empty text
        response = client.post(
            "/v1/tts/synthesize",
            json={
                "text": "   ",  # Only whitespace
                "output_format": "base64",
            },
        )

        # Assert error response
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "detail" in data
        assert "Text cannot be empty" in data["detail"]

        # Verify mock was NOT called
        mock_engine.generate_speech.assert_not_called()

    @patch("src.api.routes.tts.get_tts_service")
    def test_synthesize_speech_processing_error(self, mock_get_tts, client):
        """Test error handling when TTS processing fails."""
        # Setup mock to raise exception
        mock_engine = Mock()
        mock_engine.generate_speech.side_effect = Exception("TTS engine error")
        mock_get_tts.return_value = mock_engine

        # Make request
        response = client.post(
            "/v1/tts/synthesize",
            json={
                "text": "Test text",
                "output_format": "base64",
            },
        )

        # Assert error response
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data
        assert "Error processing TTS request" in data["detail"]
        assert "TTS engine error" in data["detail"]

    @patch("src.api.routes.tts.get_tts_service")
    def test_synthesize_speech_returns_none(self, mock_get_tts, client):
        """Test error handling when TTS service returns None."""
        # Setup mock to return None
        mock_engine = Mock()
        mock_engine.generate_speech.return_value = None
        mock_get_tts.return_value = mock_engine

        # Make request
        response = client.post(
            "/v1/tts/synthesize",
            json={
                "text": "Test text",
                "output_format": "base64",
            },
        )

        # Assert error response
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data
        assert "TTS service returned no audio data" in data["detail"]

    def test_synthesize_speech_missing_text(self, client):
        """Test validation error when text is missing."""
        # Make request without text
        response = client.post(
            "/v1/tts/synthesize",
            json={
                "output_format": "base64",
            },
        )

        # Assert validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch("src.api.routes.tts.get_tts_service")
    def test_synthesize_speech_default_format(self, mock_get_tts, client):
        """Test that default output format is base64."""
        # Setup mock
        mock_engine = Mock()
        mock_engine.generate_speech.return_value = "defaultbase64=="
        mock_get_tts.return_value = mock_engine

        # Make request without specifying output_format
        response = client.post(
            "/v1/tts/synthesize",
            json={
                "text": "Test with default format",
            },
        )

        # Assert response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["format"] == "base64"

        # Verify default format was used
        mock_engine.generate_speech.assert_called_once_with(
            text="Test with default format",
            reference_id=None,
            output_format="base64",
        )

    @patch("src.api.routes.tts.get_tts_service")
    def test_synthesize_speech_long_text(self, mock_get_tts, client):
        """Test speech synthesis with a long text."""
        # Setup mock
        mock_engine = Mock()
        mock_engine.generate_speech.return_value = "longaudiobase64=="
        mock_get_tts.return_value = mock_engine

        long_text = "This is a very long text. " * 100

        # Make request
        response = client.post(
            "/v1/tts/synthesize",
            json={
                "text": long_text,
                "output_format": "base64",
            },
        )

        # Assert response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["audio_data"] == "longaudiobase64=="

        # Verify long text was passed correctly
        mock_engine.generate_speech.assert_called_once_with(
            text=long_text,
            reference_id=None,
            output_format="base64",
        )
