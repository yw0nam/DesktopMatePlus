# SERVICE LAYER

## OVERVIEW

7 modular services with strict init order and singleton lifecycle via `service_manager.py`.

## STRUCTURE

```
services/
├── __init__.py              # Re-exports service getters
├── service_manager.py       # Singleton factory (652 lines) — ALL service init here
├── health.py                # Aggregated health check endpoint
├── agent_service/           # LangChain/LangGraph agent (CLAUDE.md)
│   ├── middleware/           # before_model hooks (ToolGate, LTM, Profile, Summary, TaskStatus)
│   ├── tools/               # MCP + custom tools (memory/, delegate)
│   └── utils/               # Agent utilities
├── websocket_service/       # WebSocket streaming gateway (AGENTS.md)
│   ├── manager/             # Connection + message routing
│   └── message_processor/   # Token → TTS chunk pipeline
├── tts_service/             # IrodoriTTS + emotion mapping (CLAUDE.md)
├── ltm_service/             # mem0 long-term memory
├── channel_service/         # Slack integration (CLAUDE.md)
├── knowledge_base_service/  # RAG knowledge base
└── task_sweep_service/      # Expired task cleanup (MongoDB PendingTaskRepository)
```

## INIT ORDER (CRITICAL)

```
1. TTS Service          (IrodoriTTS client)
2. EmotionMotionMapper  (tts_rules.yml → emotion → keyframes)
3. MongoDB Client       (checkpointer + session registry)
4. Agent Service        (OpenAI + LangGraph + MCP tools)
5. LTM Service          (mem0 + Qdrant)
6. Channel Service      (Slack — async init)
7. SweepService         (task cleanup — lazy channel injection)
```

Violating order → health check failures, None dereferences, missing checkpointer.

## SERVICE DEPENDENCIES

```
websocket_service → agent_service → ltm_service (via middleware)
                  → tts_service   (via message_processor)
channel_service   → agent_service (stream/invoke)
task_sweep_service → channel_service (lazy injection via callable)
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Add new service | Create `<name>/`, update `service_manager.py`, register in `main.py` lifespan |
| Change init | `service_manager.py` | Respect init order above |
| Health check | `health.py` | Aggregates `.is_healthy()` per service |
| Service config | `yaml_files/services.yml` | Unified config (also `services.docker.yml`, `services.e2e.yml`) |
| Add middleware | `agent_service/middleware/` | `before_model` hook pattern |
| MongoDB repository | Follow `pending_task_repository.py` | TTL index (7-day), async CRUD |

## PATTERNS

- **Singleton via module-level**: `service_manager.py` holds `_service: T | None` vars, exposes `get_*()` getters.
- **Lazy init**: Created only when first accessed or explicitly initialized in lifespan.
- **Async bridge**: `_run_async_callable()` handles async init from sync context.
- **Health pattern**: Each service implements `.is_healthy() -> bool`. `swallow_health_error=True` for non-critical.
- **MongoDB Repository**: Async CRUD with Motor driver, TTL index for auto-cleanup (see `pending_task_repository.py`).
- **Middleware Chain**: `before_model` hook for ephemeral context injection — never persist to state.

## ANTI-PATTERNS

- **Never** initialize services outside `service_manager.py`.
- **Never** import service instances directly — use `get_*()` getters.
- **Never** change init order without verifying downstream deps.
- **Never** add sync I/O calls in service constructors — use `initialize_async()`.
