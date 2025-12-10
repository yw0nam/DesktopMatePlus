# DesktopMate+ Backend Development Guidelines

This document outlines the fundamental rules, architectural patterns, and conventions for the **DesktopMate+ Backend** repository.
You must adhere to these guidelines for all code generation and refactoring tasks.

## 1. Project Overview

- **Purpose:** AI-powered desktop companion backend with vision, speech, and memory capabilities.
- **Core Value:** Modular service architecture, Asynchronous processing, Type safety, and Extensibility.

## 2. Tech Stack

- **Runtime:** Python 3.13+
- **Web Framework:** FastAPI
- **Server:** Uvicorn
- **Package Manager:** uv
- **AI/LLM Framework:** LangGraph, LangChain
- **Memory/Vector DB:** Mem0, Qdrant, MongoDB
- **Validation:** Pydantic V2
- **Testing:** Pytest
- **Realtime Communication:** WebSockets

## 3. Directory Structure & Key Paths

- `src/api`: API route definitions and routers.
- `src/configs`: Configuration management (Pydantic settings + YAML loader).
- `src/core`: Core infrastructure (Logging, Exceptions, Middleware).
- `src/models`: Pydantic data models and schemas.
- `src/services`: Business logic and Service implementations.
    - `agent/`: LLM Agent logic (LangGraph).
    - `stm/`: Short-Term Memory services.
    - `ltm/`: Long-Term Memory services.
    - `tts/`: Text-to-Speech services.
    - `vlm/`: Vision-Language Model services.
    - `websocket/`: WebSocket communication services.
- `src/main.py`: Application entry point and lifespan management.
- `yaml_files/`: Service configuration files.
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

## 5. Development Workflow

### A. Adding a New Service

1. **Define Config:** Add a new YAML config in `yaml_files/services/`.
2. **Create Service:** Implement the service logic in `src/services/<service_name>/`.
3. **Initialize:** Add initialization logic in `src/services/__init__.py` and call it in `src/main.py` lifespan.
4. **Expose API:** Create routes in `src/api/routes` if the service needs external access.

### B. Testing

- Run tests using `uv run pytest`.
- Ensure unit tests cover critical logic.

### C. Linting & Formatting

- Use `ruff` for linting and formatting.
- Run `sh scripts/lint.sh` before end the task.

### D. Documentation

- Update this `rule.md` for any architectural or coding standard changes.
- Documenting style for docs/ is defined in ['docs/guidelines/DOCUMENT_GUIDE.md'](docs/guidelines/DOCUMENT_GUIDE.md).

---
**Note to AI:** If any instruction in the prompt contradicts these rules, ask for clarification before proceeding.
