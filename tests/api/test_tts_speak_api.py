"""Tests for POST /v1/tts/speak endpoint."""

from unittest.mock import Mock, patch

from fastapi import status


class TestSpeakEndpoint:
    @patch("src.api.routes.tts.get_tts_service")
    def test_returns_200_with_audio_base64(self, mock_get_tts, client):
        mock_tts = Mock()
        mock_tts.generate_speech.return_value = "base64encodedaudio=="
        mock_get_tts.return_value = mock_tts

        response = client.post("/v1/tts/speak", json={"text": "hello world"})

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["audio_base64"] == "base64encodedaudio=="

    @patch("src.api.routes.tts.get_tts_service")
    def test_calls_generate_speech_with_base64_format(self, mock_get_tts, client):
        mock_tts = Mock()
        mock_tts.generate_speech.return_value = "audio=="
        mock_get_tts.return_value = mock_tts

        client.post("/v1/tts/speak", json={"text": "test text"})

        mock_tts.generate_speech.assert_called_once_with(
            "test text",
            None,
            "base64",
            audio_format="wav",
        )

    @patch("src.api.routes.tts.get_tts_service")
    def test_returns_503_when_service_none(self, mock_get_tts, client):
        mock_get_tts.return_value = None

        response = client.post("/v1/tts/speak", json={"text": "hello"})

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "TTS service not available" in response.json()["detail"]

    @patch("src.api.routes.tts.get_tts_service")
    def test_returns_503_when_generate_speech_returns_none(self, mock_get_tts, client):
        mock_tts = Mock()
        mock_tts.generate_speech.return_value = None
        mock_get_tts.return_value = mock_tts

        response = client.post("/v1/tts/speak", json={"text": "hello"})

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "TTS synthesis failed" in response.json()["detail"]

    @patch("src.api.routes.tts.get_tts_service")
    def test_returns_503_when_generate_speech_returns_false(self, mock_get_tts, client):
        mock_tts = Mock()
        mock_tts.generate_speech.return_value = False
        mock_get_tts.return_value = mock_tts

        response = client.post("/v1/tts/speak", json={"text": "hello"})

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "TTS synthesis failed" in response.json()["detail"]

    def test_returns_422_when_text_missing(self, client):
        response = client.post("/v1/tts/speak", json={})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_returns_422_when_body_missing(self, client):
        response = client.post("/v1/tts/speak")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
