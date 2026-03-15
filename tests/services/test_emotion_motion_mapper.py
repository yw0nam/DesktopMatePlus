"""Unit tests for EmotionMotionMapper."""

from src.services.tts_service.emotion_motion_mapper import EmotionMotionMapper

SAMPLE_CONFIG = {
    "joyful": {"motion": "happy_idle", "blendshape": "smile"},
    "sad": {"motion": "sad_idle", "blendshape": "sad"},
    "default": {"motion": "neutral_idle", "blendshape": "neutral"},
}


class TestEmotionMotionMapperRegistered:
    def test_joyful_returns_correct_motion(self):
        mapper = EmotionMotionMapper(SAMPLE_CONFIG)
        motion, blendshape = mapper.map("joyful")
        assert motion == "happy_idle"
        assert blendshape == "smile"

    def test_sad_returns_correct_motion(self):
        mapper = EmotionMotionMapper(SAMPLE_CONFIG)
        motion, blendshape = mapper.map("sad")
        assert motion == "sad_idle"
        assert blendshape == "sad"


class TestEmotionMotionMapperDefault:
    def test_unregistered_emotion_returns_default(self):
        mapper = EmotionMotionMapper(SAMPLE_CONFIG)
        motion, blendshape = mapper.map("unknown_emotion")
        assert motion == "neutral_idle"
        assert blendshape == "neutral"

    def test_none_emotion_returns_default(self):
        mapper = EmotionMotionMapper(SAMPLE_CONFIG)
        motion, blendshape = mapper.map(None)
        assert motion == "neutral_idle"
        assert blendshape == "neutral"

    def test_empty_string_returns_default(self):
        mapper = EmotionMotionMapper(SAMPLE_CONFIG)
        motion, blendshape = mapper.map("")
        assert motion == "neutral_idle"
        assert blendshape == "neutral"


class TestEmotionMotionMapperFallback:
    def test_missing_default_key_uses_hardcoded_fallback(self):
        config = {"joyful": {"motion": "happy_idle", "blendshape": "smile"}}
        mapper = EmotionMotionMapper(config)
        motion, blendshape = mapper.map("unregistered")
        assert motion == "neutral_idle"
        assert blendshape == "neutral"

    def test_empty_config_returns_hardcoded_fallback(self):
        mapper = EmotionMotionMapper({})
        motion, blendshape = mapper.map(None)
        assert motion == "neutral_idle"
        assert blendshape == "neutral"

    def test_partial_entry_missing_blendshape_falls_back_to_default(self):
        config = {
            "odd": {"motion": "odd_idle"},
            "default": {"motion": "neutral_idle", "blendshape": "neutral"},
        }
        mapper = EmotionMotionMapper(config)
        motion, blendshape = mapper.map("odd")
        assert motion == "odd_idle"
        assert blendshape == "neutral"
