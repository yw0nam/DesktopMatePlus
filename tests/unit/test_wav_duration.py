"""Tests for WAV duration calculation utility."""

import struct

import pytest

from src.services.tts_service.tts_pipeline import wav_duration


def _make_wav(sample_rate: int, channels: int, bits: int, num_samples: int) -> bytes:
    """Create a minimal WAV file in memory."""
    bytes_per_sample = bits // 8
    data_size = num_samples * channels * bytes_per_sample
    # RIFF header
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,  # file size - 8
        b"WAVE",
        b"fmt ",
        16,  # fmt chunk size
        1,  # PCM format
        channels,
        sample_rate,
        sample_rate * channels * bytes_per_sample,  # byte rate
        channels * bytes_per_sample,  # block align
        bits,  # bits per sample
        b"data",
        data_size,
    )
    return header + b"\x00" * data_size


class TestWavDuration:
    def test_one_second_mono_16bit(self):
        wav = _make_wav(sample_rate=22050, channels=1, bits=16, num_samples=22050)
        assert wav_duration(wav) == pytest.approx(1.0, abs=0.01)

    def test_half_second_stereo_16bit(self):
        wav = _make_wav(sample_rate=44100, channels=2, bits=16, num_samples=22050)
        assert wav_duration(wav) == pytest.approx(0.5, abs=0.01)

    def test_empty_data(self):
        wav = _make_wav(sample_rate=22050, channels=1, bits=16, num_samples=0)
        assert wav_duration(wav) == 0.0

    def test_invalid_bytes(self):
        assert wav_duration(b"not a wav") == 0.0

    def test_none_input(self):
        assert wav_duration(None) == 0.0
