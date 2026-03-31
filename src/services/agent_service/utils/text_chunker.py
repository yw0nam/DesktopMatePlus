import logging
import re

from fast_bunkai import FastBunkai

logger = logging.getLogger(__name__)


class TextChunkProcessor:
    # Characters that mark a real sentence end (vs FastBunkai's forced-final position)
    _SENTENCE_ENDERS = frozenset("。！？.!?\n")

    def __init__(
        self,
        reasoning_start_tag: str = "<think>",
        reasoning_end_tag: str = "</think>",
        min_chunk_length: int = 0,
    ):
        self._buffer = ""
        self._inside_reasoning = False
        self._min_chunk_length = min_chunk_length
        self._fb = FastBunkai()

        self._reasoning_pattern = re.compile(
            f"({re.escape(reasoning_start_tag)}|{re.escape(reasoning_end_tag)})",
            re.IGNORECASE,
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

    def add_chunk(self, chunk: str) -> list[str]:
        if not chunk:
            return []

        filtered_chunk = self._filter_reasoning_stream(chunk)
        if not filtered_chunk:
            return []

        self._buffer += filtered_chunk
        self._buffer = self._tool_call_pattern.sub("", self._buffer)

        result = []
        while any(c in self._SENTENCE_ENDERS for c in self._buffer):
            # find_eos always appends len(buffer) as a forced-final position.
            # Filter to positions preceded by an actual sentence-ending character
            # so we don't accidentally emit incomplete trailing text.
            positions = self._fb.find_eos(self._buffer)
            # FastBunkai includes trailing whitespace in each sentence, so the
            # character at p-1 may be a space. Strip trailing whitespace before
            # the position to find the real last character of the sentence.
            real_positions = [
                p
                for p in positions
                if p > 0
                and (s := self._buffer[:p].rstrip())
                and s[-1] in self._SENTENCE_ENDERS
            ]
            if not real_positions:
                break

            emitted = False
            for pos in real_positions:
                segment = self._buffer[:pos].strip()
                if len(segment) >= self._min_chunk_length:
                    result.append(segment)
                    self._buffer = self._buffer[pos:]
                    emitted = True
                    break
            if not emitted:
                break

        if result:
            logger.info(f"{len(result)}개의 청크 반환: {result}")

        return result

    def finalize(self) -> list[str]:
        self._buffer = self._tool_call_pattern.sub("", self._buffer)
        remaining_text = self._buffer.strip()
        self.reset()

        if not remaining_text:
            return []

        logger.info(f"마지막 남은 텍스트 처리: '{remaining_text[:50]}...'")
        return [remaining_text]

    def reset(self):
        self._buffer = ""
        self._inside_reasoning = False
        logger.debug("StreamingTTSProcessor 상태 초기화됨.")
