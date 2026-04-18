"""Tests for synthesize_chunk() TTS pipeline.

Note: asyncio_mode=auto (pyproject.toml) — @pytest.mark.asyncio decorator is NOT needed.
generate_speech() MUST be mocked in all tests — no real TTS engine in CI.
"""

import base64 as _b64
from unittest.mock import MagicMock, patch

from src.services.tts_service.tts_pipeline import synthesize_chunk


async def test_synthesize_chunk_success():
    """TTS success: audio_base64 non-null, keyframes populated from mapper.

    viseme_mapper is None here — exercises the backwards-compatible branch
    where the pipeline just base64-encodes raw bytes from generate_speech.
    """
    raw_audio = b"\x00\x01\x02\x03"
    tts_service = MagicMock()
    tts_service.generate_speech.return_value = raw_audio
    mapper = MagicMock()
    mapper.map.return_value = [{"duration": 0.3, "targets": {"happy": 1.0}}]

    chunk = await synthesize_chunk(
        tts_service=tts_service,
        mapper=mapper,
        text="안녕",
        emotion="joyful",
        sequence=0,
        tts_enabled=True,
    )

    assert chunk.audio_base64 == _b64.b64encode(raw_audio).decode("ascii")
    assert chunk.keyframes == [{"duration": 0.3, "targets": {"happy": 1.0}}]
    assert chunk.sequence == 0
    assert chunk.text == "안녕"
    assert chunk.emotion == "joyful"
    tts_service.generate_speech.assert_called_once()


async def test_synthesize_chunk_uses_wav_format():
    """generate_speech must be called with 'wav' audio format."""
    tts_service = MagicMock()
    tts_service.generate_speech.return_value = b"\x00\x01\x02\x03"
    mapper = MagicMock()
    mapper.map.return_value = [{"duration": 0.3, "targets": {"neutral": 1.0}}]

    await synthesize_chunk(
        tts_service=tts_service,
        mapper=mapper,
        text="hello",
        emotion=None,
        sequence=0,
        tts_enabled=True,
    )

    # Fourth positional arg to generate_speech is the audio format
    args = tts_service.generate_speech.call_args
    positional = args[0] if args[0] else []
    keyword = args[1] if args[1] else {}
    audio_format = positional[3] if len(positional) > 3 else keyword.get("audio_format")
    assert audio_format == "wav", f"Expected 'wav', got {audio_format!r}"


async def test_synthesize_chunk_generate_speech_returns_none():
    """generate_speech returns None → audio=None, keyframes still populated."""
    tts_service = MagicMock()
    tts_service.generate_speech.return_value = None
    mapper = MagicMock()
    mapper.map.return_value = [{"duration": 0.3, "targets": {"neutral": 1.0}}]

    chunk = await synthesize_chunk(
        tts_service=tts_service,
        mapper=mapper,
        text="텍스트",
        emotion=None,
        sequence=1,
        tts_enabled=True,
    )

    assert chunk.audio_base64 is None
    assert chunk.sequence == 1
    assert chunk.keyframes == [{"duration": 0.3, "targets": {"neutral": 1.0}}]


async def test_synthesize_chunk_exception():
    """generate_speech raises exception → audio=None, logger.warning called once."""
    tts_service = MagicMock()
    tts_service.generate_speech.side_effect = ConnectionError("TTS server down")
    mapper = MagicMock()
    mapper.map.return_value = [{"duration": 0.3, "targets": {"neutral": 1.0}}]

    with patch("src.services.tts_service.tts_pipeline.logger") as mock_logger:
        chunk = await synthesize_chunk(
            tts_service=tts_service,
            mapper=mapper,
            text="텍스트",
            emotion=None,
            sequence=2,
            tts_enabled=True,
        )

    assert chunk.audio_base64 is None
    assert chunk.sequence == 2
    # Pipeline now logs exceptions via logger.opt(exception=True).warning(...)
    mock_logger.opt.return_value.warning.assert_called_once()


async def test_synthesize_chunk_tts_disabled():
    """tts_enabled=False → audio=None, generate_speech NOT called, keyframes still set."""
    tts_service = MagicMock()
    mapper = MagicMock()
    mapper.map.return_value = [{"duration": 0.4, "targets": {"sad": 0.8}}]

    chunk = await synthesize_chunk(
        tts_service=tts_service,
        mapper=mapper,
        text="텍스트",
        emotion="sad",
        sequence=3,
        tts_enabled=False,
    )

    assert chunk.audio_base64 is None
    assert chunk.keyframes == [{"duration": 0.4, "targets": {"sad": 0.8}}]
    assert chunk.sequence == 3
    tts_service.generate_speech.assert_not_called()
