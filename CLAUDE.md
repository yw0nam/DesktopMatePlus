# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Updated: 2026-03-25

This document outlines the fundamental rules, architectural patterns, and conventions for the **DesktopMate+ Backend** repository.
You must adhere to these guidelines for all code generation and refactoring tasks.

Keep this document lean but contain all critical information for capturing the architectural vision and coding standards of the project.

- If there is too much detail, split into subdirectory `CLAUDE.md` files (e.g., `src/CLAUDE.md`, `tests/CLAUDE.md`, `docs/CLAUDE.md`) — Claude Code auto-loads these context-sensitively when entering that directory.
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
    - `__init__.py`: `init_channel_service()` (**async**), `get_slack_service()`, `process_message()` — 공통 진입점.
    - `slack_service.py`: `SlackService` (서명 검증, 이벤트 파싱, 메시지 전송), `SlackSettings` (`bot_name` 포함), `SlackMessage`.
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
- Log errors using the `src/core/logger` module (Loguru wrapped). See `.claude/rules/LOGGING_GUIDE.md` for details.

### D. WebSocket Communication

- **Definition:** WebSocket endpoints should be defined within `src/api/routes` or a dedicated `src/api/websockets` module.
- **Protocol:** Clearly define message formats for both incoming and outgoing WebSocket communication (e.g., JSON payloads with a `type` field).
- **Error Handling:** Implement robust error handling for WebSocket connections, including disconnects and invalid message formats.
- **State Management:** Carefully manage state for connected clients.

### E. Service-Specific Patterns

Service implementation details live in context-sensitive subdirectory files (auto-loaded when working in that service):

- [TTS & Keyframes](src/services/tts_service/CLAUDE.md)
- [Channel Service (Slack)](src/services/channel_service/CLAUDE.md)
- [Agent Architecture](src/services/agent_service/CLAUDE.md)

## 5. Development Workflow

### A. Adding a New Service

1. **Define Config:** Add a new YAML config in `yaml_files/services/`.
2. **Create Service:** Implement the service logic in `src/services/<service_name>/`.
3. **Initialize:** Add initialization logic in `src/services/__init__.py` and call it in `src/main.py` lifespan.
4. **Expose API:** Create routes in `src/api/routes` if the service needs external access.

### B. Setup

```bash
uv sync --all-extras        # install all dependencies
uv run pre-commit install   # install pre-commit hooks
```

### C. Dev Server

```bash
uv run uvicorn src.main:app --port 5500 --reload

# For use slack, you need to run `ngrok http 5500`
# Override YAML config: YAML_FILE=yaml_files/custom.yml uv run uvicorn ...
```

### D. Testing

```bash
uv run pytest                                              # all tests
uv run pytest tests/path/test_file.py                     # specific file
uv run pytest tests/path/test_file.py::TestClass::test_name  # single test
uv run pytest -m slow                                     # E2E tests (requires real services)
uv run pytest --cov=src                                   # with coverage
```

- `asyncio_mode = "auto"` in `pyproject.toml` — no `@pytest.mark.asyncio` decorator needed.
- `slow` tests hit real MongoDB/Qdrant/LLM — skip in CI unless services are available.
- Update `examples/realtime_tts_streaming_demo.py` for any API or WebSocket interface changes.

### E. Linting & Formatting

```bash
sh scripts/lint.sh   # ruff lint + format check — run before ending any task
```
