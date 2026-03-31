# tests/services/agent_service/test_streaming_buffer.py
from src.services.agent_service.utils.streaming_buffer import StreamingBuffer


def test_add_below_min_returns_none():
    buf = StreamingBuffer()
    assert buf.add("short") is None


def test_add_sentence_ending_flushes():
    # len("This is a long sentence.") == 24 >= MIN(20), ends with "."
    buf = StreamingBuffer()
    result = buf.add("This is a long sentence.")
    assert result == "This is a long sentence."
    assert buf.flush() is None  # buffer was cleared


def test_add_sentence_ending_below_min_does_not_flush():
    # ends with "." but len < 20 → still accumulates
    buf = StreamingBuffer()
    result = buf.add("Short.")
    assert result is None


def test_add_word_ending_flushes():
    # 47 chars, ends with " ", >= MIN*2(40) → flush
    buf = StreamingBuffer()
    text = "This is a very long text that ends with space "
    assert len(text) >= StreamingBuffer.MIN_BUFFER_SIZE * 2
    result = buf.add(text)
    assert result == text.strip()


def test_add_word_ending_below_double_min_does_not_flush():
    # ends with " " but len < 40 → still accumulates
    buf = StreamingBuffer()
    result = buf.add("Not long enough ")
    assert result is None


def test_add_max_exceeded_force_flush():
    # 101 chars > MAX(100) → force flush
    buf = StreamingBuffer()
    long_content = "a" * 101
    result = buf.add(long_content)
    assert result == long_content.strip()


def test_add_exactly_max_does_not_force_flush():
    # 100 chars == MAX, not >, no sentence/word ending → no flush
    buf = StreamingBuffer()
    result = buf.add("a" * 100)
    assert result is None


def test_flush_returns_remaining():
    buf = StreamingBuffer()
    buf.add("Hello")  # 5 chars, no threshold → accumulates
    result = buf.flush()
    assert result == "Hello"


def test_flush_empty_returns_none():
    buf = StreamingBuffer()
    assert buf.flush() is None


def test_flush_whitespace_only_returns_none():
    # add whitespace-only → discarded; buffer stays empty
    buf = StreamingBuffer()
    buf.add("   ")
    assert buf.flush() is None


def test_whitespace_only_discarded():
    buf = StreamingBuffer()
    result = buf.add("   ")
    assert result is None
    # Confirm nothing accumulated
    assert buf.flush() is None


def test_empty_string_discarded():
    buf = StreamingBuffer()
    result = buf.add("")
    assert result is None
    assert buf.flush() is None


def test_no_content_loss():
    # Accumulated tokens must equal final collected text
    buf = StreamingBuffer()
    tokens = ["Hello", " world", " how", " are", " you", "?"]
    # "?" triggers sentence flush: buffer="Hello world how are you?" (24 chars >= 20)
    collected = ""
    for token in tokens:
        flushed = buf.add(token)
        if flushed:
            collected += flushed
    remaining = buf.flush()
    if remaining:
        collected += remaining
    assert collected == "Hello world how are you?"


def test_endswith_check_is_on_incoming_token_not_buffer():
    # Buffer ends with "." after first add, but second token "x" doesn't end with sentence char
    # → no flush on second token even though buffer ends with "."
    buf = StreamingBuffer()
    buf.add("First sentence.")  # 15 chars < MIN(20), no flush
    result = buf.add("x")  # "x" doesn't end with sentence/word char → no flush
    assert result is None
    assert buf.flush() == "First sentence.x"
