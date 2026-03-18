"""Unit tests for WebSocket text processing utilities."""

from __future__ import annotations

from typing import List

from src.services.websocket_service.text_processors import (
    TextChunkProcessor,
    TTSTextProcessor,
    build_sentence_pipeline,
)


class TestTextChunkProcessor:
    """Validate sentence chunking behavior."""

    def test_multiple_sentences_single_chunk(self):
        processor = TextChunkProcessor(min_chunk_length=0)
        chunk = "Hello world. How are you? Great!"

        sentences = list(processor.process(chunk))

        assert sentences == ["Hello world.", "How are you?", "Great!"]
        assert processor.flush() is None

    def test_flush_returns_remainder(self):
        processor = TextChunkProcessor(min_chunk_length=0)

        list(processor.process("This is an incomplete"))
        remainder = processor.flush()

        assert remainder == "This is an incomplete"
        assert processor.flush() is None

    def test_multilingual_punctuation(self):
        processor = TextChunkProcessor(min_chunk_length=0)
        chunk = "첫 번째 문장입니다。第二句话！Third sentence?"

        sentences = list(processor.process(chunk))

        expected = ["첫 번째 문장입니다。", "第二句话！", "Third sentence?"]
        assert sentences == expected

    def test_min_chunk_length_merges_short_sentences(self):
        processor = TextChunkProcessor(min_chunk_length=30)
        # Each sentence is short; they should be merged until threshold is met
        tokens = [
            "Hi! ",
            "How are you? ",
            "I am doing great today and feeling wonderful!",
        ]

        sentences: List[str] = []
        for token in tokens:
            sentences.extend(processor.process(token))
        remainder = processor.flush()
        if remainder:
            sentences.append(remainder)

        # Short sentences ("Hi!" and "How are you?") should be merged together
        # before the long sentence triggers output
        assert all(
            len(s) >= 30 or i == len(sentences) - 1 for i, s in enumerate(sentences)
        )

    def test_min_chunk_length_loaded_from_yaml(self, tmp_path):
        rules_file = tmp_path / "rules.yml"
        rules_file.write_text("min_chunk_length: 10\n", encoding="utf-8")

        processor = TextChunkProcessor(rules_path=rules_file)
        # "Hi!" is 3 chars < 10, so it should be buffered
        sentences = list(processor.process("Hi! "))
        assert sentences == []

        # "Hi! How are you?" is 16 chars >= 10, should flush
        sentences = list(processor.process("How are you?"))
        remainder = processor.flush()
        all_output = sentences + ([remainder] if remainder else [])
        assert any("Hi!" in s for s in all_output)


class TestTTSTextProcessor:
    """Validate configurable regex transformations."""

    def test_loads_rules_from_yaml(self, tmp_path):
        rules_file = tmp_path / "rules.yml"
        rules_file.write_text(
            (
                "rules:\n"
                "  - pattern: '[0-9]'\n"
                "    replacement: '#'\n"
                "  - pattern: '\\s{2,}'\n"
                "    replacement: ' '\n"
            ),
            encoding="utf-8",
        )

        processor = TTSTextProcessor(rules_path=rules_file)
        processed = processor.process("Call 123   now")
        assert processed.filtered_text == "Call ### now"
        assert processed.emotion_tag is None

    def test_missing_rules_file_falls_back_to_defaults(self, tmp_path):
        processor = TTSTextProcessor(rules_path=tmp_path / "missing.yml")
        processed = processor.process("Hello   world")
        assert processed.filtered_text == "Hello world"
        assert processed.emotion_tag is None

    def test_parenthetical_nonverbal_removed(self, tmp_path):
        rules_file = tmp_path / "rules.yml"
        rules_file.write_text(
            "rules:\n  - pattern: '\\([^)]*\\)'\n    replacement: ''\n  - pattern: '\\s{2,}'\n    replacement: ' '\n",
            encoding="utf-8",
        )
        processor = TTSTextProcessor(rules_path=rules_file)

        result = processor.process("(嬉しそうに) 今日も一緒に楽しい時間を作ろうね！")
        assert "嬉しそうに" not in result.filtered_text
        assert "今日も一緒に楽しい時間を作ろうね" in result.filtered_text

    def test_production_rules_remove_nonverbal(self):
        """Verify the real tts_rules.yml filters non-verbal parenthetical content."""
        processor = TTSTextProcessor()

        result = processor.process("(手を振って) 何か面白いことある？")
        assert "手を振って" not in result.filtered_text
        assert "何か面白いことある" in result.filtered_text


class TestPipelineIntegration:
    """End-to-end pipeline expectations."""

    def test_pipeline_emits_clean_sentences(self, tmp_path):
        rules_file = tmp_path / "pipeline_rules.yml"
        rules_file.write_text(
            (
                "rules:\n"
                "  - pattern: '\\(aside\\)'\n"
                "    replacement: ''\n"
                "  - pattern: '\\s{2,}'\n"
                "    replacement: ' '\n"
            ),
            encoding="utf-8",
        )

        chunk_processor = TextChunkProcessor(min_chunk_length=0)
        tts_processor = TTSTextProcessor(rules_path=rules_file)

        tokens: List[str] = [
            "Hello world. ",
            "(aside)  All good?",
        ]

        outputs: List[str] = []
        for token in tokens:
            for sentence in chunk_processor.process(token):
                cleaned = tts_processor.process(sentence)
                if cleaned.filtered_text:
                    outputs.append(cleaned.filtered_text)

        remainder = chunk_processor.flush()
        if remainder:
            cleaned = tts_processor.process(remainder)
            if cleaned.filtered_text:
                outputs.append(cleaned.filtered_text)

        assert outputs == ["Hello world.", "All good?"]

    def test_pipeline_builder_returns_processed_text(self):
        processed = build_sentence_pipeline(["(laughing) Hello!", " All set."])

        assert [item.filtered_text for item in processed] == ["Hello!", "All set."]
        assert processed[0].emotion_tag == "laughing"
