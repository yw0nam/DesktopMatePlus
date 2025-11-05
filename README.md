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
- **C# Integration Guide**: `docs/api/INDEX.md`

### Example Usage

```bash
# Test TTS API
curl -X POST http://localhost:5500/v1/tts/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello from DesktopMatePlus!", "reference_id": "ナツメ"}'

# Test VLM API
curl -X POST http://localhost:5500/v1/vlm/analyze \
  -H "Content-Type: application/json" \
  -d '{"image": "data:image/png;base64,...", "prompt": "What is in this image?"}'

# Run real-time streaming demo
uv run python examples/realtime_tts_streaming_demo.py
```

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

## API Endpoints

### HTTP REST APIs

#### Short-Term Memory (STM)
- `POST /v1/stm/chat-history` - Add messages to a session
- `GET /v1/stm/chat-history` - Retrieve conversation history
- `GET /v1/stm/sessions` - List all sessions
- `DELETE /v1/stm/sessions/{session_id}` - Delete a session
- `PATCH /v1/stm/sessions/{session_id}/metadata` - Update session metadata

#### Text-to-Speech (TTS)
- `POST /v1/tts/synthesize` - Convert text to speech (returns base64 WAV)

#### Vision Language Model (VLM)
- `POST /v1/vlm/analyze` - Analyze images with AI

#### Health Check
- `GET /health` - Backend health status

### WebSocket API

#### Real-time Chat Streaming ⭐
- `WS /v1/chat/stream` - Real-time chat with automatic TTS chunk generation

**Key Events:**
- `authorize` / `authorize_success` - Connection authentication
- `chat_message` - Send message to agent
- `stream_start` - Agent starts responding
- `tts_ready_chunk` - Sentence-level TTS chunks (ready for synthesis)
- `stream_end` - Agent finished responding
- `ping` / `pong` - Heartbeat mechanism

See `docs/api/WebSocket_ChatStream.md` for complete documentation.

## C# Integration

Complete C# integration documentation is available in `docs/api/`:

- **[INDEX.md](docs/api/INDEX.md)** - Documentation overview and quick search
- **[GettingStarted.md](docs/api/GettingStarted.md)** - 5-minute integration guide
- **[CSharp_QuickReference.md](docs/api/CSharp_QuickReference.md)** - Common patterns and examples
- **[WebSocket_ChatStream.md](docs/api/WebSocket_ChatStream.md)** - Real-time streaming details

### Quick C# Example

```csharp
// HTTP Client
var client = new DesktopMatePlusClient("http://localhost:5500");
var audio = await client.SynthesizeSpeechAsync("Hello!", "ナツメ");

// WebSocket Client
var ws = new DesktopMatePlusWebSocketClient();
ws.OnTTSReady += async (s, chunk) => await PlayAudio(chunk.Text);
await ws.ConnectAsync();
await ws.SendChatMessageAsync("Tell me a story");
```

## Real-time TTS Streaming

The WebSocket streaming gateway provides real-time TTS chunk generation:

### How It Works

1. Client sends a `chat_message`
2. Agent starts streaming tokens (internal, not sent to client)
3. Sentences are detected automatically by punctuation
4. `tts_ready_chunk` events are emitted **DURING** streaming (not after)
5. Client synthesizes and plays audio immediately
6. Natural conversation flow with no waiting

### Key Events

- `tts_ready_chunk` - Sentence-level text chunks ready for TTS synthesis
- `stream_start` / `stream_end` - Stream lifecycle
- `tool_call` / `tool_result` - Tool execution (logged server-side only)
- `error` - Error handling

**Note:** Raw `stream_token` events are processed internally. Clients should use `tts_ready_chunk` for both UI rendering and TTS playback.

### Example Flow

```text
User: "Tell me a story"
  → stream_start
  → tts_ready_chunk: "Once upon a time, there was a brave knight."
  → [Client plays audio immediately]
  → tts_ready_chunk: "He lived in a castle on a hill."
  → [Client plays audio]
  → tts_ready_chunk: "The end."
  → [Client plays audio]
  → stream_end
```

## Examples

Several example scripts are provided in the `examples/` directory:

```bash
# Real-time TTS streaming demo
uv run python examples/realtime_tts_streaming_demo.py

# Custom message with Japanese voice
uv run python examples/realtime_tts_streaming_demo.py \
  --message "君の名前は何？" \
  --reference-id "ナツメ"

# WebSocket client demo
uv run python examples/websocket_client_demo.py

# Screen capture and VLM integration
uv run python examples/screen_vlm_integration.py

# TTS synthesis demo
uv run python examples/tts_synthesis_demo.py
```

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

## Architecture Highlights

### Service Manager Pattern

All services are managed through a centralized `ServiceManager`:

```python
from src.services import get_tts_service, get_vlm_service, get_agent_service, get_stm_service, get_ltm_service

tts_service = get_tts_service()
vlm_service = get_vlm_service()
agent_service = get_agent_service()
stm_service = get_stm_service()
ltm_service = get_ltm_service()
```

### WebSocket Message Processor

The `MessageProcessor` handles real-time streaming with:
- Token buffering and sentence detection
- Automatic TTS chunk generation
- Turn-based conversation management
- Error handling and recovery

### Memory System

- **STM (MongoDB)**: Session-based conversation history
- **LTM (mem0)**: Long-term user context and preferences
- Automatic memory integration in agent responses

## Testing

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
2. **Docker Container** - Containerized deployment
3. **Executable** - PyInstaller bundled executable (future)

## Release Notes

### Version 2.0 (November 2025)
- ✅ Complete WebSocket streaming with real-time TTS chunks
- ✅ MongoDB-based STM for session management
- ✅ mem0 integration for long-term memory
- ✅ Customizable agent personas per message
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
