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
- `add()` appends `content` to the internal buffer first, then evaluates flush conditions.
  When it returns non-None (the flushed text), the internal buffer is cleared to `""`.
  No carry-over of flushed content occurs.
- Flush triggers in priority order (evaluated after appending):
  1. `len(buffer) > MAX_BUFFER_SIZE` → force flush the full buffer (memory guard).
  2. **Incoming `content` token** (not the buffer) ends with `SENTENCE_ENDINGS` AND `len(buffer) >= MIN` → flush.
  3. **Incoming `content` token** ends with `WORD_ENDINGS` AND `len(buffer) >= MIN×2` → flush.
  - Note: `endswith` checks apply to the freshly received `content` argument, NOT to the accumulated buffer string.
- Whitespace-only content is silently discarded before accumulation (returns None, no accumulation).
- `flush()` strips the buffer before returning; returns `None` if the result is empty or whitespace-only.

**Error-path behaviour:**
`_process_message` must call `buffer.flush()` in its `except` block before yielding the error event,
to avoid silently dropping buffered tokens on exceptions. This mirrors the existing behaviour.

**Logging:**
`_process_message` retains its `chunk_count` counter and `logger.info(f"Processing completed: {chunk_count} chunks")` log line. `chunk_count` is incremented in `_process_message` each time `buffer.add()` or `buffer.flush()` returns non-None.

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
The module-level docstring referencing the old `process_message` function will be updated to reflect the current class structure.

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

### New: `tests/services/agent_service/test_streaming_buffer.py`

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
| `tests/services/agent_service/test_streaming_buffer.py` | NEW |
