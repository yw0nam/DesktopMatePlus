"""Unit tests for EmotionMotionMapper — keyframes return format."""

from src.services.tts_service.emotion_motion_mapper import EmotionMotionMapper

SAMPLE_CONFIG = {
    "joyful": {"keyframes": [{"duration": 0.3, "targets": {"happy": 1.0}}]},
    "sad": {"keyframes": [{"duration": 0.4, "targets": {"sad": 0.8}}]},
    "default": {"keyframes": [{"duration": 0.3, "targets": {"neutral": 1.0}}]},
}


class TestEmotionMotionMapperRegistered:
    def test_joyful_returns_keyframes(self):
        mapper = EmotionMotionMapper(SAMPLE_CONFIG)
        keyframes = mapper.map("joyful")
        assert keyframes == [{"duration": 0.3, "targets": {"happy": 1.0}}]

    def test_sad_returns_keyframes(self):
        mapper = EmotionMotionMapper(SAMPLE_CONFIG)
        keyframes = mapper.map("sad")
        assert keyframes == [{"duration": 0.4, "targets": {"sad": 0.8}}]


class TestEmotionMotionMapperDefault:
    def test_unregistered_emotion_returns_default(self):
        mapper = EmotionMotionMapper(SAMPLE_CONFIG)
        keyframes = mapper.map("unknown_emotion")
        assert keyframes == [{"duration": 0.3, "targets": {"neutral": 1.0}}]

    def test_none_emotion_returns_default(self):
        mapper = EmotionMotionMapper(SAMPLE_CONFIG)
        keyframes = mapper.map(None)
        assert keyframes == [{"duration": 0.3, "targets": {"neutral": 1.0}}]

    def test_empty_string_returns_default(self):
        mapper = EmotionMotionMapper(SAMPLE_CONFIG)
        keyframes = mapper.map("")
        assert keyframes == [{"duration": 0.3, "targets": {"neutral": 1.0}}]


class TestEmotionMotionMapperFallback:
    def test_missing_default_key_uses_hardcoded_fallback(self):
        config = {
            "joyful": {"keyframes": [{"duration": 0.3, "targets": {"happy": 1.0}}]}
        }
        mapper = EmotionMotionMapper(config)
        keyframes = mapper.map("unregistered")
        # Should return hardcoded default: neutral expression
        assert isinstance(keyframes, list)
        assert len(keyframes) == 1
        assert "targets" in keyframes[0]
        assert "neutral" in keyframes[0]["targets"]

    def test_empty_config_returns_hardcoded_fallback(self):
        mapper = EmotionMotionMapper({})
        keyframes = mapper.map(None)
        assert isinstance(keyframes, list)
        assert len(keyframes) >= 1

    def test_returns_list_type(self):
        mapper = EmotionMotionMapper(SAMPLE_CONFIG)
        result = mapper.map("joyful")
        assert isinstance(result, list)

    def test_multiple_keyframes_preserved(self):
        config = {
            "excited": {
                "keyframes": [
                    {"duration": 0.2, "targets": {"happy": 0.5}},
                    {"duration": 0.3, "targets": {"happy": 1.0}},
                ]
            },
            "default": {"keyframes": [{"duration": 0.3, "targets": {"neutral": 1.0}}]},
        }
        mapper = EmotionMotionMapper(config)
        keyframes = mapper.map("excited")
        assert len(keyframes) == 2
        assert keyframes[0]["duration"] == 0.2
        assert keyframes[1]["duration"] == 0.3
