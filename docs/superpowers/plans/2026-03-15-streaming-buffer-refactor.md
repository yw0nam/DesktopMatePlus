# Streaming Buffer Refactor Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract duplicated streaming buffer logic into a single `StreamingBuffer` class and delete the dead `message_util.process_message` function.

**Architecture:** New `StreamingBuffer` class encapsulates token accumulation and threshold-based flushing. `_process_message` in `OpenAIChatAgent` delegates buffer management to it. Dead standalone `process_message` function is removed.

**Tech Stack:** Python 3.13, pytest (asyncio_mode=auto), uv run python -m pytest

**Spec:** `docs/superpowers/specs/2026-03-15-streaming-buffer-refactor-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/services/agent_service/utils/streaming_buffer.py` | CREATE | `StreamingBuffer` class — token accumulation + flush logic |
| `tests/services/agent_service/test_streaming_buffer.py` | CREATE | Unit tests for `StreamingBuffer` |
| `src/services/agent_service/openai_chat_agent.py` | MODIFY | `_process_message` uses `StreamingBuffer`; `__doc__` updated |
| `src/services/agent_service/utils/message_util.py` | MODIFY | Delete `process_message()` function |
| `src/services/agent_service/utils/__init__.py` | MODIFY | Remove `process_message` export |

---

## Chunk 1: StreamingBuffer class (TDD)

### Task 1: Write failing tests for StreamingBuffer

**Files:**
- Create: `tests/services/agent_service/test_streaming_buffer.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/services/agent_service/test_streaming_buffer.py
import pytest
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
    result = buf.add("x")      # "x" doesn't end with sentence/word char → no flush
    assert result is None
    assert buf.flush() == "First sentence.x"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend
uv run python -m pytest tests/services/agent_service/test_streaming_buffer.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` — `streaming_buffer` does not exist yet.

---

### Task 2: Implement StreamingBuffer

**Files:**
- Create: `src/services/agent_service/utils/streaming_buffer.py`

- [ ] **Step 3: Write the implementation**

```python
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
        result = self._buffer.strip()
        self._buffer = ""
        return result if result else None
```

- [ ] **Step 4: Run tests to verify they all pass**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend
uv run python -m pytest tests/services/agent_service/test_streaming_buffer.py -v
```

Expected: All 14 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend
git add src/services/agent_service/utils/streaming_buffer.py \
        tests/services/agent_service/test_streaming_buffer.py
git commit -m "feat: StreamingBuffer class with unit tests"
```

---

## Chunk 2: Refactor _process_message

### Task 3: Refactor _process_message to use StreamingBuffer

**Files:**
- Modify: `src/services/agent_service/openai_chat_agent.py`

The refactored `_process_message` removes the inline buffer variables
(`content_buffer`, `MIN_BUFFER_SIZE`, `MAX_BUFFER_SIZE`, `SENTENCE_ENDINGS`, `WORD_ENDINGS`,
`should_send`, `chunk_count` local block) and delegates to `StreamingBuffer`.
The `chunk_count` counter and logger line are preserved. Externally-visible
event shapes (`stream_token`, `tool_result`, `final_response`, `error`) are unchanged.

- [ ] **Step 6: Add top-level import for `StreamingBuffer` in `openai_chat_agent.py`**

Add this import alongside the existing imports at the top of the file (after the `from src.services.agent_service.service import AgentService` line):

```python
from src.services.agent_service.utils.streaming_buffer import StreamingBuffer
```

- [ ] **Step 6b: Replace `_process_message` method in `openai_chat_agent.py`**

Replace the entire `_process_message` method only. The method starts at `async def _process_message(` and ends at the `except` block's closing line (the line with `"error": "메시지 처리 중 오류가 발생했습니다."}`). The `if __name__ == "__main__":` block below it must remain untouched.

Replace only the `_process_message` method with:

```python
    async def _process_message(
        self,
        messages: list[BaseMessage],
        agent: CompiledStateGraph,
        config: RunnableConfig,
    ):
        """메시지를 처리하고 스트리밍 응답을 생성합니다."""
        logger.debug(f"Processing {len(messages)} messages with agent")

        node = None
        tool_called = False
        gathered = ""
        chunk_count = 0
        buffer = StreamingBuffer()

        try:
            async for msg, metadata in agent.astream(
                {"messages": messages}, stream_mode="messages", config=config
            ):
                if node != metadata.get("langgraph_node"):
                    node = metadata.get("langgraph_node", "unknown")

                if isinstance(msg.content, str) and not msg.additional_kwargs:
                    content = msg.content
                    if not content or content.isspace():
                        continue

                    if flushed := buffer.add(content):
                        yield self._flush_buffer(node, flushed)
                        chunk_count += 1

                elif isinstance(msg, AIMessageChunk) and msg.additional_kwargs.get(
                    "tool_calls"
                ):
                    if not tool_called:
                        gathered = msg
                        tool_called = True
                    else:
                        gathered = gathered + msg

                    if hasattr(msg, "tool_call_chunks") and msg.tool_call_chunks:
                        tool_info = gathered.tool_call_chunks[0]
                        args_str = tool_info.get("args", "")
                        if args_str and args_str.strip().endswith("}"):
                            tool_name = tool_info.get("name", "unknown")
                            logger.info(f"Tool call detected: '{tool_name}'")
                            yield {
                                "type": "tool_call",
                                "tool_name": tool_name,
                                "args": args_str,
                                "node": node,
                            }
                            tool_called = False
                            gathered = ""

            if remaining := buffer.flush():
                yield self._flush_buffer(node, remaining)
                chunk_count += 1

            state = agent.get_state(config=config)
            new_chats = state.values["messages"][len(messages) - 1 :]
            yield {
                "type": "final_response",
                "data": new_chats,
            }
            logger.info(f"Processing completed: {chunk_count} chunks")

        except Exception as e:
            logger.error(f"Error in process_message: {e}")
            if remaining := buffer.flush():
                yield self._flush_buffer(node, remaining)
            yield {
                "type": "error",
                "error": "메시지 처리 중 오류가 발생했습니다.",
            }
```

Also update the module-level `__doc__` string at the top of the file (lines 30–45).
Remove the stale `process_message` reference from the `Functions:` section.
Do NOT list `StreamingBuffer` here — it is defined in `utils/streaming_buffer.py`, not this module.

```python
__doc__ = """
This module contains the implementation of the OpenAIChatAgent class, which provides
functionality for processing chat messages using a language model and tools from a
Multi-Server MCP client.

Classes:
- OpenAIChatAgent: Processes chat messages via LangGraph react agent with tool support.

Functions:
- stream: Initializes the agent with the provided language model and configuration,
  then streams message processing results.

Example usage:
    agent = OpenAIChatAgent(temperature=0.7, top_p=0.9, ...)
    async for result in agent.stream(messages=[...]):
        print(result)
"""
```

- [ ] **Step 7: Run the full agent service test suite**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend
uv run python -m pytest tests/services/agent_service/ -v
```

Expected: All tests PASS (including `test_streaming_buffer.py`).

- [ ] **Step 8: Commit**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend
git add src/services/agent_service/openai_chat_agent.py
git commit -m "refactor: _process_message uses StreamingBuffer"
```

---

## Chunk 3: Delete dead code

### Task 4: Remove dead process_message function

**Files:**
- Modify: `src/services/agent_service/utils/message_util.py`
- Modify: `src/services/agent_service/utils/__init__.py`

- [ ] **Step 9a: Pre-flight — verify no production consumer imports `process_message`**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend
grep -r "process_message" src/ --include="*.py" | grep -v "__init__.py" | grep -v "message_util.py"
```

Expected: **no output** (zero matches). If any match appears, do NOT delete — investigate first.

- [ ] **Step 9b: Verify which imports in `message_util.py` are unused after deletion**

```bash
grep -n "AIMessageChunk\|RunnableConfig\|CompiledStateGraph" \
    src/services/agent_service/utils/message_util.py
```

Expected output:
```
11: from langchain_core.messages import (
12:     AIMessage,
13:     AIMessageChunk,   ← only used in process_message (now deleted)
...
13: from langchain_core.runnables import RunnableConfig   ← only used in process_message
14: from langgraph.graph.state import CompiledStateGraph  ← only used in process_message
```

All three are safe to remove. Confirm none appear in `trim_messages`, `check_table_exists`, or `strip_images_from_messages`.

- [ ] **Step 9c: Delete `process_message` and its now-unused imports from `message_util.py`**

Delete the entire `process_message` function (lines 76–199 in the original file).
Remove the following imports from the top of the file (they were only needed by `process_message`):
- `from langchain_core.runnables import RunnableConfig`
- `from langgraph.graph.state import CompiledStateGraph`
- `AIMessageChunk` from the `langchain_core.messages` import block

After deletion, `message_util.py` should contain only:
- `trim_messages()`
- `check_table_exists()`
- `strip_images_from_messages()`

- [ ] **Step 10: Update `utils/__init__.py`**

Remove `process_message` import and `__all__` entry:

```python
# src/services/agent_service/utils/__init__.py
from src.services.agent_service.utils.text_chunker import (
    TextChunkProcessor,
    process_stream_pipeline,
)
from src.services.agent_service.utils.text_processor import TTSTextProcessor

__all__ = [
    "TextChunkProcessor",
    "TTSTextProcessor",
    "process_stream_pipeline",
]
```

- [ ] **Step 11: Run full test suite**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend
uv run python -m pytest -v
```

Expected: All tests PASS. No import errors.

- [ ] **Step 12: Run lint**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend
sh scripts/lint.sh
```

Expected: No errors.

- [ ] **Step 13: Commit**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend
git add src/services/agent_service/utils/message_util.py \
        src/services/agent_service/utils/__init__.py
git commit -m "refactor: delete dead process_message function"
```
