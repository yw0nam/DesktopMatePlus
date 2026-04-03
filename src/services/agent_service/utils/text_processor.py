import re
from pathlib import Path
from typing import NamedTuple

import yaml
from loguru import logger

_DEFAULT_EMOJI_SET: frozenset[str] = frozenset(
    [
        "😊",
        "😭",
        "😠",
        "😮",
        "😪",
        "🤭",
        "😰",
        "😆",
        "😱",
        "😟",
        "😌",
        "🤔",
        "😲",
        "😖",
        "🥺",
        "😏",
        "🫶",
        "😒",
        "🥵",
    ]
)

_DEFAULT_EMOTION_PROMPT_TEMPLATE = """
[EMOTION INSTRUCTIONS]
You MUST express your emotion using one of the following keywords in parentheses at the start of your response or when your emotion changes.
Available Keywords: {keywords}
Example: (joyful) I am so happy to see you!
"""


def _load_emojis_from_yaml(config_path: str | None = None) -> frozenset[str]:
    """Load known emojis from emotion_motion_map keys in tts_rules.yml."""
    if config_path:
        path = Path(config_path)
    else:
        path = Path(__file__).resolve().parents[4] / "yaml_files" / "tts_rules.yml"

    if not path.exists():
        return _DEFAULT_EMOJI_SET

    try:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict):
            motion_map = data.get("emotion_motion_map", {})
            keys = frozenset(k for k in motion_map if k != "default")
            return keys if keys else _DEFAULT_EMOJI_SET
    except Exception:
        pass
    return _DEFAULT_EMOJI_SET


def load_emotion_prompt_template(config_path: str | None = None) -> str:
    """Load emotion prompt template from a YAML configuration file."""
    if config_path:
        path = Path(config_path)
    else:
        path = Path(__file__).resolve().parents[4] / "yaml_files" / "tts_rules.yml"

    if not path.exists():
        return _DEFAULT_EMOTION_PROMPT_TEMPLATE

    try:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("emotion_prompt_template", _DEFAULT_EMOTION_PROMPT_TEMPLATE)
    except Exception:
        return _DEFAULT_EMOTION_PROMPT_TEMPLATE


class ProcessedText(NamedTuple):
    """처리된 텍스트의 구조화된 결과"""

    filtered_text: str
    emotion_tag: str | None


class TTSTextProcessor:
    def __init__(
        self,
        known_emojis: frozenset[str] | None = None,
        config_path: str | None = None,
    ):
        if known_emojis is not None:
            self.known_emojis = known_emojis
        else:
            self.known_emojis = _load_emojis_from_yaml(config_path)

        self.cleanup_patterns = [
            re.compile(r"\*[^*]*\*"),
            re.compile(r"\[[^\]]*\]"),
        ]

    def process_text(self, text: str) -> ProcessedText:
        if not text or not text.strip():
            return ProcessedText("", None)

        emotion_tag: str | None = None

        # 텍스트에서 첫 번째로 등장하는 known emoji를 emotion_tag로 추출
        # 이모지는 텍스트에서 제거하지 않음 (Irodori가 직접 사용)
        if self.known_emojis:
            first_pos = len(text)
            for emoji in self.known_emojis:
                pos = text.find(emoji)
                if pos != -1 and pos < first_pos:
                    first_pos = pos
                    emotion_tag = emoji

        filtered_text = self._clean_text(text)
        return ProcessedText(filtered_text, emotion_tag)

    def _clean_text(self, text: str) -> str:
        """불필요한 패턴 제거 (*행동 지시*, [메타] 등)"""
        cleaned = text
        for pattern in self.cleanup_patterns:
            cleaned = pattern.sub("", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip()


if __name__ == "__main__":
    # --- 테스트 예제 ---
    processor = TTSTextProcessor()

    # 예제 1: 영어 텍스트 (감정 태그)
    text1 = "I should check the user's mood first. (curious) So, how are you feeling today? *smiles warmly*"
    processed1 = processor.process_text(text1)
    logger.debug("--- 예제 1 ---")
    logger.debug(f"원본 텍스트: '{text1}'")
    logger.debug(f"필터링된 텍스트: '{processed1.filtered_text}'")
    logger.debug(f"감정 태그: {processed1.emotion_tag}")

    # 예제 2: 일본어 텍스트 (감정 태그 + 행동 지시)
    text2 = "(joyful)やったー！これで勝てる！ *ガッツポーズをする*"
    processed2 = processor.process_text(text2)
    logger.debug("--- 예제 2 ---")
    logger.debug(f"원본 텍스트: '{text2}'")
    logger.debug(f"필터링된 텍스트: '{processed2.filtered_text}'")
    logger.debug(f"감정 태그: {processed2.emotion_tag}")

    # TODO: 여러개의 감정태그를 처리할수 있도록 바꿔야할수도?
    # 예제 3: 톤 마커 및 웃음소리가 포함된 경우
    text3 = (
        "(whispering) I think I found a clue... (laughing) Ha,ha,ha, this is hilarious!"
    )
    processed3 = processor.process_text(text3)
    logger.debug("--- 예제 3 ---")
    logger.debug(f"원본 텍스트: '{text3}'")
    logger.debug(f"필터링된 텍스트: '{processed3.filtered_text}'")
    logger.debug(f"감정 태그: {processed3.emotion_tag}")
