# WEBSOCKET SERVICE

## OVERVIEW

Real-time streaming gateway: WebSocket connections → agent responses → TTS chunks → client events.

## STRUCTURE

```
websocket_service/
├── __init__.py               # Re-exports WebSocketManager
├── error_classifier.py       # Classifies errors as recoverable/fatal
├── text_processors.py        # Token text cleaning (emoji strip, whitespace normalize)
├── manager/
│   ├── websocket_manager.py  # Connection lifecycle (455 lines) — auth, heartbeat, routing
│   └── handlers.py           # Message type handlers (393 lines) — chat turn orchestration
└── message_processor/
    ├── processor.py           # Turn processor (626 lines) — task lifecycle, event queues
    ├── event_handlers.py      # Event pipeline (448 lines) — agent events → TTS chunks
    ├── models.py              # Internal event models
    ├── tts_text_processor.py  # Text → TTS-ready chunks
    ├── text_chunk_processor.py # Token accumulation → sentence boundaries
    └── dependencies.py        # DI for processor creation
```

## DATA FLOW

```
Client WS message
  → websocket_manager.handle_message()
    → handlers.handle_chat_message()
      → MessageProcessor.start_turn()
        → agent_service.stream()
          → event_handlers.produce_agent_events()
            → TTS synthesis per sentence chunk
              → stream_token + tts_chunk events → Client
        → stream_end event → Client
```

## WHERE TO LOOK

| Task | File |
|------|------|
| Connection auth/heartbeat | `manager/websocket_manager.py` |
| New message type handler | `manager/handlers.py` |
| Agent event processing | `message_processor/event_handlers.py` |
| TTS chunk generation | `message_processor/tts_text_processor.py` |
| Sentence boundary logic | `message_processor/text_chunk_processor.py` |
| Turn lifecycle/interrupts | `message_processor/processor.py` |
| Error recovery | `error_classifier.py` |

## CONVENTIONS

- **Concurrent turn protection**: One chat turn per connection (code 4002 on violation).
- **Interrupt support**: `interrupt_stream` cancels active turn, sends partial results.
- **TTS barrier**: Per-chunk inactivity timeout (rolling, configurable in YAML).
- **Error classification**: `error_classifier.py` decides recoverable vs fatal → auto-close on fatal.

## ANTI-PATTERNS

- **Never** send events after `stream_end` — client expects clean termination.
- **Never** skip cleanup in `processor.py` — leaked tasks cause zombie connections.
- **Never** bypass `error_classifier` for error handling — inconsistent close codes.
