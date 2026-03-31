"""Integration tests for GET /v1/tts/voices endpoint."""

from unittest.mock import Mock, patch

from fastapi import status


class TestListVoicesEndpoint:
    @patch("src.api.routes.tts.get_tts_service")
    def test_returns_200_with_voice_list(self, mock_get_tts, client):
        mock_tts = Mock()
        mock_tts.list_voices.return_value = ["aria", "natsume", "voice_b"]
        mock_get_tts.return_value = mock_tts
        response = client.get("/v1/tts/voices")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["voices"] == ["aria", "natsume", "voice_b"]

    @patch("src.api.routes.tts.get_tts_service")
    def test_returns_200_with_empty_list(self, mock_get_tts, client):
        mock_tts = Mock()
        mock_tts.list_voices.return_value = []
        mock_get_tts.return_value = mock_tts
        response = client.get("/v1/tts/voices")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["voices"] == []

    @patch("src.api.routes.tts.get_tts_service")
    def test_returns_503_when_service_none(self, mock_get_tts, client):
        mock_get_tts.return_value = None
        response = client.get("/v1/tts/voices")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "TTS service not available" in response.json()["detail"]

    def test_synthesize_endpoint_gone(self, client):
        response = client.post("/v1/tts/synthesize", json={"text": "hello"})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("src.api.routes.tts.get_tts_service")
    def test_calls_service_list_voices(self, mock_get_tts, client):
        mock_tts = Mock()
        mock_tts.list_voices.return_value = ["voice_x"]
        mock_get_tts.return_value = mock_tts
        client.get("/v1/tts/voices")
        mock_tts.list_voices.assert_called_once_with()
        mock_tts.generate_speech.assert_not_called()
