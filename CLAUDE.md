# DesktopMate+ Backend Development Guidelines

This document outlines the fundamental rules, architectural patterns, and conventions for the **DesktopMate+ Backend** repository.
You must adhere to these guidelines for all code generation and refactoring tasks.

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
  - `stm_service/`: Short-Term Memory services.
  - `ltm_service/`: Long-Term Memory (Mem0/Qdrant) services.
  - `tts_service/`: Text-to-Speech services.
  - `websocket_service/`: WebSocket communication services.
  - `knowledge_base_service/`: Knowledge base (RAG) services.
  - `task_sweep_service/`: Background expired task cleanup.
- `src/main.py`: Application entry point and lifespan management.
- `yaml_files/`: Service configuration files.
  - `personas.yml`: Persona definitions (system prompts keyed by `persona_id`).
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

### E. Agent Architecture Patterns

- **Single instance:** `OpenAIChatAgent` is created once; `initialize_async()` is called in lifespan after all sync inits. It fetches MCP tools and creates the agent. `is_healthy()` returns `False` until then (swallowed via `swallow_health_error=True`).
- **Persona injection:** `ChatMessage.persona_id` (default `"yuri"`) maps to a key in `yaml_files/personas.yml`. Persona text is prepended as `SystemMessage` at `stream()` time — not stored in the model field.
- **DelegateToolMiddleware:** Injects `DelegateTaskTool` per request via `AgentMiddleware.awrap_model_call()`. Session ID is read from `RunnableConfig.configurable` via `get_config()` — do not pass it as a constructor arg.
- **STM as sole history source:** No checkpointer. `handlers.py` fetches history from STM each turn and passes it as `messages` to `stream()`.

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
