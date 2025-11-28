# Service Layer

## 1. Synopsis

- **Purpose**: Provide modular business logic for AI capabilities (Agent, TTS, VLM, Memory)
- **I/O**: YAML configs → Service instances via Factory pattern → API responses

## 2. Core Logic

### Architecture Pattern

| Component | Role |
|-----------|------|
| `service.py` | Abstract base class defining interface |
| `*_factory.py` | Factory for creating service instances |
| `service_manager.py` | Centralized initialization & singletons |

### Available Services

| Service | Purpose | Implementation |
|---------|---------|----------------|
| Agent | LLM with tools & streaming | `OpenAIChatAgent` |
| TTS | Text-to-Speech synthesis | `FishSpeechTTS` |
| VLM | Vision-Language Model | `OpenAICompatibleVLM` |
| STM | Short-Term Memory (sessions) | `MongoDBSTM` |
| LTM | Long-Term Memory (semantic) | `Mem0LTM` |
| WebSocket | Real-time streaming | `WebSocketManager` |
| ScreenCapture | Cross-platform capture | `ScreenCaptureService` |
| Health | Service health checks | `HealthService` |

### Service Initialization Flow

```python
# 1. Import initializers
from src.services import (
    initialize_agent_service,
    initialize_tts_service,
    initialize_vlm_service,
    initialize_stm_service,
    initialize_ltm_service,
)

# 2. Initialize (reads YAML config automatically)
agent = initialize_agent_service()
tts = initialize_tts_service()
vlm = initialize_vlm_service()

# 3. Get service anywhere (singleton)
from src.services import get_agent_service, get_tts_service
agent = get_agent_service()
tts = get_tts_service()
```

### Factory Pattern

Each service uses a factory for flexible instantiation:

```python
# Factory creates correct implementation based on config type
tts_engine = TTSFactory.get_tts_engine("fish_local_tts", **configs)
vlm_engine = VLMFactory.get_vlm_service("openai_compatible", **configs)
agent_engine = AgentFactory.get_agent_service("openai_chat_agent", **configs)
```

### Common Service Interface

All services implement:

| Method | Description |
|--------|-------------|
| `initialize_*()` | Initialize underlying client/model |
| `is_healthy()` | Return `(bool, str)` health status |

## 3. Usage

### TTS Service

```python
tts = get_tts_service()
audio_bytes = tts.generate_speech(
    text="Hello, world!",
    reference_id="voice_001",
    output_format="bytes"
)
```

### VLM Service

```python
vlm = get_vlm_service()
response = vlm.generate_response(
    image=image_bytes,
    prompt="What is in this image?"
)
```

### Agent Service (Streaming)

```python
agent = get_agent_service()
async for event in agent.stream(messages, conversation_id="conv_001"):
    if event["type"] == "stream_token":
        print(event["chunk"], end="")
    elif event["type"] == "stream_end":
        print("\nDone:", event["content"])
```

---

## Appendix

### A. Service Documentation

For detailed service specifications, refer to:

- [Agent Service](./Agent_Service.md)
- [TTS Service](./TTS_Service.md)
- [VLM Service](./VLM_Service.md)
- [STM Service](./STM_Service.md)
- [LTM Service](./LTM_Service.md)
- [WebSocket Service](./WebSocket_Service.md)

### B. File Structure

```text
src/services/
├── service_manager.py       # Centralized initialization
├── health.py                # Health check service
├── agent_service/           # AI Agent
├── tts_service/             # Text-to-Speech
├── vlm_service/             # Vision-Language Model
├── stm_service/             # Short-Term Memory
├── ltm_service/             # Long-Term Memory
├── websocket_service/       # Real-time streaming
└── screen_capture_service/  # Screen capture
```

### C. Related Documents

- [Configuration System](../config/README.md)
- [API Guide](../../API_GUIDE.md)
- [WebSocket API Guide](../../websocket/WEBSOCKET_API_GUIDE.md)
