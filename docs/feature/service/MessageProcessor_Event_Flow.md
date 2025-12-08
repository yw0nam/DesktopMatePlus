# MessageProcessor Event Flow

Updated: 2024-12-08

## 1. Synopsis

- **Purpose**: Stream agent responses through WebSocket with real-time TTS chunk generation
- **I/O**: Agent stream events → TTS-ready text chunks → WebSocket client

## 2. Core Logic

### 2.1 Architecture Overview

```
Agent Stream → Producer → Token Queue → Consumer → Event Queue → WebSocket
                  ↓                         ↓           ↓
            [stream_start]           [TTS chunks]  [stream_end]
            [stream_token]           [emotion tags]
            [stream_end]
```

### 2.2 Key Components

**MessageProcessor** (`processor.py`)
- Orchestrates conversation turn lifecycle
- Manages event_queue (output to WebSocket)
- Manages token_queue (internal processing)

**EventHandler** (`event_handlers.py`)
- `produce_agent_events()`: Consumes agent stream, routes events
- `consume_token_events()`: Processes tokens into TTS chunks

**Text Processors**
- `TextChunkProcessor`: Splits text on sentence boundaries (`.!?。！？`)
- `TTSTextProcessor`: Filters/normalizes text, extracts emotion tags

### 2.3 Event Flow Phases

#### Phase 1: Producer (Agent Stream → Token Queue)

```python
async def produce_agent_events(turn_id, agent_stream):
    async for event in agent_stream:
        event_type = event.get("type")

        if event_type == "stream_token":
            # Put in token_queue for TTS processing
            await token_queue.put(event)

        elif event_type == "stream_start":
            # Forward directly to event_queue
            await event_queue.put(event)

        elif event_type == "stream_end":
            # Signal closure + wait for consumer
            await token_queue.put(SENTINEL)
            await queue.join()  # Wait for queue drain
            await consumer_task  # Wait for flush complete
            await event_queue.put(event)
```

**Critical Rule**: Producer MUST wait for consumer task completion before emitting `stream_end`.

#### Phase 2: Consumer (Token Queue → Event Queue)

```python
async def consume_token_events(turn_id):
    while True:
        token_event = await token_queue.get()

        if token_event is SENTINEL:
            # Flush remaining buffer
            await _flush_tts_buffer(turn_id)
            queue.task_done()
            break

        # Process token into sentences
        chunk = token_event.get("chunk")
        for sentence in chunk_processor.process(chunk):
            # Generate TTS event
            tts_event = {
                "type": "tts_ready_chunk",
                "chunk": sentence,
                "emotion": tts_processor.process(sentence).emotion_tag
            }
            await event_queue.put(tts_event)

        queue.task_done()
```

**Critical Rule**: Consumer MUST call `task_done()` for every item removed from queue.

#### Phase 3: Forwarder (Event Queue → WebSocket)

```python
async def forward_turn_events(turn_id, connection_id):
    async for event in message_processor.stream_events(turn_id):
        event_json = json.dumps(event)
        await websocket.send_text(event_json)
```

### 2.4 Synchronization Guarantees

**Problem**: Race condition where `stream_end` overtakes TTS chunks

**Solution**: Two-phase wait in `_wait_for_token_queue()`:

```python
async def _wait_for_token_queue(turn_id):
    # Phase 1: Wait for queue items to be removed
    await queue.join()

    # Phase 2: Wait for consumer task to finish (includes flush)
    consumer_task = turn.token_consumer_task
    if consumer_task and not consumer_task.done():
        await asyncio.wait_for(consumer_task, timeout=1.0)
```

This ensures:
1. All tokens processed
2. Buffer flushed
3. All TTS chunks emitted
4. THEN stream_end emitted

### 2.5 Text Processing Pipeline

**Sentence Boundary Detection** (TextChunkProcessor)

```python
# Supports multi-language punctuation
SENTENCE_PATTERN = r"(?<=[。！？])|(?<=\n)|(?<=[.!?])(?=\s)"

# Minimum chunk length (prevents poor TTS quality)
MIN_CHUNK_LENGTH = 10

# Short sentences are buffered and merged
"Hi!" + " How are you?" → "Hi! How are you?" (len=15)
```

**TTS Text Processing** (TTSTextProcessor)

```python
# Extract emotion tags: [happy], [sad], [angry], etc.
# Filter out URLs, special chars
# Normalize whitespace
```

## 3. Usage

### Start a Turn

```python
from src.services.websocket_service.message_processor import MessageProcessor

processor = MessageProcessor(
    connection_id=uuid.uuid4(),
    user_id="user123",
    queue_maxsize=100
)

# Start turn with agent stream
turn_id = await processor.start_turn(
    user_message="Hello!",
    conversation_id="conv-001",
    agent_stream=agent_service.stream_response(...)
)

# Stream events to client
async for event in processor.stream_events(turn_id):
    await websocket.send_json(event)
```

### Event Types Received

```python
# 1. Stream start
{"type": "stream_start", "turn_id": "...", "timestamp": 1234567890}

# 2. TTS chunks (multiple)
{"type": "tts_ready_chunk", "chunk": "私の名前は...", "emotion": "neutral"}
{"type": "tts_ready_chunk", "chunk": "もちろん、誰が...", "emotion": "happy"}

# 3. Stream end
{"type": "stream_end", "turn_id": "...", "timestamp": 1234567900}
```

### Interrupt Active Turn

```python
# Gracefully cancel ongoing turn
await processor.handle_interrupt(turn_id)

# Events will include:
{"type": "interrupted", "turn_id": "...", "timestamp": 1234567895}
```

---

## Appendix

### A. Troubleshooting

**Issue**: TTS chunks not reaching client

**Cause**: Race condition where stream_end sent before chunks emitted

**Solution**: Ensure `_wait_for_token_queue()` waits for consumer task completion (fixed in v2024-12-08)

---

**Issue**: Short sentences causing poor TTS quality

**Cause**: TextChunkProcessor yielding <10 char chunks like "Hi!"

**Solution**: MIN_CHUNK_LENGTH=10 merges short sentences until threshold met

---

**Issue**: Japanese text not splitting on sentence boundaries

**Cause**: Regex only matched English punctuation (`.!?`)

**Solution**: Enhanced regex with `。！？` support

### B. Configuration

**Queue Sizes**
```python
queue_maxsize=100  # Default event queue size per turn
```

**Timeouts**
```python
INTERRUPT_WAIT_TIMEOUT=1.0  # Max wait for task cancellation
```

**Text Processing**
```python
MIN_CHUNK_LENGTH=10  # Minimum TTS chunk length (chars)
```

### C. Related Documents

- `message_processor/README.md` - Module architecture
- `TextChunkProcessor.md` - Sentence splitting details
- `TTSTextProcessor.md` - Text filtering/emotion extraction
- `WebSocket_API_GUIDE.md` - Client-side event handling
