"""Tests for IrodoriTTSService client."""

import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from src.configs.tts.irodori import IrodoriTTSConfig
from src.services.tts_service.irodori_tts import IrodoriTTSService
from src.services.tts_service.service import TTSService
from src.services.tts_service.tts_factory import TTSFactory


class TestIrodoriTTSConfig:
    """Test IrodoriTTSConfig Pydantic model."""

    def test_defaults(self):
        config = IrodoriTTSConfig(base_url="http://localhost:8000")
        assert config.base_url == "http://localhost:8000"
        assert config.reference_audio_path is None
        assert config.seconds == 30.0
        assert config.num_steps == 40
        assert config.cfg_scale_text == 3.0
        assert config.cfg_scale_speaker == 5.0
        assert config.seed is None
        assert config.timeout == 60.0

    def test_custom_values(self):
        config = IrodoriTTSConfig(
            base_url="http://myserver:9000",
            reference_audio_path="/tmp/ref.wav",
            seconds=15.0,
            num_steps=20,
            cfg_scale_text=2.5,
            cfg_scale_speaker=4.0,
            seed=42,
            timeout=30.0,
        )
        assert config.reference_audio_path == "/tmp/ref.wav"
        assert config.seconds == 15.0
        assert config.seed == 42


class TestIrodoriTTSServiceInit:
    """Test IrodoriTTSService initialization."""

    def test_is_tts_service(self):
        svc = IrodoriTTSService(base_url="http://localhost:8000")
        assert isinstance(svc, TTSService)

    def test_default_params(self):
        svc = IrodoriTTSService(base_url="http://localhost:8000")
        assert svc.base_url == "http://localhost:8000"
        assert svc.reference_audio_path is None

    def test_with_reference_audio(self, tmp_path):
        ref = tmp_path / "ref.wav"
        ref.write_bytes(b"RIFF")
        svc = IrodoriTTSService(
            base_url="http://localhost:8000",
            reference_audio_path=str(ref),
        )
        assert svc.reference_audio_path == str(ref)


class TestIrodoriTTSServiceGenerateSpeech:
    """Test generate_speech method."""

    def _make_service(self, **kwargs) -> IrodoriTTSService:
        return IrodoriTTSService(base_url="http://localhost:8000", **kwargs)

    def test_empty_text_returns_none(self):
        svc = self._make_service()
        assert svc.generate_speech("") is None
        assert svc.generate_speech("   ") is None

    @patch("src.services.tts_service.irodori_tts.httpx.Client")
    def test_generate_speech_bytes_success(self, mock_client_cls):
        wav_bytes = b"RIFF\x00\x00\x00\x00WAVE"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = wav_bytes
        mock_resp.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        svc = self._make_service()
        result = svc.generate_speech("Hello world", output_format="bytes")

        assert result == wav_bytes
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert "/synthesize" in call_kwargs[0][0]

    @patch("src.services.tts_service.irodori_tts.httpx.Client")
    def test_generate_speech_base64_format(self, mock_client_cls):
        wav_bytes = b"RIFF\x00\x00\x00\x00WAVE"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = wav_bytes
        mock_resp.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        svc = self._make_service()
        result = svc.generate_speech("Hello", output_format="base64")

        assert isinstance(result, str)
        assert base64.b64decode(result) == wav_bytes

    @patch("src.services.tts_service.irodori_tts.httpx.Client")
    def test_generate_speech_file_format(self, mock_client_cls, tmp_path):
        wav_bytes = b"RIFF\x00\x00\x00\x00WAVE"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = wav_bytes
        mock_resp.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        out_path = str(tmp_path / "output.wav")
        svc = self._make_service()
        result = svc.generate_speech(
            "Hello", output_format="file", output_filename=out_path
        )

        assert result is True
        assert Path(out_path).read_bytes() == wav_bytes

    @patch("src.services.tts_service.irodori_tts.httpx.Client")
    def test_server_down_returns_none(self, mock_client_cls):
        """Graceful degradation: server unreachable → None."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")
        mock_client_cls.return_value = mock_client

        svc = self._make_service()
        result = svc.generate_speech("Hello world")
        assert result is None

    @patch("src.services.tts_service.irodori_tts.httpx.Client")
    def test_http_error_returns_none(self, mock_client_cls):
        """Graceful degradation: HTTP 5xx → None."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock()
        )

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        svc = self._make_service()
        result = svc.generate_speech("Hello world")
        assert result is None

    @patch("src.services.tts_service.irodori_tts.httpx.Client")
    def test_multipart_form_fields(self, mock_client_cls):
        """Verify POST /synthesize is called with correct multipart form fields."""
        wav_bytes = b"RIFF\x00\x00\x00\x00WAVE"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = wav_bytes
        mock_resp.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        svc = IrodoriTTSService(
            base_url="http://localhost:8000",
            seconds=15.0,
            num_steps=20,
            cfg_scale_text=2.0,
            cfg_scale_speaker=4.0,
            seed=99,
        )
        svc.generate_speech("Hello 😊 world", output_format="bytes")

        call_kwargs = mock_client.post.call_args
        data = call_kwargs[1].get("data", {}) or call_kwargs.kwargs.get("data", {})
        assert data["text"] == "Hello 😊 world"
        assert float(data["seconds"]) == 15.0
        assert int(data["num_steps"]) == 20
        assert float(data["cfg_scale_text"]) == 2.0
        assert float(data["cfg_scale_speaker"]) == 4.0
        assert int(data["seed"]) == 99

    @patch("src.services.tts_service.irodori_tts.httpx.Client")
    def test_reference_audio_sent_in_multipart(self, mock_client_cls, tmp_path):
        """When reference_audio_path is set, file is sent in multipart files."""
        ref_audio = tmp_path / "ref.wav"
        ref_audio.write_bytes(b"RIFF")

        wav_bytes = b"RIFF\x00\x00\x00\x00WAVE"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = wav_bytes
        mock_resp.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        svc = IrodoriTTSService(
            base_url="http://localhost:8000",
            reference_audio_path=str(ref_audio),
        )
        svc.generate_speech("Hello", output_format="bytes")

        call_kwargs = mock_client.post.call_args
        files = call_kwargs[1].get("files", {}) or call_kwargs.kwargs.get("files", {})
        assert "reference_audio" in files

    @patch("src.services.tts_service.irodori_tts.httpx.Client")
    def test_no_reference_audio_omits_field(self, mock_client_cls):
        """When reference_audio_path is None, reference_audio field omitted."""
        wav_bytes = b"RIFF\x00\x00\x00\x00WAVE"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = wav_bytes
        mock_resp.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        svc = IrodoriTTSService(base_url="http://localhost:8000")
        svc.generate_speech("Hello", output_format="bytes")

        call_kwargs = mock_client.post.call_args
        files = call_kwargs[1].get("files") or call_kwargs.kwargs.get("files")
        assert not files or "reference_audio" not in files

    @patch("src.services.tts_service.irodori_tts.httpx.Client")
    def test_empty_200_response_returns_none(self, mock_client_cls):
        """Server returns HTTP 200 with empty body → None (not empty bytes)."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b""
        mock_resp.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        svc = self._make_service()
        result = svc.generate_speech("Hello", output_format="bytes")
        # Empty bytes are falsy but we should return None, not b""
        assert result is None

    @patch("src.services.tts_service.irodori_tts.httpx.Client")
    def test_file_format_with_none_filename_returns_false(self, mock_client_cls):
        """output_format='file' with output_filename=None → False (not TypeError)."""
        wav_bytes = b"RIFF\x00\x00\x00\x00WAVE"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = wav_bytes
        mock_resp.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        svc = self._make_service()
        result = svc.generate_speech(
            "Hello", output_format="file", output_filename=None
        )
        assert result is False

    def test_missing_reference_audio_file_returns_none(self):
        """reference_audio_path set to non-existent file → None (graceful)."""
        svc = IrodoriTTSService(
            base_url="http://localhost:8000",
            reference_audio_path="/tmp/nonexistent_ref_abc123.wav",
        )
        result = svc.generate_speech("Hello", output_format="bytes")
        assert result is None


class TestIrodoriTTSServiceListVoices:
    """Test list_voices method."""

    def test_list_voices_with_reference(self, tmp_path):
        ref = tmp_path / "narrator.wav"
        ref.write_bytes(b"RIFF")
        svc = IrodoriTTSService(
            base_url="http://localhost:8000",
            reference_audio_path=str(ref),
        )
        voices = svc.list_voices()
        assert voices == ["narrator"]

    def test_list_voices_no_reference(self):
        svc = IrodoriTTSService(base_url="http://localhost:8000")
        voices = svc.list_voices()
        assert voices == ["no-reference"]


class TestIrodoriTTSServiceIsHealthy:
    """Test is_healthy method."""

    @patch("src.services.tts_service.irodori_tts.httpx.get")
    def test_healthy_when_server_ok(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok", "pool_size": 4, "available": 3}
        mock_get.return_value = mock_resp

        svc = IrodoriTTSService(base_url="http://localhost:8000")
        ok, msg = svc.is_healthy()

        assert ok is True
        assert "ok" in msg.lower()

    @patch("src.services.tts_service.irodori_tts.httpx.get")
    def test_unhealthy_when_server_down(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("refused")

        svc = IrodoriTTSService(base_url="http://localhost:8000")
        ok, msg = svc.is_healthy()

        assert ok is False
        assert len(msg) > 0

    @patch("src.services.tts_service.irodori_tts.httpx.get")
    def test_unhealthy_when_non_ok_status(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "initializing"}
        mock_get.return_value = mock_resp

        svc = IrodoriTTSService(base_url="http://localhost:8000")
        ok, _msg = svc.is_healthy()

        assert ok is False


class TestTTSFactoryIrodori:
    """Test TTSFactory irodori type."""

    def test_factory_creates_irodori_service(self):
        svc = TTSFactory.get_tts_engine("irodori", base_url="http://localhost:8000")
        assert isinstance(svc, IrodoriTTSService)
        assert isinstance(svc, TTSService)

    def test_factory_passes_config_params(self):
        svc = TTSFactory.get_tts_engine(
            "irodori",
            base_url="http://myserver:9000",
            num_steps=20,
            seed=7,
        )
        assert svc.base_url == "http://myserver:9000"
        assert svc.num_steps == 20
        assert svc.seed == 7
