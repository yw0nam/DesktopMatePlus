"""Emotion-to-keyframe mapper loaded from YAML config.

Config format:
    emotion_name:
      keyframes:
        - duration: 0.3
          targets:
            expression_name: weight   # float 0.0–1.0
    default:
      keyframes:
        - duration: 0.3
          targets:
            neutral: 1.0

Keyframe list format matches desktop-homunculus POST /vrm/{entity}/speech/timeline.
"""

from src.models.websocket import TimelineKeyframe

_HARDCODED_DEFAULT: list[TimelineKeyframe] = [
    {"duration": 0.3, "targets": {"neutral": 1.0}}
]


class EmotionMotionMapper:
    """Maps emotion keyword strings to desktop-homunculus timeline keyframes."""

    def __init__(self, config: dict[str, dict]):
        self._map = config
        default_entry = config.get("default", {})
        self._default: list[TimelineKeyframe] = (
            default_entry.get("keyframes") or _HARDCODED_DEFAULT
        )

    def map(self, emotion: str | None) -> list[TimelineKeyframe]:
        """Return keyframes list for the given emotion.

        Returns the default keyframes when emotion is None, empty, or unregistered.
        """
        entry = self._map.get(emotion) if emotion else None
        if entry is None:
            return self._default
        return entry.get("keyframes") or self._default
