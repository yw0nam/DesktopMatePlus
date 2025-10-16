# DesktopMate+ Backend

AI-powered desktop companion backend with vision, speech, and memory capabilities.

## Overview

This is the Python backend (sidecar) for DesktopMate-Plus, a desktop application that provides an intelligent AI companion. The backend handles:

- **Vision Cognition Module (VLM)**: Screen understanding using vLLM inference server
- **Speech Generation Module (TTS)**: Natural voice synthesis using Fish Speech
- **Cognitive Engine**: LangGraph-based agent with memory management
- **Memory System**: Long-term and short-term memory using mem0 and LangGraph checkpointers

## Architecture

The backend is built as a FastAPI-based lightweight HTTP server that will be packaged as a standalone executable using PyInstaller. It communicates with the Tauri-based frontend via HTTP API.

### Key Design Principles

- **Independence**: Backend can run and be tested independently of the frontend
- **Stateful API**: Uses LangGraph's built-in memory and Checkpointer for conversation state management
- **Simplicity First**: Avoiding unnecessary complexity with clear separation of concerns
- **Service Independence**: VLM, TTS, and agent are loosely coupled for easy testing/replacement
- **Testability**: Designed with mockable interfaces for unit/integration testing
- **External Model Servers**: Only calls external APIs (OpenAI, local vLLM, Fish Speech) - no GPU inference inside the backend process

## Project Structure

```
src/
├── api/              # FastAPI endpoints
├── agents/           # LangGraph agent definitions
├── tools/            # Agent tools (memory, vision, speech)
│   └── memory/       # Memory management tools
├── services/         # External service clients (VLM, TTS)
├── configs/          # Configuration management
└── models/           # Pydantic models and schemas
```

## Setup

### Prerequisites

- Python 3.13+
- uv package manager
- External services: vLLM server, Fish Speech server

### Installation

```bash
# Install dependencies
uv sync

# Install development dependencies
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install
```

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# LLM Configuration
OPENAI_API_KEY=your_api_key_here

# VLM Server
VLM_BASE_URL=http://localhost:8001
VLM_MODEL_NAME=your_vlm_model

# TTS Server
TTS_BASE_URL=http://localhost:8002

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=desktopmate
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password

# Qdrant Vector Store
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_qdrant_key
```

## Running

```bash
# Start the backend server
uv run uvicorn src.api.main:app --reload

# Or with specific host/port
uv run uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
```

The API documentation will be available at: `http://127.0.0.1:8000/docs`

## Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/test_memory.py
```

## Code Quality

```bash
# Format code
uv run black src/

# Lint code
uv run ruff check src/ --fix

# Type check
uv run mypy src/
```

## API Endpoints

### POST /v1/chat
Process user messages and return AI companion responses with audio.

### POST /v1/voice
Upload voice sample for zero-shot voice cloning.

### GET /health
Health check for backend and all AI modules.

## Development Workflow

1. Create/update tasks in Task Master
2. Implement feature with proper tests
3. Run code quality checks (black, ruff, mypy)
4. Commit with pre-commit hooks
5. Update task status

## Packaging

The final backend will be packaged as a single executable using PyInstaller, including all dependencies and model weights.

## License

[Your License Here]
