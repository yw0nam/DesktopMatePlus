"""Unit tests for emoji-based emotion detection system (BE-FEAT-2)."""

from __future__ import annotations

import pytest

from src.services.agent_service.utils.text_processor import (
    ProcessedText,
    TTSTextProcessor,
)
from src.services.tts_service.emotion_motion_mapper import EmotionMotionMapper

EMOJI_CONFIG = {
    "😊": {"keyframes": [{"duration": 0.3, "targets": {"happy": 1.0}}]},
    "😭": {"keyframes": [{"duration": 0.3, "targets": {"sad": 1.0}}]},
    "😠": {"keyframes": [{"duration": 0.3, "targets": {"angry": 0.8}}]},
    "default": {"keyframes": [{"duration": 0.3, "targets": {"neutral": 1.0}}]},
}


class TestEmotionMotionMapperKnownEmojis:
    """EmotionMotionMapper.known_emojis property tests."""

    def test_known_emojis_returns_frozenset(self):
        mapper = EmotionMotionMapper(EMOJI_CONFIG)
        assert isinstance(mapper.known_emojis, frozenset)

    def test_known_emojis_contains_registered_emojis(self):
        mapper = EmotionMotionMapper(EMOJI_CONFIG)
        assert "😊" in mapper.known_emojis
        assert "😭" in mapper.known_emojis
        assert "😠" in mapper.known_emojis

    def test_known_emojis_excludes_default_key(self):
        mapper = EmotionMotionMapper(EMOJI_CONFIG)
        assert "default" not in mapper.known_emojis

    def test_known_emojis_empty_config(self):
        mapper = EmotionMotionMapper({})
        assert isinstance(mapper.known_emojis, frozenset)
        assert len(mapper.known_emojis) == 0

    def test_emoji_still_maps_to_keyframes(self):
        mapper = EmotionMotionMapper(EMOJI_CONFIG)
        keyframes = mapper.map("😊")
        assert keyframes == [{"duration": 0.3, "targets": {"happy": 1.0}}]


class TestTTSTextProcessorEmojiDetection:
    """TTSTextProcessor detects first known emoji as emotion_tag."""

    def test_emoji_at_start_detected(self):
        known = frozenset(["😊", "😭", "😠"])
        processor = TTSTextProcessor(known_emojis=known)
        result = processor.process_text("😊今日も楽しいね！")
        assert result.emotion_tag == "😊"

    def test_emoji_in_middle_detected(self):
        known = frozenset(["😊", "😭"])
        processor = TTSTextProcessor(known_emojis=known)
        result = processor.process_text("元気だった😊？")
        assert result.emotion_tag == "😊"

    def test_emoji_not_removed_from_text(self):
        known = frozenset(["😊"])
        processor = TTSTextProcessor(known_emojis=known)
        result = processor.process_text("😊今日も楽しいね！")
        assert "😊" in result.filtered_text

    def test_first_emoji_wins(self):
        known = frozenset(["😊", "😭"])
        processor = TTSTextProcessor(known_emojis=known)
        result = processor.process_text("😊楽しい！😭悲しい。")
        assert result.emotion_tag == "😊"

    def test_unknown_emoji_ignored(self):
        known = frozenset(["😊"])
        processor = TTSTextProcessor(known_emojis=known)
        result = processor.process_text("😂これは面白い！")
        assert result.emotion_tag is None

    def test_no_emoji_returns_none_emotion_tag(self):
        known = frozenset(["😊", "😭"])
        processor = TTSTextProcessor(known_emojis=known)
        result = processor.process_text("普通のテキストです。")
        assert result.emotion_tag is None

    def test_empty_known_emojis_returns_none(self):
        processor = TTSTextProcessor(known_emojis=frozenset())
        result = processor.process_text("😊楽しい！")
        assert result.emotion_tag is None

    def test_empty_text_returns_empty(self):
        known = frozenset(["😊"])
        processor = TTSTextProcessor(known_emojis=known)
        result = processor.process_text("")
        assert result == ProcessedText("", None)

    def test_loads_emojis_from_yaml_when_none(self, tmp_path):
        """When known_emojis=None, TTSTextProcessor loads from tts_rules.yml."""
        rules_file = tmp_path / "tts_rules.yml"
        rules_file.write_text(
            "emotion_motion_map:\n  😊:\n    keyframes:\n      - duration: 0.3\n        targets:\n          happy: 1.0\n",
            encoding="utf-8",
        )
        processor = TTSTextProcessor(config_path=str(rules_file))
        result = processor.process_text("😊今日も楽しいね！")
        assert result.emotion_tag == "😊"


class TestTTSFactoryNoFishSpeech:
    """fish_local_tts must be removed from TTSFactory."""

    def test_fish_local_tts_raises_value_error(self):
        from src.services.tts_service.tts_factory import TTSFactory

        with pytest.raises(ValueError, match="Unknown TTS engine type"):
            TTSFactory.get_tts_engine(
                "fish_local_tts", base_url="http://localhost:8080/v1/tts"
            )

    def test_irodori_engine_created(self):
        from src.services.tts_service.irodori_tts import IrodoriTTSService
        from src.services.tts_service.tts_factory import TTSFactory

        engine = TTSFactory.get_tts_engine("irodori", base_url="http://localhost:8000")
        assert isinstance(engine, IrodoriTTSService)

    def test_vllm_omni_still_works(self):
        from src.services.tts_service.tts_factory import TTSFactory
        from src.services.tts_service.vllm_omni import VLLMOmniTTSService

        engine = TTSFactory.get_tts_engine(
            "vllm_omni", base_url="http://localhost:5517"
        )
        assert isinstance(engine, VLLMOmniTTSService)
