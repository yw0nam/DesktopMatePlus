"""Maps Japanese text to VRM viseme (A/I/U/E/O) keyframes via pyopenjtalk G2P."""

from __future__ import annotations

from loguru import logger

from src.models.websocket import TimelineKeyframe

# Vowel phonemes → VRM viseme name + default weight
_VOWEL_MAP: dict[str, tuple[str, float]] = {
    "a": ("A", 0.9),
    "i": ("I", 0.7),
    "u": ("U", 0.6),
    "e": ("E", 0.7),
    "o": ("O", 0.8),
}

_VISEME_KEYS = ("A", "I", "U", "E", "O")
_CLOSING_DURATION = 0.05  # seconds for mouth-close keyframe
_COARTICULATION_WEIGHT = 0.3  # Consonant mouth shape blends to 30% of next vowel


class VisemeMapper:
    """Converts Japanese text to timed VRM viseme keyframes.

    Uses pyopenjtalk for grapheme-to-phoneme conversion,
    then maps each phoneme to A/I/U/E/O visemes with timing
    proportional to audio duration.
    """

    def generate(
        self,
        text: str,
        audio_duration: float,
        emotion_targets: dict[str, float] | None = None,
    ) -> list[TimelineKeyframe]:
        """Generate viseme keyframes from Japanese text.

        Args:
            text: Japanese text to convert to visemes.
            audio_duration: Duration of the TTS audio in seconds.
            emotion_targets: Emotion expression values to merge into every keyframe
                (e.g. {"happy": 1.0}). Prevents ClearAllExpressions from
                resetting emotions between viseme keyframes.

        Returns:
            List of TimelineKeyframe dicts. Empty list on failure or invalid input.
        """
        if not text or not text.strip() or audio_duration <= 0:
            return []

        phonemes = self._extract_phonemes(text)
        if not phonemes:
            return []

        # Reserve time for closing keyframe
        main_duration = audio_duration - _CLOSING_DURATION
        if main_duration <= 0:
            return []

        per_phoneme = main_duration / len(phonemes)
        keyframes: list[TimelineKeyframe] = []

        for idx, phoneme in enumerate(phonemes):
            targets: dict[str, float] = {}

            # Always include all 5 viseme keys explicitly
            vowel = self._phoneme_to_vowel(phoneme)
            if vowel:
                viseme_name, weight = vowel
                for k in _VISEME_KEYS:
                    targets[k] = weight if k == viseme_name else 0.0
            else:
                # Consonant/N/silence: check for coarticulation
                next_vowel = self._next_vowel(phonemes, idx)
                for k in _VISEME_KEYS:
                    if next_vowel and k == next_vowel[0]:
                        targets[k] = next_vowel[1] * _COARTICULATION_WEIGHT
                    else:
                        targets[k] = 0.0

            # Merge emotion targets
            if emotion_targets:
                targets.update(emotion_targets)

            keyframes.append({"duration": per_phoneme, "targets": targets})

        # Closing keyframe: all visemes zero
        closing_targets: dict[str, float] = {k: 0.0 for k in _VISEME_KEYS}
        if emotion_targets:
            closing_targets.update(emotion_targets)
        keyframes.append({"duration": _CLOSING_DURATION, "targets": closing_targets})

        return keyframes

    def _extract_phonemes(self, text: str) -> list[str]:
        """Extract phoneme list from text using pyopenjtalk."""
        try:
            import pyopenjtalk

            raw = pyopenjtalk.g2p(text)
            if not raw:
                return []
            # pyopenjtalk returns space-separated phonemes like "k o N n i ch i w a"
            return [p for p in raw.split() if p]
        except Exception:
            logger.warning(f"[Viseme] pyopenjtalk.g2p failed for text: {text[:30]}")
            return []

    def _phoneme_to_vowel(self, phoneme: str) -> tuple[str, float] | None:
        """Map a phoneme to its vowel viseme, or None if consonant/silence."""
        return _VOWEL_MAP.get(phoneme.lower())

    def _next_vowel(
        self, phonemes: list[str], current_idx: int
    ) -> tuple[str, float] | None:
        """Find the next vowel after current_idx for coarticulation."""
        for i in range(current_idx + 1, min(current_idx + 3, len(phonemes))):
            v = self._phoneme_to_vowel(phonemes[i])
            if v:
                return v
        return None
