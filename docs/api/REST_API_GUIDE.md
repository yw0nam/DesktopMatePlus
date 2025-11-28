# REST API Guide

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: RESTful API for STM, TTS, and VLM services
- **I/O**: HTTP requests → JSON responses

## 2. Core Logic

### Base URL

- **Development**: `http://127.0.0.1:5500/v1`

### Short-Term Memory (STM)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/stm/sessions` | GET | [List Sessions](./STM_ListSessions.md) |
| `/stm/chat-history` | GET | [Get Chat History](./STM_GetChatHistory.md) |
| `/stm/chat-history` | POST | [Add Chat History](./STM_AddChatHistory.md) |
| `/stm/sessions/{session_id}/metadata` | PATCH | [Update Metadata](./STM_UpdateSessionMetadata.md) |
| `/stm/sessions/{session_id}` | DELETE | [Delete Session](./STM_DeleteSession.md) |

### Text-to-Speech (TTS)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/tts/synthesize` | POST | [Synthesize Speech](./TTS_Synthesize.md) |

### Vision-Language Model (VLM)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/vlm/analyze` | POST | [Analyze Image](./VLM_Analyze.md) |

## 3. Usage

```bash
# Example: Synthesize speech
curl -X POST "http://127.0.0.1:5500/v1/tts/synthesize" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello!", "output_format": "base64"}'
```

---

## Appendix

### A. Related Documents

- [WebSocket API Guide](../websocket/WEBSOCKET_API_GUIDE.md)
- [Service Layer](../feature/service/README.md)
