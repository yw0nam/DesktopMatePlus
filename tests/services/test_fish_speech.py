"""Tests for FishSpeechTTS — BE-BUG-2 (logger restore) and BE-BUG-3 (serial queue)."""

import threading
from asyncio import to_thread
from unittest.mock import patch

import requests
from src.services.tts_service.fish_speech import FishSpeechTTS, ServeTTSRequest


class TestFishSpeechLoggerRestore:
    """BE-BUG-2: logger.error must be called on exceptions in _request_tts_stream."""

    def _make_tts(self) -> FishSpeechTTS:
        return FishSpeechTTS(base_url="http://localhost:8080")

    def test_request_exception_logs_error(self) -> None:
        """RequestException in _request_tts_stream → logger.error called."""
        tts = self._make_tts()
        with patch("src.services.tts_service.fish_speech.requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.RequestException(
                "connection refused"
            )
            with patch("src.services.tts_service.fish_speech.logger") as mock_logger:
                result = tts._request_tts_stream(ServeTTSRequest(text="hello"))

        assert result is None
        mock_logger.error.assert_called_once()
        assert "TTS API 요청 실패" in mock_logger.error.call_args[0][0]

    def test_generic_exception_logs_error(self) -> None:
        """Unexpected Exception in _request_tts_stream → logger.error called."""
        tts = self._make_tts()
        with patch("src.services.tts_service.fish_speech.requests.post") as mock_post:
            mock_post.side_effect = RuntimeError("unexpected")
            with patch("src.services.tts_service.fish_speech.logger") as mock_logger:
                result = tts._request_tts_stream(ServeTTSRequest(text="hello"))

        assert result is None
        mock_logger.error.assert_called_once()
        assert "예상치 못한 오류" in mock_logger.error.call_args[0][0]


class TestFishSpeechSerialQueue:
    """BE-BUG-3: Queue worker serializes concurrent TTS requests."""

    async def test_start_worker_creates_running_task(self) -> None:
        """start_worker() creates an active asyncio.Task."""
        tts = FishSpeechTTS(base_url="http://localhost:8080")
        await tts.start_worker()
        assert tts._worker_task is not None
        assert not tts._worker_task.done()
        await tts.stop_worker()

    async def test_generate_speech_via_queue_returns_bytes(self) -> None:
        """generate_speech() returns bytes via queue worker."""
        tts = FishSpeechTTS(base_url="http://localhost:8080")
        fake_audio = b"fake_audio_data"

        with patch.object(tts, "_request_tts_stream", return_value=fake_audio):
            await tts.start_worker()
            result = await to_thread(tts.generate_speech, "hello", None, "bytes")
            await tts.stop_worker()

        assert result == fake_audio

    async def test_concurrent_requests_are_serialized(self) -> None:
        """Two concurrent generate_speech() calls must NOT overlap in _request_tts_stream."""
        tts = FishSpeechTTS(base_url="http://localhost:8080")

        overlap_detected = threading.Event()
        in_progress = threading.Event()
        call_lock = threading.Lock()

        def controlled_http(payload: ServeTTSRequest) -> bytes:
            with call_lock:
                if in_progress.is_set():
                    overlap_detected.set()
                in_progress.set()
            import time

            time.sleep(0.05)  # simulate HTTP latency
            with call_lock:
                in_progress.clear()
            return b"audio"

        with patch.object(tts, "_request_tts_stream", side_effect=controlled_http):
            await tts.start_worker()
            await __import__("asyncio").gather(
                to_thread(tts.generate_speech, "first"),
                to_thread(tts.generate_speech, "second"),
            )
            await tts.stop_worker()

        assert (
            not overlap_detected.is_set()
        ), "Concurrent HTTP calls detected — not serialized!"

    def test_timeout_is_120s(self) -> None:
        """_request_tts_stream uses timeout=120."""
        tts = FishSpeechTTS(base_url="http://localhost:8080")
        captured: dict = {}

        def mock_post(*args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")
            raise requests.exceptions.RequestException("mock")

        with patch(
            "src.services.tts_service.fish_speech.requests.post", side_effect=mock_post
        ):
            tts._request_tts_stream(ServeTTSRequest(text="test"))

        assert captured.get("timeout") == 120
