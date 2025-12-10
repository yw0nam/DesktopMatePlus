"""Token-to-TTS processors reusing agent service utilities with extra rules."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Pattern, Tuple

import yaml
from loguru import logger

from src.services.agent_service.utils.text_chunker import (  # noqa: WPS347
    TextChunkProcessor as AgentTextChunkProcessor,
)
from src.services.agent_service.utils.text_processor import (  # noqa: WPS347
    ProcessedText,
)
from src.services.agent_service.utils.text_processor import (
    TTSTextProcessor as AgentTTSTextProcessor,
)

_DEFAULT_RULES: List[dict] = [
    {"pattern": r"\((?:웃음|giggle)\)", "replacement": ""},
    {"pattern": r"\b(?:음|uh|um)+[\.\u2026]*", "replacement": ""},
    {"pattern": r"\s{2,}", "replacement": " "},
]


class TextChunkProcessor:
    """Wrapper exposing the agent chunker with a generator-style API."""

    def __init__(self) -> None:
        self._delegate = AgentTextChunkProcessor()

    def process(self, token: str) -> Iterator[str]:
        """Yield completed sentences after ingesting a token fragment."""

        if not token:
            return

        for sentence in self._delegate.add_chunk(token):
            yield sentence

    def flush(self) -> Optional[str]:
        """Return any buffered text that never reached a terminator."""

        sentences = self._delegate.finalize()
        if not sentences:
            return None

        # Join multiple sentences if present to ensure no data is lost
        return " ".join(sentences)

    def reset(self) -> None:
        """Reset underlying processor state."""

        self._delegate.reset()


class TTSTextProcessor:
    """Configurable regex cleanup layered on top of the agent processor."""

    def __init__(self, rules_path: Optional[str | Path] = None) -> None:
        self._delegate = AgentTTSTextProcessor()
        self._rules_path = (
            Path(rules_path)
            if rules_path
            else Path(__file__).resolve().parents[3] / "yaml_files" / "tts_rules.yml"
        )
        self._compiled_rules = self._load_rules(self._rules_path)

    def process(self, text: str) -> ProcessedText:
        """Apply the agent processor first, then configurable replacements."""

        if not text:
            return ProcessedText("", None)

        processed = self._delegate.process_text(text)
        filtered = processed.filtered_text

        for pattern, replacement in self._compiled_rules:
            filtered = pattern.sub(replacement, filtered)

        filtered = re.sub(r"\s{2,}", " ", filtered).strip()
        return ProcessedText(filtered, processed.emotion_tag)

    def _load_rules(self, path: Path) -> List[Tuple[Pattern[str], str]]:
        data = None

        if path.exists():
            try:
                if path.suffix.lower() in {".yaml", ".yml"}:
                    with path.open("r", encoding="utf-8") as stream:
                        data = yaml.safe_load(stream)
                elif path.suffix.lower() == ".json":
                    with path.open("r", encoding="utf-8") as stream:
                        data = json.load(stream)
                else:
                    logger.warning(f"Unsupported rules file extension: {path}")
            except (
                yaml.YAMLError,
                json.JSONDecodeError,
                OSError,
            ) as exc:  # pragma: no cover - defensive
                logger.error(f"Failed to load TTS rules from {path}: {exc}")

        rules: Iterable[dict]
        if isinstance(data, dict):
            rules = data.get("rules", _DEFAULT_RULES)
        elif isinstance(data, list):
            rules = data
        else:
            rules = _DEFAULT_RULES

        compiled: List[Tuple[Pattern[str], str]] = []
        for rule in rules:
            pattern = rule.get("pattern")
            replacement = rule.get("replacement", "")
            if not pattern:
                continue
            try:
                compiled.append((re.compile(pattern), replacement))
            except re.error as exc:  # pragma: no cover - defensive
                logger.warning(f"Skipping invalid regex pattern {pattern}: {exc}")

        if not compiled:
            compiled = [(re.compile(r"\s{2,}"), " ")]

        return compiled


def build_sentence_pipeline(tokens: Iterable[str]) -> List[ProcessedText]:
    """Utility to run the combined pipeline on an iterable of token chunks."""

    chunker = TextChunkProcessor()
    cleaner = TTSTextProcessor()
    results: List[ProcessedText] = []

    for token in tokens:
        for sentence in chunker.process(token):
            processed = cleaner.process(sentence)
            text = processed.filtered_text
            if text and any(char.isalnum() for char in text):
                results.append(ProcessedText(text, processed.emotion_tag))

    remainder = chunker.flush()
    if remainder:
        processed = cleaner.process(remainder)
        text = processed.filtered_text
        if text and any(char.isalnum() for char in text):
            results.append(ProcessedText(text, processed.emotion_tag))

    return results
