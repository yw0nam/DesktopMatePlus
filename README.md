# DesktopMatePlus Backend

AI-powered desktop companion backend with real-time streaming, vision, speech, and memory capabilities.

## Overview

This is the Python FastAPI backend for DesktopMatePlus, a 3D desktop AI companion (Yuri). The backend provides:

- **Real-time Chat Streaming**: WebSocket-based streaming with automatic TTS chunk generation
- **Text-to-Speech (TTS)**: Natural voice synthesis with voice cloning using Fish Speech / vLLM Omni
- **Cognitive Agent**: OpenAI-based agent with tool calling, streaming, and image support
- **Memory System**: Long-term memory (LTM) using mem0 and short-term memory (STM) using MongoDB
- **Task Delegation**: Background task delegation to NanoClaw with automatic expired task cleanup

## Architecture

The backend is built as a FastAPI-based HTTP/WebSocket server designed for C# frontend integration (Unity/WPF). It provides both RESTful APIs and real-time WebSocket streaming.

### Key Features

- **Real-time Streaming**: WebSocket-based chat with live TTS chunk generation during agent response
- **Multi-modal Support**: Text chat, image analysis (via Agent), and voice synthesis (TTS)
- **Session Management**: Persistent conversation sessions with MongoDB-based STM
- **Memory System**: Long-term memory with mem0 for user context and preferences
- **Service Architecture**: Modular design with independent TTS, Agent, and Memory services
- **Task Delegation & Sweep**: Delegate tasks to NanoClaw; background sweep auto-fails expired tasks
- **Customizable Personas**: Dynamic agent personality configuration per message
- **External Model Servers**: Calls external APIs (OpenAI, vLLM, Fish Speech) - no GPU inference in backend process

## Project Structure

```text
src/
├── api/                          # FastAPI routes
│   └── routes/                   # API endpoints (STM, TTS, WebSocket)
├── services/                     # Service layer
│   ├── agent_service/            # OpenAI chat agent with tools
│   ├── ltm_service/              # Long-term memory (mem0)
│   ├── stm_service/              # Short-term memory (MongoDB)
│   ├── tts_service/              # Text-to-speech (Fish Speech, vLLM Omni)
│   ├── vlm_service/              # Vision language model (deprecated)
│   ├── task_sweep_service/       # Background expired task cleanup
│   ├── websocket_service/        # WebSocket streaming gateway
│   │   └── message_processor/    # Token processing and TTS chunk generation
│   └── screen_capture_service/   # Screen capture utilities
├── configs/                      # Configuration management
├── models/                       # Pydantic models and schemas
├── core/                         # Core utilities (logging, etc.)
└── main.py                       # Application entry point

examples/                         # Example scripts
├── realtime_tts_streaming_demo.py
├── websocket_client_demo.py
└── ...

tests/                            # Comprehensive test suite
```

## Setup

### Prerequisites

- Python 3.13+
- uv package manager
- External services (MongoDB, Qdrant, vLLM) — see [Dependencies Guide](docs/setup/DEPENDENCIES.md)

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

Create a `.env` file with essential configuration:

```bash
# Agent LLM
OPENAI_API_KEY=your_api_key_here

# Memory
MONGODB_URI=mongodb://localhost:27017
QDRANT_URL=http://localhost:6333

# Optional: TTS, Server config, etc.
```

For complete environment variable documentation, see [Environment Setup Guide](docs/setup/ENVIRONMENT.md).

## Running

### Start the Backend Server

```bash
# Start with default settings (port 5500)
uv run python src/main.py

# Or with custom port
uv run python src/main.py --port 8000

# With uvicorn directly
uv run uvicorn src.main:app --host 0.0.0.0 --port 5500 --reload
```

The server will start on `http://localhost:5500` by default.

### API Documentation

- **Swagger UI**: `http://localhost:5500/docs`
- **ReDoc**: `http://localhost:5500/redoc`
- **Frontend Integration Guide**: `docs/api/REST_API_GUIDE.md`

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
# Format code with ruff
bash scripts/lint.sh
```

## Documentation

### Setup & Configuration
- [Environment Variables](docs/setup/ENVIRONMENT.md) - Complete .env configuration
- [External Dependencies](docs/setup/DEPENDENCIES.md) - MongoDB, Qdrant, vLLM, Fish Speech setup
- [Configuration System](docs/feature/config/README.md) - YAML config management

### API Reference
- [REST API Guide](docs/api/REST_API_GUIDE.md) - HTTP endpoints
- [WebSocket API Guide](docs/websocket/WEBSOCKET_API_GUIDE.md) - Real-time streaming

### Service Architecture
- [Service Layer](docs/feature/service/README.md) - Service overview
- [Agent Service](docs/feature/service/Agent_Service.md)
- [Memory Services](docs/feature/service/STM_Service.md) (STM/LTM)
- [TTS Service](docs/feature/service/TTS_Service.md)

### Release History
- [CHANGELOG.md](CHANGELOG.md) - Version history
- [Patch Notes](docs/patch/) - Detailed technical changes

## Contributing

1. Create a feature branch
2. Implement with tests
3. Run code quality checks: `bash scripts/lint.sh`
4. Submit pull request

## License

MIT License
