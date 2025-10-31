# MessageProcessor Module

This module provides the core orchestration for conversation turns in the WebSocket service, managing async tasks, coordinating AgentService streaming events, and guaranteeing deterministic cleanup.

## Module Structure

The MessageProcessor has been modularized into several components:

### Core Files

- **`__init__.py`** - Public API exports for the module
- **`constants.py`** - Shared constants (sentinel values, timeouts)
- **`models.py`** - Data models (TurnStatus enum, ConversationTurn dataclass)
- **`processor.py`** - Main MessageProcessor class orchestrating turn lifecycle
- **`event_handlers.py`** - Event processing logic (agent stream, token events, TTS chunks)
- **`task_manager.py`** - Task tracking and cleanup utilities

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MessageProcessor                          │
│  (Orchestrates conversation turns and manages lifecycle)    │
└───────────────┬─────────────────────────┬───────────────────┘
                │                         │
        ┌───────▼──────────┐      ┌──────▼──────────┐
        │  EventHandler    │      │  TaskManager    │
        │  - Agent events  │      │  - Task tracking│
        │  - Token stream  │      │  - Cleanup      │
        │  - TTS chunks    │      │  - Cancellation │
        └──────────────────┘      └─────────────────┘
```

## Components

### MessageProcessor (processor.py)

The main orchestrator that:
- Manages conversation turn lifecycle (start, interrupt, complete, cleanup)
- Maintains turn state and metadata
- Coordinates event and token queues
- Handles async task tracking through TaskManager
- Delegates event processing to EventHandler

**Key Methods:**
- `start_turn()` - Initialize a new conversation turn
- `handle_interrupt()` - Interrupt active turn and cleanup
- `cleanup()` - Deterministic resource cleanup
- `stream_events()` - Async generator yielding turn events

### EventHandler (event_handlers.py)

Handles all event processing:
- **Agent Events**: Consumes AgentService stream and routes events
- **Token Processing**: Transforms stream_token events into TTS chunks
- **Text Processing**: Uses TextChunkProcessor and TTSTextProcessor pipelines
- **Queue Management**: Manages token queue and signals stream closure

**Key Methods:**
- `produce_agent_events()` - Consume AgentService stream
- `consume_token_events()` - Process tokens into TTS chunks
- `_process_token_event()` - Transform individual tokens
- `_flush_tts_buffer()` - Emit remaining buffered text

### TaskManager (task_manager.py)

Manages async task lifecycle:
- **Task Tracking**: Register tasks with turn and processor
- **Cleanup Callbacks**: Auto-remove completed tasks
- **Cancellation**: Cancel turn tasks with timeout
- **Queue Operations**: Token consumer creation, event queue draining

**Key Methods:**
- `track_task()` - Register task for lifecycle management
- `cancel_turn_tasks()` - Cancel all tasks for a turn
- `ensure_token_consumer()` - Create token processing task
- `drain_event_queue()` - Clear pending events

### Models (models.py)

Data structures:
- **`TurnStatus`**: Enum for turn states (PENDING, PROCESSING, COMPLETED, INTERRUPTED, FAILED)
- **`ConversationTurn`**: Dataclass containing turn state, queues, tasks, and metadata

### Constants (constants.py)

Shared configuration:
- `TOKEN_QUEUE_SENTINEL` - Sentinel object for stream closure
- `INTERRUPT_WAIT_TIMEOUT` - Timeout for interrupt operations (1.0s)

## Usage

```python
from src.services.websocket_service.message_processor import MessageProcessor

# Initialize processor
processor = MessageProcessor(
    connection_id=connection_uuid,
    user_id="user123",
    queue_maxsize=100
)

# Start a turn with agent stream
turn_id = await processor.start_turn(
    conversation_id="conv-123",
    user_input="Hello!",
    agent_stream=agent_service.stream(messages),
)

# Stream events to client
async for event in processor.stream_events(turn_id):
    await websocket.send_json(event)

# Interrupt if needed
await processor.interrupt_turn(turn_id, "User requested stop")

# Cleanup when done
await processor.cleanup(turn_id)
```

## Event Flow

```
AgentService.stream()
    │
    ▼
EventHandler.produce_agent_events()
    │
    ├─► stream_start ──────────► event_queue ──► client
    │
    ├─► stream_token ──────────► token_queue
    │                                  │
    │                                  ▼
    │                      EventHandler.consume_token_events()
    │                                  │
    │                                  ├─► TextChunkProcessor
    │                                  │
    │                                  ├─► TTSTextProcessor
    │                                  │
    │                                  ▼
    │                            tts_ready_chunk ──► event_queue ──► client
    │
    └─► stream_end ────────────► event_queue ──► client
```

## Design Principles

1. **Separation of Concerns**: Each module has a single, well-defined responsibility
2. **Async-First**: All operations are async-aware and properly handle cancellation
3. **Deterministic Cleanup**: Resources are cleaned up in predictable order
4. **Backpressure**: Uses bounded queues to prevent memory issues
5. **Type Safety**: Full type hints for better IDE support and validation

## Testing

Tests are organized to verify each component:
- `test_message_processor.py` - Core MessageProcessor functionality
- `test_message_processor_stream_pipeline.py` - Event streaming and token processing
- `test_websocket_service.py` - Integration with WebSocket manager

Run tests:
```bash
uv run pytest tests/test_message_processor*.py -v
```
