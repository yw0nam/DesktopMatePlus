"""Tests for VisemeMapper — text to viseme keyframe generation."""

import pytest

from src.services.tts_service.viseme_mapper import VisemeMapper


class TestPhonemeToViseme:
    """Test Japanese phoneme → VRM viseme mapping."""

    def setup_method(self):
        self.mapper = VisemeMapper()

    def test_simple_vowel_a(self):
        """Single vowel 'あ' → one A keyframe + closing keyframe."""
        result = self.mapper.generate("あ", audio_duration=0.5)
        # Should have at least 2 keyframes (phoneme + closing)
        assert len(result) >= 2
        # First keyframe should have A viseme active
        assert result[0]["targets"]["A"] > 0
        # Last keyframe should close mouth (all visemes 0)
        last = result[-1]
        assert last["targets"]["A"] == 0
        assert last["targets"]["I"] == 0

    def test_konnichiwa_phoneme_count(self):
        """'こんにちは' → keyframes for each phoneme + closing."""
        result = self.mapper.generate("こんにちは", audio_duration=1.0)
        # pyopenjtalk produces ~9 phonemes for こんにちは
        # plus 1 closing keyframe
        assert len(result) >= 5  # at minimum vowels + closing

    def test_konnichiwa_viseme_values(self):
        """'こんにちは' should map to O, (N), I, I, A visemes."""
        result = self.mapper.generate("こんにちは", audio_duration=1.0)
        # Collect non-zero visemes from keyframes (excluding closing)
        visemes = []
        for kf in result[:-1]:  # skip closing keyframe
            targets = kf["targets"]
            for v in ("A", "I", "U", "E", "O"):
                if targets.get(v, 0) > 0.5:
                    visemes.append(v)
                    break
        # Should contain O (ko), I (ni), I (chi), A (wa) at minimum
        assert "O" in visemes
        assert "I" in visemes
        assert "A" in visemes

    def test_duration_distribution(self):
        """Total keyframe durations should approximately equal audio_duration."""
        result = self.mapper.generate("こんにちは", audio_duration=1.0)
        total = sum(kf["duration"] for kf in result)
        assert abs(total - 1.0) < 0.1  # within 100ms tolerance

    def test_closing_keyframe(self):
        """Last keyframe should have all visemes at 0 and short duration."""
        result = self.mapper.generate("テスト", audio_duration=0.5)
        last = result[-1]
        assert last["duration"] == pytest.approx(0.05, abs=0.01)
        for v in ("A", "I", "U", "E", "O"):
            assert last["targets"][v] == 0

    def test_all_visemes_explicit_in_every_keyframe(self):
        """Every keyframe must contain all 5 viseme keys (even if 0)."""
        result = self.mapper.generate("あいうえお", audio_duration=1.0)
        for kf in result:
            for v in ("A", "I", "U", "E", "O"):
                assert v in kf["targets"], f"Missing {v} in keyframe targets"


class TestEmotionMerging:
    """Test emotion targets merged into viseme keyframes."""

    def setup_method(self):
        self.mapper = VisemeMapper()

    def test_emotion_targets_merged(self):
        """Emotion targets should appear in every keyframe."""
        emotion = {"happy": 1.0}
        result = self.mapper.generate("あ", audio_duration=0.5, emotion_targets=emotion)
        for kf in result:
            assert kf["targets"]["happy"] == 1.0

    def test_no_emotion_targets(self):
        """Without emotion_targets, keyframes should only have visemes."""
        result = self.mapper.generate("あ", audio_duration=0.5)
        for kf in result:
            assert "happy" not in kf["targets"]

    def test_multiple_emotion_targets(self):
        """Multiple emotion targets should all be present."""
        emotion = {"happy": 0.8, "fun": 0.5}
        result = self.mapper.generate("あ", audio_duration=0.5, emotion_targets=emotion)
        for kf in result:
            assert kf["targets"]["happy"] == 0.8
            assert kf["targets"]["fun"] == 0.5


class TestEdgeCases:
    """Test edge cases and graceful degradation."""

    def setup_method(self):
        self.mapper = VisemeMapper()

    def test_empty_text(self):
        """Empty text returns empty keyframes."""
        result = self.mapper.generate("", audio_duration=0.5)
        assert result == []

    def test_zero_duration(self):
        """Zero audio duration returns empty keyframes."""
        result = self.mapper.generate("こんにちは", audio_duration=0.0)
        assert result == []

    def test_non_japanese_text(self):
        """Non-Japanese text: graceful degradation (empty or best-effort)."""
        result = self.mapper.generate("hello world", audio_duration=1.0)
        # Should not raise, may return empty or best-effort
        assert isinstance(result, list)

    def test_mixed_text(self):
        """Mixed Japanese/non-Japanese should not raise."""
        result = self.mapper.generate("Hello こんにちは World", audio_duration=1.0)
        assert isinstance(result, list)

    def test_negative_duration(self):
        """Negative duration returns empty keyframes."""
        result = self.mapper.generate("あ", audio_duration=-1.0)
        assert result == []
