# Streaming Buffer Refactor — Design Spec

Date: 2026-03-15

## Problem

`openai_chat_agent.py:_process_message()` and `message_util.py:process_message()` contain
identical streaming buffer logic (token accumulation, MIN/MAX thresholds, natural-break
flushing). `message_util.process_message` is dead code (exported but never imported by any
consumer), making the duplication an active maintenance hazard if either copy drifts.

## Goal

1. Extract the streaming buffer logic into a single, testable `StreamingBuffer` class.
2. Delete the dead `message_util.process_message` function.
3. `_process_message` uses `StreamingBuffer`; its externally-visible behaviour is unchanged.

## Out of Scope

- `message_util.strip_images_from_messages`, `trim_messages`, `check_table_exists` — untouched.
- `TextChunkProcessor` in `text_chunker.py` — separate concern (TTS segmentation), untouched.
- WebSocket event types (`stream_token`, `tool_result`, `final_response`) — unchanged.

---

## Component Design

### `src/services/agent_service/utils/streaming_buffer.py` (NEW)

```python
class StreamingBuffer:
    MIN_BUFFER_SIZE: int = 20
    MAX_BUFFER_SIZE: int = 100
    SENTENCE_ENDINGS: tuple[str, ...] = (".", "!", "?", "\n")
    WORD_ENDINGS: tuple[str, ...] = (" ", ",", ";", ":")

    def add(self, content: str) -> str | None:
        """Accumulate content. Returns flushed text when threshold is met, else None."""

    def flush(self) -> str | None:
        """Return all remaining buffered text and reset. Returns None if empty."""
```

**Rules:**
- `add()` resets the internal buffer when it returns non-None.
- Flush triggers in priority order:
  1. MAX exceeded → force flush (memory guard)
  2. Ends with SENTENCE_ENDINGS AND len >= MIN → flush
  3. Ends with WORD_ENDINGS AND len >= MIN×2 → flush
- Whitespace-only content is silently discarded (returns None, no accumulation).
- `flush()` returns None on empty buffer (never returns empty string).

### `openai_chat_agent.py` (MODIFIED)

`_process_message` is simplified to:

```python
buffer = StreamingBuffer()
async for msg, metadata in agent.astream(...):
    if text_content:
        if flushed := buffer.add(text_content):
            yield self._flush_buffer(node, flushed)
    elif tool_call:
        ...  # unchanged

if remaining := buffer.flush():
    yield self._flush_buffer(node, remaining)
```

No change to yielded event shapes or error handling behaviour.

### `message_util.py` (MODIFIED)

- `process_message()` function deleted.
- `utils/__init__.py` export of `process_message` removed.
- All other functions in `message_util.py` untouched.

---

## Data Flow

```
LangGraph agent.astream()
    → token str
        → StreamingBuffer.add(token)
            → None (still accumulating)
            → str  (flush threshold hit)
                → _flush_buffer(node, str)
                    → {"type": "stream_token", "chunk": ...}  (non-tool node)
                    → {"type": "tool_result", "result": ...}  (tool node)
```

---

## Testing

### New: `tests/unit/test_streaming_buffer.py`

| Test | Assertion |
|------|-----------|
| `test_add_below_min_returns_none` | Short token → None |
| `test_add_sentence_ending_flushes` | `.` + len≥MIN → returns content, buffer empty |
| `test_add_word_ending_flushes` | ` ` + len≥MIN×2 → returns content |
| `test_add_max_exceeded_force_flush` | 101-char token → returns content |
| `test_flush_returns_remaining` | Partial buffer → flush returns it |
| `test_flush_empty_returns_none` | Empty buffer → None |
| `test_no_content_loss` | Series of add + final flush = original text |
| `test_whitespace_only_discarded` | `" "` → None, buffer unchanged |

### Existing tests

`openai_chat_agent.py` tests pass without modification (behaviour unchanged).
No `process_message` unit tests exist to delete.

---

## Files Changed

| File | Change |
|------|--------|
| `src/services/agent_service/utils/streaming_buffer.py` | NEW |
| `src/services/agent_service/utils/__init__.py` | Remove `process_message` export |
| `src/services/agent_service/utils/message_util.py` | Delete `process_message()` |
| `src/services/agent_service/openai_chat_agent.py` | Use `StreamingBuffer` in `_process_message` |
| `tests/unit/test_streaming_buffer.py` | NEW |
