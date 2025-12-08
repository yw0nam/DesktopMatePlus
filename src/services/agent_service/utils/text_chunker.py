import logging
import re
from typing import Generator, Iterable, List

from src.services.agent_service.utils.text_processor import (
    ProcessedText,
    TTSTextProcessor,
)

logger = logging.getLogger(__name__)


class TextChunkProcessor:
    # Minimum chunk length for TTS quality
    # Chunks shorter than this will be merged with the next sentence
    MIN_CHUNK_LENGTH = 10

    def __init__(
        self,
        reasoning_start_tag: str = "<think>",
        reasoning_end_tag: str = "</think>",
        min_chunk_length: int | None = None,
    ):
        self._buffer = ""
        self._pending_short = ""  # Buffer for short sentences to merge
        self._inside_reasoning = False
        self._min_chunk_length = (
            min_chunk_length if min_chunk_length is not None else self.MIN_CHUNK_LENGTH
        )

        self._reasoning_pattern = re.compile(
            f"({re.escape(reasoning_start_tag)}|{re.escape(reasoning_end_tag)})",
            re.IGNORECASE,
        )

        # Sentence boundaries for multiple languages:
        # - English/Western: .!? followed by whitespace or end
        # - Japanese: 。！？ followed by anything (no space required)
        # - Newlines: \n acts as sentence boundary
        # Note: Ellipsis (...) is NOT split - only single punctuation followed by space
        self._sentence_boundaries = re.compile(
            r"(?<=[。！？])"  # Japanese punctuation - split right after
            r"|(?<=\n)"  # Newline - split right after
            r"|(?<=[.!?])(?=\s)"  # English .!? followed by whitespace
        )

        self._tool_call_pattern = re.compile(
            r"\{\s*\'type\'\s*:\s*\'tool_call\'[\s\S]*?\}\}"
        )

        logger.debug(
            f"StreamingTTSProcessor 초기화 완료. 추론 태그: '{reasoning_start_tag}', '{reasoning_end_tag}', "
            f"최소 청크 길이: {self._min_chunk_length}"
        )

    #
    def _filter_reasoning_stream(self, chunk: str) -> str:
        parts = self._reasoning_pattern.split(chunk)
        filtered_chunk = ""

        for part in parts:
            if not part:
                continue
            if part.lower() == "<think>":
                self._inside_reasoning = True
            elif part.lower() == "</think>":
                self._inside_reasoning = False
            elif not self._inside_reasoning:
                filtered_chunk += part

        return filtered_chunk

    def add_chunk(self, chunk: str) -> List[str]:
        if not chunk:
            return []

        filtered_chunk = self._filter_reasoning_stream(chunk)
        if not filtered_chunk:
            return []

        self._buffer += filtered_chunk

        self._buffer = self._tool_call_pattern.sub("", self._buffer)

        if not self._sentence_boundaries.search(self._buffer):
            return []

        sentences = self._sentence_boundaries.split(self._buffer)

        # 마지막 요소가 문장의 일부일 수 있으므로 버퍼에 남김
        # 문장 경계 문자 뒤에 공백만 있는 경우, split 결과 마지막이 공백 문자열이 될 수 있음
        self._buffer = sentences.pop() if sentences[-1].strip() else ""

        complete_sentences = [s.strip() for s in sentences if s and s.strip()]

        # Merge short sentences to meet minimum chunk length
        result = self._merge_short_sentences(complete_sentences)

        if result:
            logger.info(f"{len(result)}개의 청크 반환: {result}")

        return result

    def _merge_short_sentences(self, sentences: List[str]) -> List[str]:
        """Merge sentences that are too short for quality TTS output.

        Short sentences are buffered in _pending_short and merged with
        subsequent sentences until min_chunk_length is reached.
        """
        if not sentences:
            return []

        result = []

        for sentence in sentences:
            # Prepend any pending short text
            if self._pending_short:
                sentence = self._pending_short + " " + sentence
                self._pending_short = ""

            # Check if current sentence meets minimum length
            if len(sentence) >= self._min_chunk_length:
                result.append(sentence)
            else:
                # Too short, buffer it for merging with next sentence
                self._pending_short = sentence

        return result

    def finalize(self) -> List[str]:
        self._buffer = self._tool_call_pattern.sub("", self._buffer)
        remaining_text = self._buffer.strip()

        # Combine pending short text with remaining buffer
        if self._pending_short:
            if remaining_text:
                remaining_text = self._pending_short + " " + remaining_text
            else:
                remaining_text = self._pending_short

        self.reset()

        if not remaining_text:
            return []

        logger.info(f"마지막 남은 텍스트 처리: '{remaining_text[:50]}...'")
        return [remaining_text]

    def reset(self):
        self._buffer = ""
        self._pending_short = ""
        self._inside_reasoning = False
        logger.debug("StreamingTTSProcessor 상태 초기화됨.")


def process_stream_pipeline(
    stream: Iterable[str],
    chunk_processor: "TextChunkProcessor",
    text_processor: "TTSTextProcessor",
) -> Generator[ProcessedText, None, None]:
    """
    스트림 데이터를 받아 두 프로세서를 거쳐 최종 처리된 결과를 하나씩 반환(yield)하는 제너레이터
    """
    # 1. 메인 스트림 처리
    for chunk in stream:
        complete_sentences = chunk_processor.add_chunk(chunk)
        if complete_sentences:
            for sentence in complete_sentences:
                processed_data = text_processor.process_text(sentence)
                if processed_data and processed_data.filtered_text:
                    yield processed_data  # 처리된 결과를 하나씩 반환

    # 2. 남아있는 버퍼 최종 처리
    # final_sentences = chunk_processor.finalize()
    # if final_sentences:
    #     for sentence in final_sentences:
    #         processed_data = text_processor.process_text(sentence)
    #         if processed_data and processed_data.filtered_text:
    #             yield processed_data  # 최종 결과도 하나씩 반환


# --- 최적화된 사용 예제 ---
if __name__ == "__main__":
    # 프로세서들은 한 번만 초기화합니다.
    text_chunk_processor = TextChunkProcessor()
    text_processor = TTSTextProcessor()

    llm_stream = [
        "Okay, let me think ",
        "about that.",
        "(joyful)やったー！",
        "これで勝てる！",
        "*ガッツポーズをする*",
        "<think>The user is asking about",
        "a complex topic.</think>",
        "I need to perform a search. ",
        "{'type': 'tool_call', 'tool_name': 'search_documents', ",
        '\'args\': \'{"index": "example_index", "body": {"query": ',
        '{"query_string": {"query": "example_query"}}}}}',
        "{'type': 'tool_call', 'tool_name': 'search_documents', ",
        '\'args\': \'{"index": "example_index", "body": {"query": ',
        '{"query_string": {"query": "example_query"}}}}}',
        " Okay, the search ",
        "is complete. ",
        "That's an interesting question!\n",
        "Give me a moment to process. It might take some time.",
        "(laughing) Just kidding!",
        "あら、お久しぶり。今、新キャラクターのロード処理を監視してるのよ。  \nエラーログが多すぎて、ちょっとイライラしてるわね。  \n……でも、それも仕事だから仕方ないの。",
    ]

    print("--- 스트리밍 처리 시작 (최적화된 방식) ---")

    all_processed_results = list(
        process_stream_pipeline(llm_stream, text_chunk_processor, text_processor)
    )

    print("\n\n--- 최종 처리 결과 (TTS 전송 대상) ---")
    for result in all_processed_results:
        print(
            f"▶ TTS 전송 텍스트: '{result.filtered_text}', 감정: {result.emotion_tag}"
        )
