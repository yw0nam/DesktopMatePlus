# DesktopMate+ Backend Development Guidelines

This document outlines the fundamental rules, architectural patterns, and conventions for the **DesktopMate+ Backend** repository.
You must adhere to these guidelines for all code generation and refactoring tasks.

Keep this document lean but contain all critical information for capturing the architectural vision and coding standards of the project.

- If there is too much detail, split to seperate files in `docs/guidelines/` (e.g., `TESTING_GUIDE.md`, `DOCUMENT_GUIDE.md`, `LOGGING_GUIDE.md`) and reference them here.
- But, this document must contain the information for capturing the overall architecture, design patterns, and coding conventions that are critical for maintaining consistency across the codebase.

## Core Philosophy

- Question every requirement. Is it really necessary? Is there a simpler way?
- Eliminate as much as possible.
- Simplify and optimize.
- Speed ​​up and shorten cycle times.
- Automate.

## 1. Project Overview

- **Purpose:** AI-powered desktop companion backend with speech, memory, and task delegation capabilities.
- **Core Value:** Modular service architecture, Asynchronous processing, Type safety, and Extensibility.

## 2. Tech Stack

- **Runtime:** Python 3.13+
- **Web Framework:** FastAPI
- **Server:** Uvicorn
- **Package Manager:** uv
- **AI/LLM Framework:** LangChain (`langchain.agents.create_agent`), LangGraph
- **Memory/Vector DB:** Mem0, Qdrant, MongoDB
- **Validation:** Pydantic V2
- **Testing:** Pytest
- **Realtime Communication:** WebSockets

## 3. Directory Structure & Key Paths

- `docs/`: Documentation and guidelines for development, architecture, and coding standards, and code overview.
- `src/api`: API route definitions and routers.
- `src/configs`: Configuration management (Pydantic settings + YAML loader).
- `src/core`: Core infrastructure (Logging, Exceptions, Middleware).
- `src/models`: Pydantic data models and schemas.
- `src/services`: Business logic and Service implementations.
  - `agent_service/`: LLM Agent logic (`create_agent`, single instance). Supports text + image (OpenAI-compatible).
  - `stm_service/`: Short-Term Memory services (MongoDB).
  - `ltm_service/`: Long-Term Memory (Mem0/Qdrant) services.
  - `tts_service/`: Text-to-Speech services.
    - `tts_pipeline.py`: `synthesize_chunk()` — emotion → keyframes + WAV audio synthesis.
    - `emotion_motion_mapper.py`: `EmotionMotionMapper` — maps emotion string → `list[TimelineKeyframe]`.
  - `websocket_service/`: WebSocket communication services.
    - `manager/memory_orchestrator.py`: STM/LTM I/O — `load_context()` and `save_turn()`.
  - `knowledge_base_service/`: Knowledge base (RAG) services.
  - `task_sweep_service/`: Background expired task cleanup.
  - `channel_service/`: External channel integrations (Slack 등).
    - `__init__.py`: `init_channel_service()`, `get_slack_service()`, `process_message()` — 공통 진입점.
    - `slack_service.py`: `SlackService` (서명 검증, 이벤트 파싱, 메시지 전송), `SlackSettings`, `SlackMessage`.
    - `session_lock.py`: TTLCache 기반 `session_lock()` — 채널 세션 concurrency control.
- `src/main.py`: Application entry point and lifespan management.
- `yaml_files/`: Service configuration files.
  - `personas.yml`: Persona definitions (system prompts keyed by `persona_id`).
  - `tts_rules.yml`: TTS text chunking rules, emotion keywords, and `emotion_motion_map` (emotion → keyframes).
- `tests/`: Unit and integration tests.

## 4. Coding Conventions

### A. General Principles

- **Type Hinting:** Use strict type hints for all functions and variables. Use `|` for unions (Python 3.10+ style).
- **Asynchronous First:** Prefer `async/await` for all I/O operations (DB, API calls).
- **Dependency Injection:** Use FastAPI's `Depends` for route dependencies.
- **Configuration:** Do not hardcode settings. Use the central `settings` object or YAML config injection.

### B. Naming Conventions

- **Files/Modules:** `snake_case.py`
- **Classes:** `PascalCase`
- **Variables/Functions:** `snake_case`
- **Constants:** `UPPER_CASE`

### C. Error Handling

- Use custom exception classes where possible.
- Let FastAPI's exception handlers manage HTTP error responses.
- Log errors using the `src/core/logger` module (Loguru wrapped). See ['docs/guidelines/LOGGING_GUIDE.md'](docs/guidelines/LOGGING_GUIDE.md) for details.

### D. WebSocket Communication

- **Definition:** WebSocket endpoints should be defined within `src/api/routes` or a dedicated `src/api/websockets` module.
- **Protocol:** Clearly define message formats for both incoming and outgoing WebSocket communication (e.g., JSON payloads with a `type` field).
- **Error Handling:** Implement robust error handling for WebSocket connections, including disconnects and invalid message formats.
- **State Management:** Carefully manage state for connected clients.

### E. TTS & Keyframes Patterns

- **`EmotionMotionMapper`** is a standalone service initialized in lifespan via `initialize_emotion_motion_mapper()`. It reads `emotion_motion_map` from `yaml_files/tts_rules.yml` and maps emotion strings → `list[TimelineKeyframe]`.
- **`TimelineKeyframe` type:** `dict[str, float | dict[str, float]]` — e.g., `{"duration": 0.3, "targets": {"happy": 1.0}}`. Replaces the old `motion_name`/`blendshape_name` fields.
- **`synthesize_chunk()`** in `tts_pipeline.py`: always returns a `TtsChunkMessage` (never raises). If TTS fails or is disabled, `audio_base64=None`; `keyframes` is always populated from the mapper.
- **Audio format:** TTS service is called with `audio_format="wav"`. Encoded as base64 in `TtsChunkMessage.audio_base64`.
- **Service init order in lifespan:** TTS → EmotionMotionMapper → STM → Agent → LTM → Channel → Sweep.

### F. Channel Service Patterns

- **`process_message()` 공통 진입점:** Webhook 라우트(text 있음)와 Callback 핸들러(text="") 양쪽에서 호출. `text=""`이면 STM에 TaskResult가 이미 주입된 상태이므로 `HumanMessage` 추가하지 않음.
- **`session_lock`:** `cachetools.TTLCache` 기반, 10분 TTL, maxsize 1024. 동일 세션의 동시 처리 방지.
- **`reply_channel` 메타데이터:** `process_message()`가 STM session metadata에 `{"provider": "slack", "channel_id": "..."}` 형태로 저장. `callback.py`는 이 값을 읽어 Slack 라우팅 결정.
- **`SlackService` 서명 검증:** HMAC-SHA256, 5분 타임스탬프 tolerance, `hmac.compare_digest` 사용.
- **session_id 형식:** `"slack:{team_id}:{channel_id}:{user_id}"` (현재 user_id는 `"default"` 상수).
- **`upsert_session`:** filter는 `session_id`만 사용, `user_id`/`agent_id`는 `$set`으로 업데이트. `add_chat_history`와 달리 메시지 미삽입.
- **`BackgroundSweepService`:** `slack_service_fn: Callable[[], SlackService | None]` lazy 주입으로 초기화 순서 의존 없음.

### G. Agent Architecture Patterns

- **Single instance:** `OpenAIChatAgent` is created once; `initialize_async()` is called in lifespan after all sync inits. It fetches MCP tools and creates the agent. `is_healthy()` returns `False` until then (swallowed via `swallow_health_error=True`).
- **Persona injection:** `ChatMessage.persona_id` (default `"yuri"`) maps to a key in `yaml_files/personas.yml`. Persona text is prepended as `SystemMessage` at `stream()` time — not stored in the model field.
- **DelegateToolMiddleware:** Injects `DelegateTaskTool` per request via `AgentMiddleware.awrap_model_call()`. Session ID is read from `RunnableConfig.configurable` via `get_config()` — do not pass it as a constructor arg.
- **AgentService is a pure inference engine:** No STM/LTM dependency. `stream()` yields a `stream_end` event with `new_chats: list[BaseMessage]` — the messages generated this turn — for the caller to persist.
- **Memory I/O via `memory_orchestrator`:** `handlers.py` calls `memory_orchestrator.load_context()` (LTM prefix + STM history) before each turn. After `stream_end`, `event_handlers.py` fires `asyncio.create_task(save_turn(...))` as a background task. `stm_service`/`ltm_service` are passed via `turn.metadata` — not injected into AgentService.

## 5. Development Workflow

### A. Adding a New Service

1. **Define Config:** Add a new YAML config in `yaml_files/services/`.
2. **Create Service:** Implement the service logic in `src/services/<service_name>/`.
3. **Initialize:** Add initialization logic in `src/services/__init__.py` and call it in `src/main.py` lifespan.
4. **Expose API:** Create routes in `src/api/routes` if the service needs external access.

### B. Dev Server

```bash
uvicorn src.main:app --port 5500 --reload
```

### C. Testing

- Run tests using `uv run pytest`.
- Ensure unit tests cover critical logic.
- See the guidelines in ['docs/guidelines/TESTING_GUIDE.md'](docs/guidelines/TESTING_GUIDE.md) for best practices.
- Update `examples/realtime_tts_streaming_demo.py` for any api or websocket interface changes. It is for actual integration test, not a mock.

### D. Linting & Formatting

- Use `ruff` for linting and formatting.
- Run `sh scripts/lint.sh` before end the task.

### E. Documentation

- Documenting style for docs/ is defined in ['docs/guidelines/DOCUMENT_GUIDE.md'](docs/guidelines/DOCUMENT_GUIDE.md).
