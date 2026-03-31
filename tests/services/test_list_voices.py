"""Unit tests for list_voices() on TTS service implementations."""

from src.services.tts_service.fish_speech import FishSpeechTTS
from src.services.tts_service.vllm_omni import VLLMOmniTTSService


class TestVLLMOmniListVoices:
    def test_missing_ref_audio_dir_returns_empty(self, tmp_path):
        nonexistent = tmp_path / "does_not_exist"
        tts = VLLMOmniTTSService(
            base_url="http://localhost:5517", ref_audio_dir=str(nonexistent)
        )
        assert tts.list_voices() == []

    def test_empty_ref_audio_dir_returns_empty(self, tmp_path):
        tts = VLLMOmniTTSService(
            base_url="http://localhost:5517", ref_audio_dir=str(tmp_path)
        )
        assert tts.list_voices() == []

    def test_valid_voice_dir_is_included(self, tmp_path):
        d = tmp_path / "aria"
        d.mkdir()
        (d / "merged_audio.mp3").write_bytes(b"mp3data")
        (d / "combined.lab").write_text("reference text", encoding="utf-8")
        tts = VLLMOmniTTSService(
            base_url="http://localhost:5517", ref_audio_dir=str(tmp_path)
        )
        assert "aria" in tts.list_voices()

    def test_incomplete_dir_mp3_only_is_excluded(self, tmp_path):
        d = tmp_path / "incomplete"
        d.mkdir()
        (d / "merged_audio.mp3").write_bytes(b"mp3data")
        tts = VLLMOmniTTSService(
            base_url="http://localhost:5517", ref_audio_dir=str(tmp_path)
        )
        assert "incomplete" not in tts.list_voices()

    def test_incomplete_dir_lab_only_is_excluded(self, tmp_path):
        d = tmp_path / "labonly"
        d.mkdir()
        (d / "combined.lab").write_text("text", encoding="utf-8")
        tts = VLLMOmniTTSService(
            base_url="http://localhost:5517", ref_audio_dir=str(tmp_path)
        )
        assert "labonly" not in tts.list_voices()

    def test_multiple_voices_returned_sorted(self, tmp_path):
        for name in ("zebra", "alpha", "bravo"):
            d = tmp_path / name
            d.mkdir()
            (d / "merged_audio.mp3").write_bytes(b"mp3")
            (d / "combined.lab").write_text("t", encoding="utf-8")
        tts = VLLMOmniTTSService(
            base_url="http://localhost:5517", ref_audio_dir=str(tmp_path)
        )
        voices = tts.list_voices()
        assert voices == sorted(voices)
        assert set(voices) == {"zebra", "alpha", "bravo"}

    def test_list_voices_returns_cached_value(self, tmp_path):
        d = tmp_path / "voice1"
        d.mkdir()
        (d / "merged_audio.mp3").write_bytes(b"mp3")
        (d / "combined.lab").write_text("t", encoding="utf-8")
        tts = VLLMOmniTTSService(
            base_url="http://localhost:5517", ref_audio_dir=str(tmp_path)
        )
        assert tts.list_voices() is tts.list_voices()

    def test_file_at_root_level_is_ignored(self, tmp_path):
        (tmp_path / "README.txt").write_text("not a voice")
        tts = VLLMOmniTTSService(
            base_url="http://localhost:5517", ref_audio_dir=str(tmp_path)
        )
        assert tts.list_voices() == []


class TestFishSpeechListVoices:
    def test_list_voices_returns_empty_list(self):
        tts = FishSpeechTTS(base_url="http://localhost:8080/v1/tts")
        assert tts.list_voices() == []

    def test_list_voices_return_type_is_list(self):
        tts = FishSpeechTTS(base_url="http://localhost:8080/v1/tts")
        assert isinstance(tts.list_voices(), list)
