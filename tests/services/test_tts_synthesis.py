"""
Tests for TTS synthesis functionality.

Tests the TTS service integration with new factory pattern.
"""

from unittest.mock import Mock, patch

import pytest

from src.services.tts_service.fish_speech import FishSpeechTTS
from src.services.tts_service.service import TTSService
from src.services.tts_service.tts_factory import TTSFactory
from src.services.tts_service.vllm_omni import VLLMOmniTTSService


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
        assert tts_engine.base_url == "http://test.com/v1/tts"
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
        tts = FishSpeechTTS(base_url="http://localhost:8080/v1/tts")

        # Test synthesis
        result = tts.generate_speech("Hello world", output_format="bytes")
        assert result == b"fake_audio_data"

        # Verify the API was called
        assert mock_post.called

    def test_generate_speech_empty_text(self):
        """Test synthesis with empty text."""
        tts = FishSpeechTTS(base_url="http://localhost:8080/v1/tts")

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

        tts = FishSpeechTTS(base_url="http://localhost:8080/v1/tts")

        # Test synthesis with base64 format
        result = tts.generate_speech("Hello", output_format="base64")
        assert isinstance(result, str)
        assert result  # Should be a non-empty base64 string

    @patch("src.services.tts_service.fish_speech.requests.post")
    def test_generate_speech_api_failure(self, mock_post):
        """Test synthesis when API fails."""
        # Mock the HTTP response to raise an exception
        mock_post.side_effect = Exception("Connection error")

        tts = FishSpeechTTS(base_url="http://localhost:8080/v1/tts")

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

        tts = FishSpeechTTS(base_url="http://localhost:8080/v1/tts")

        # Test health check
        is_healthy, message = tts.is_healthy()
        assert is_healthy is True
        assert "healthy" in message.lower()

    @patch("src.services.tts_service.fish_speech.requests.post")
    def test_health_check_unhealthy(self, mock_post):
        """Test health check when TTS is unhealthy."""
        # Mock failed response
        mock_post.side_effect = Exception("Service unavailable")

        tts = FishSpeechTTS(base_url="http://localhost:8080/v1/tts")

        # Test health check
        is_healthy, message = tts.is_healthy()
        assert is_healthy is False
        assert "empty result" in message.lower() or "failed" in message.lower()


class TestTTSConfiguration:
    """Test TTS configuration integration."""

    def test_fish_speech_with_custom_params(self):
        """Test Fish Speech TTS with custom parameters."""
        tts = FishSpeechTTS(
            base_url="http://custom.com/tts",
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

        assert tts.base_url == "http://custom.com/tts"
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
        is_healthy, _message = tts_engine.is_healthy()
        assert is_healthy is True


class TestTTSFactoryVLLMOmni:
    """Test TTSFactory vllm_omni engine creation."""

    def test_get_vllm_omni_engine(self):
        """Test creating VLLMOmni TTS engine via factory."""
        tts_engine = TTSFactory.get_tts_engine(
            "vllm_omni",
            base_url="http://localhost:5517",
        )
        assert isinstance(tts_engine, VLLMOmniTTSService)
        assert isinstance(tts_engine, TTSService)

    def test_get_vllm_omni_engine_with_params(self):
        """Test creating VLLMOmni TTS engine with custom parameters."""
        tts_engine = TTSFactory.get_tts_engine(
            "vllm_omni",
            base_url="http://custom:5517",
            api_key="my-token",
            model="my_model",
        )
        assert isinstance(tts_engine, VLLMOmniTTSService)
        assert tts_engine.base_url == "http://custom:5517"
        assert tts_engine.api_key == "my-token"
        assert tts_engine.model == "my_model"


class TestVLLMOmniTTSService:
    """Test VLLMOmni TTS service functionality."""

    @patch("src.services.tts_service.vllm_omni.httpx.post")
    def test_generate_speech_bytes_success(self, mock_post):
        """Test successful speech synthesis returning bytes."""
        mock_response = Mock()
        mock_response.content = b"vllm_audio_bytes"
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        tts = VLLMOmniTTSService(base_url="http://localhost:5517")
        result = tts.generate_speech("Hello world", output_format="bytes")

        assert result == b"vllm_audio_bytes"
        assert mock_post.called

    def test_generate_speech_empty_text_returns_none(self):
        """Test that empty text returns None without calling API."""
        tts = VLLMOmniTTSService(base_url="http://localhost:5517")

        assert tts.generate_speech("") is None
        assert tts.generate_speech("   ") is None

    @patch("src.services.tts_service.vllm_omni.httpx.post")
    def test_generate_speech_base64_format(self, mock_post):
        """Test synthesis with base64 output format."""
        mock_response = Mock()
        mock_response.content = b"audio"
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        tts = VLLMOmniTTSService(base_url="http://localhost:5517")
        result = tts.generate_speech("Hello", output_format="base64")

        assert isinstance(result, str)
        assert len(result) > 0

    @patch("src.services.tts_service.vllm_omni.httpx.post")
    def test_generate_speech_api_failure_returns_none(self, mock_post):
        """Test that API failure returns None gracefully."""
        import httpx

        mock_post.side_effect = httpx.RequestError("Connection refused")

        tts = VLLMOmniTTSService(base_url="http://localhost:5517")
        result = tts.generate_speech("Hello world")

        assert result is None

    def test_generate_speech_missing_reference_returns_none(self, tmp_path):
        """Test that missing reference voice returns None."""
        tts = VLLMOmniTTSService(
            base_url="http://localhost:5517",
            ref_audio_dir=str(tmp_path),
        )
        result = tts.generate_speech("Hello", reference_id="nonexistent_voice")

        assert result is None

    def test_generate_speech_with_valid_reference(self, tmp_path):
        """Test synthesis with a valid reference voice directory."""
        # Create a fake reference voice directory
        ref_dir = tmp_path / "test_voice"
        ref_dir.mkdir()
        audio_file = ref_dir / "merged_audio.mp3"
        audio_file.write_bytes(b"fake_mp3_data")
        text_file = ref_dir / "combined.lab"
        text_file.write_text("reference transcript text", encoding="utf-8")

        with patch("src.services.tts_service.vllm_omni.httpx.post") as mock_post:
            mock_response = Mock()
            mock_response.content = b"synthesized_audio"
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            tts = VLLMOmniTTSService(
                base_url="http://localhost:5517",
                ref_audio_dir=str(tmp_path),
            )
            result = tts.generate_speech(
                "Test speech", reference_id="test_voice", output_format="bytes"
            )

        assert result == b"synthesized_audio"
        # Verify ref_audio and ref_text were passed in the request
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json", {})
        assert "ref_audio" in payload
        assert payload["ref_text"] == "reference transcript text"

    def test_reference_cache_avoids_repeated_io(self, tmp_path):
        """Test that loaded reference data is cached."""
        ref_dir = tmp_path / "cached_voice"
        ref_dir.mkdir()
        (ref_dir / "merged_audio.mp3").write_bytes(b"mp3")
        (ref_dir / "combined.lab").write_text("text", encoding="utf-8")

        tts = VLLMOmniTTSService(
            base_url="http://localhost:5517",
            ref_audio_dir=str(tmp_path),
        )

        ref1 = tts._load_reference("cached_voice")
        ref2 = tts._load_reference("cached_voice")

        assert ref1 is ref2  # Same object — cache hit

    @patch("src.services.tts_service.vllm_omni.httpx.get")
    def test_is_healthy_when_server_up(self, mock_get):
        """Test health check passes when server returns 200."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        tts = VLLMOmniTTSService(base_url="http://localhost:5517")
        is_healthy, message = tts.is_healthy()

        assert is_healthy is True
        assert "healthy" in message.lower()

    @patch("src.services.tts_service.vllm_omni.httpx.get")
    def test_is_healthy_when_server_down(self, mock_get):
        """Test health check fails when server is unreachable."""
        import httpx

        mock_get.side_effect = httpx.ConnectError("Connection refused")

        tts = VLLMOmniTTSService(base_url="http://localhost:5517")
        is_healthy, message = tts.is_healthy()

        assert is_healthy is False
        assert "failed" in message.lower()

    @patch("src.services.tts_service.vllm_omni.httpx.get")
    def test_is_healthy_non_200_response(self, mock_get):
        """Test health check fails when server returns non-200 status."""
        mock_response = Mock()
        mock_response.status_code = 503
        mock_get.return_value = mock_response

        tts = VLLMOmniTTSService(base_url="http://localhost:5517")
        is_healthy, message = tts.is_healthy()

        assert is_healthy is False
        assert "503" in message
