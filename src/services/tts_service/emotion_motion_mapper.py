"""Emotion-to-motion/blendshape mapper loaded from YAML config."""

_HARDCODED_DEFAULT: dict[str, str] = {
    "motion": "neutral_idle",
    "blendshape": "neutral",
}


class EmotionMotionMapper:
    """Maps emotion keyword strings to Unity motion + blendshape names."""

    def __init__(self, config: dict[str, dict[str, str]]):
        self._map = config
        self._default: dict[str, str] = {
            **_HARDCODED_DEFAULT,
            **config.get("default", {}),
        }

    def map(self, emotion: str | None) -> tuple[str, str]:
        """Return (motion_name, blendshape_name) for the given emotion."""
        entry = self._map.get(emotion) if emotion else None
        if entry is None:
            return self._default["motion"], self._default["blendshape"]
        return (
            entry.get("motion", self._default["motion"]),
            entry.get("blendshape", self._default["blendshape"]),
        )
