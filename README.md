# DesktopMatePlus Backend

AI-powered desktop companion backend with real-time streaming, vision, speech, and memory capabilities.

## Overview

This is the Python FastAPI backend for DesktopMatePlus, a 3D desktop AI companion (Yuri). The backend provides:

- **Real-time Chat Streaming**: WebSocket-based streaming with automatic TTS chunk generation
- **Vision Language Model (VLM)**: Screen understanding and image analysis using vLLM inference server
- **Text-to-Speech (TTS)**: Natural voice synthesis with voice cloning using Fish Speech
- **Cognitive Agent**: OpenAI-based agent with tool calling and streaming support
- **Memory System**: Long-term memory (LTM) using mem0 and short-term memory (STM) using MongoDB

## Architecture

The backend is built as a FastAPI-based HTTP/WebSocket server designed for C# frontend integration (Unity/WPF). It provides both RESTful APIs and real-time WebSocket streaming.

### Key Features

- **Real-time Streaming**: WebSocket-based chat with live TTS chunk generation during agent response
- **Multi-modal Support**: Text chat, image analysis (VLM), and voice synthesis (TTS)
- **Session Management**: Persistent conversation sessions with MongoDB-based STM
- **Memory System**: Long-term memory with mem0 for user context and preferences
- **Service Architecture**: Modular design with independent VLM, TTS, Agent, and Memory services
- **Customizable Personas**: Dynamic agent personality configuration per message
- **External Model Servers**: Calls external APIs (OpenAI, vLLM, Fish Speech) - no GPU inference in backend process

## Project Structure

```text
src/
├── api/                          # FastAPI routes
│   └── routes/                   # API endpoints (STM, TTS, VLM, WebSocket)
├── services/                     # Service layer
│   ├── agent_service/            # OpenAI chat agent with tools
│   ├── ltm_service/              # Long-term memory (mem0)
│   ├── stm_service/              # Short-term memory (MongoDB)
│   ├── tts_service/              # Text-to-speech (Fish Speech)
│   ├── vlm_service/              # Vision language model (vLLM)
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

Create a `.env` file with the following variables:

```bash
# OpenAI Configuration (for Agent)
OPENAI_API_KEY=your_api_key_here

# VLM Server (vLLM)
VLM_BASE_URL=http://localhost:8001/v1
VLM_MODEL_NAME=Qwen/Qwen2-VL-7B-Instruct

# TTS Server (Fish Speech)
TTS_SERVER_URL=http://localhost:8080
TTS_REFERENCE_AUDIO_DIR=./reference_audio

# MongoDB (for Short-term Memory)
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=desktopmate_stm

# mem0 Configuration (for Long-term Memory)
MEM0_API_KEY=your_mem0_api_key  # Optional, if using mem0 cloud
# Or configure local vector store
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_qdrant_key  # Optional

# Server Configuration
HOST=0.0.0.0
PORT=5500
LOG_LEVEL=INFO
LOG_RETENTION="30 days"
```

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
# Format code
bash script/lint.sh

```
#### Avatar & Background Management

The WebSocket API also supports avatar configuration and background management:

- **Fetch Backgrounds**: Request available background images
- **Fetch Avatar Configs**: Request available avatar/character configurations
- **Switch Avatar Config**: Change the active avatar configuration

See [WebSocket API Guide](docs/websocket/WEBSOCKET_API_GUIDE.md) for complete message documentation.

**Client → Server Messages:**

| Message Type | Description |
|-------------|-------------|
| `authorize` | Authenticate the connection with a token |
| `pong` | Response to server ping for heartbeat |
| `chat_message` | Send a user's message to the agent |
| `interrupt_stream` | Interrupt an active response stream |
| `fetch_backgrounds` | Request list of available backgrounds |
| `fetch_avatar_configs` | Request list of avatar configurations |
| `switch_avatar_config` | Switch to a different avatar configuration |

**Server → Client Messages:**

| Message Type | Description |
|-------------|-------------|
| `authorize_success` | Confirms successful authorization (includes `connection_id`) |
| `authorize_error` | Indicates authorization failure |
| `ping` | Heartbeat message from server |
| `stream_start` | Beginning of agent response (includes `turn_id`, `conversation_id`) |
| `stream_token` | Internal token chunk (not typically used by clients) |
| `tts_ready_chunk` | Complete sentence ready for TTS (includes `chunk`, optional `emotion`) |
| `tool_call` | Agent is calling a tool (includes `tool_name`, `args`) |
| `tool_result` | Result from tool execution |
| `stream_end` | End of agent response (includes `turn_id`, `conversation_id`, `content`) |
| `error` | Error message (includes `error`, optional `code`) |
| `background_files` | List of available background files |
| `avatar_config_files` | List of avatar configurations |
| `avatar_config_switched` | Confirmation of config switch |
| `set_model_and_conf` | Set Live2D model and configuration |

See `docs/websocket/WEBSOCKET_API_GUIDE.md` for complete documentation.

## Documentation

Complete documentation is available in `docs/`:

- **[REST_API_GUIDE.md](docs/api/REST_API_GUIDE.md)** - REST API reference
- **[WEBSOCKET_API_GUIDE.md](docs/websocket/WEBSOCKET_API_GUIDE.md)** - WebSocket API reference


## Service Dependencies

The backend requires the following external services to be running:

1. **vLLM Server** (for VLM)
   - Default: `http://localhost:8001/v1`
   - Model: `Qwen/Qwen2-VL-7B-Instruct` or similar

2. **Fish Speech Server** (for TTS)
   - Default: `http://localhost:8080`
   - Supports voice cloning with reference audio
   - Note you have to set up your own Fish Speech server before starting.

3. **MongoDB** (for STM)
   - Default: `mongodb://localhost:27017`
   - Database: `desktopmate_stm`

4. **Qdrant** (For mem0 LTM)
   - Default: `http://localhost:6333`
   - Or use mem0 cloud service


## Test Suite

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test categories
uv run pytest tests/test_websocket*.py
uv run pytest tests/test_tts*.py
uv run pytest tests/test_vlm*.py
```

## Deployment

The backend is designed to be deployed as:

1. **Standalone Service** - Run as a Python service

## Release Notes

### Version 2.1 (November 2025)

- ✅ Avatar configuration management via WebSocket
- ✅ Background image management via WebSocket
- ✅ Live2D model configuration support
- ✅ Updated documentation structure

### Version 2.0 (November 2025)

- ✅ Complete WebSocket streaming with real-time TTS chunks
- ✅ MongoDB-based STM for session management
- ✅ mem0 integration for long-term memory
- ✅ Customizable agent personas per message
- ✅ Non-blocking async memory save (no TTS blocking)
- ✅ Production-ready error handling and reconnection
- ✅ Full test coverage for all services

### Version 1.0 (October 2025)

- Initial release with basic HTTP APIs
- WebSocket streaming foundation
- VLM and TTS service integration

## Contributing

1. Create a feature branch
2. Implement with tests
3. Run code quality checks: `bash scripts/lint.sh`
4. Submit pull request

## License

MIT License
