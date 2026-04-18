"""Tests for viseme integration in tts_pipeline.synthesize_chunk."""

import base64
import struct
from unittest.mock import MagicMock

import pytest

from src.services.tts_service.emotion_motion_mapper import EmotionMotionMapper
from src.services.tts_service.tts_pipeline import synthesize_chunk
from src.services.tts_service.viseme_mapper import VisemeMapper


def _make_wav_bytes(duration_seconds: float = 1.0) -> bytes:
    """Create WAV bytes with specified duration."""
    sample_rate = 22050
    channels = 1
    bits = 16
    num_samples = int(sample_rate * duration_seconds)
    bytes_per_sample = bits // 8
    data_size = num_samples * channels * bytes_per_sample
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size, b"WAVE",
        b"fmt ", 16, 1, channels, sample_rate,
        sample_rate * channels * bytes_per_sample,
        channels * bytes_per_sample, bits,
        b"data", data_size,
    )
    return header + b"\x00" * data_size


@pytest.fixture
def tts_service():
    svc = MagicMock()
    svc.generate_speech.return_value = _make_wav_bytes(1.0)
    return svc


@pytest.fixture
def emotion_mapper():
    return EmotionMotionMapper(
        {"😊": {"keyframes": [{"duration": 0.3, "targets": {"happy": 1.0}}]}}
    )


@pytest.fixture
def viseme_mapper():
    return VisemeMapper()


async def test_viseme_keyframes_in_output(tts_service, emotion_mapper, viseme_mapper):
    """synthesize_chunk should produce keyframes with A/I/U/E/O visemes."""
    msg = await synthesize_chunk(
        tts_service=tts_service,
        mapper=emotion_mapper,
        viseme_mapper=viseme_mapper,
        text="こんにちは",
        emotion="😊",
        sequence=0,
        tts_enabled=True,
    )
    assert msg.audio_base64 is not None
    assert len(msg.keyframes) > 0
    # Viseme keyframes should have A/I/U/E/O keys
    has_viseme = any("A" in kf["targets"] for kf in msg.keyframes)
    assert has_viseme, "Keyframes should contain viseme targets"


async def test_emotion_merged_in_viseme_keyframes(tts_service, emotion_mapper, viseme_mapper):
    """Emotion targets should be present in viseme keyframes."""
    msg = await synthesize_chunk(
        tts_service=tts_service,
        mapper=emotion_mapper,
        viseme_mapper=viseme_mapper,
        text="こんにちは",
        emotion="😊",
        sequence=0,
    )
    # Every keyframe should have happy emotion merged
    for kf in msg.keyframes:
        assert kf["targets"].get("happy") == 1.0, f"Missing happy in {kf}"


async def test_tts_disabled_still_has_emotion_keyframes(tts_service, emotion_mapper, viseme_mapper):
    """When TTS disabled, should fall back to emotion-only keyframes."""
    msg = await synthesize_chunk(
        tts_service=tts_service,
        mapper=emotion_mapper,
        viseme_mapper=viseme_mapper,
        text="こんにちは",
        emotion="😊",
        sequence=0,
        tts_enabled=False,
    )
    assert msg.audio_base64 is None
    assert len(msg.keyframes) > 0  # emotion keyframes still present


async def test_tts_failure_falls_back(tts_service, emotion_mapper, viseme_mapper):
    """When TTS fails, should fall back to emotion-only keyframes."""
    tts_service.generate_speech.return_value = None
    msg = await synthesize_chunk(
        tts_service=tts_service,
        mapper=emotion_mapper,
        viseme_mapper=viseme_mapper,
        text="こんにちは",
        emotion="😊",
        sequence=0,
    )
    assert msg.audio_base64 is None
    # Should still have emotion keyframes
    assert len(msg.keyframes) > 0
