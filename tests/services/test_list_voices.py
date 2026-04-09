"""Unit tests for list_voices() on TTS service implementations."""

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


class TestIrodoriListVoices:
    def test_list_voices_no_reference(self):
        from src.services.tts_service.irodori_tts import IrodoriTTSService

        tts = IrodoriTTSService(base_url="http://localhost:8000")
        assert tts.list_voices() == []

    def test_list_voices_with_ref_audio_dir(self, tmp_path):
        from src.services.tts_service.irodori_tts import IrodoriTTSService

        voice_dir = tmp_path / "natsume"
        voice_dir.mkdir()
        (voice_dir / "merged_audio.mp3").write_bytes(b"RIFF")
        tts = IrodoriTTSService(
            base_url="http://localhost:8000", ref_audio_dir=str(tmp_path)
        )
        assert tts.list_voices() == ["natsume"]

    def test_list_voices_nonexistent_dir_returns_empty(self, tmp_path):
        from src.services.tts_service.irodori_tts import IrodoriTTSService

        tts = IrodoriTTSService(
            base_url="http://localhost:8000",
            ref_audio_dir=str(tmp_path / "does_not_exist"),
        )
        assert tts.list_voices() == []
