# src/services/agent_service/utils/streaming_buffer.py


class StreamingBuffer:
    """Streaming token buffer with natural-break flushing.

    Accumulates incoming text tokens and flushes them when a natural break
    point is reached (sentence ending, word boundary) or a size limit is hit.

    Flush is triggered on the incoming token, not on the accumulated buffer end.
    """

    MIN_BUFFER_SIZE: int = 20
    MAX_BUFFER_SIZE: int = 100
    SENTENCE_ENDINGS: tuple[str, ...] = (".", "!", "?", "\n")
    WORD_ENDINGS: tuple[str, ...] = (" ", ",", ";", ":")

    def __init__(self) -> None:
        self._buffer: str = ""

    def add(self, content: str) -> str | None:
        """Accumulate a content token.

        Returns the flushed (stripped) buffer text when a threshold is met,
        or None if still accumulating. The internal buffer is cleared on flush.
        Whitespace-only or empty content is silently discarded.
        """
        if not content or content.isspace():
            return None

        self._buffer += content

        # Priority 1: MAX exceeded → force flush (memory guard)
        if len(self._buffer) > self.MAX_BUFFER_SIZE:
            return self._take()

        # Priority 2: sentence ending on incoming token + MIN size
        if (
            content.endswith(self.SENTENCE_ENDINGS)
            and len(self._buffer) >= self.MIN_BUFFER_SIZE
        ):
            return self._take()

        # Priority 3: word ending on incoming token + MIN*2 size
        if (
            content.endswith(self.WORD_ENDINGS)
            and len(self._buffer) >= self.MIN_BUFFER_SIZE * 2
        ):
            return self._take()

        return None

    def flush(self) -> str | None:
        """Return all remaining buffered text and reset.

        Strips the buffer before returning. Returns None if empty or whitespace-only.
        """
        return self._take()

    def _take(self) -> str | None:
        """Reset buffer and return stripped content, or None if empty."""
        # strip() is intentional: leading/trailing whitespace is irrelevant for TTS/streaming consumers
        result = self._buffer.strip()
        self._buffer = ""
        return result if result else None
