# REST API Guide

Updated: 2026-03-26

## 1. Synopsis

- **Purpose**: RESTful API for STM, LTM, and TTS services
- **I/O**: HTTP requests → JSON responses

## 2. Core Logic

### Base URL

- **Development**: `http://127.0.0.1:5500/v1`

### Short-Term Memory (STM) / Checkpointer

> **Note:** STM routes are now backed by the LangGraph `MongoDBSaver` checkpointer + `SessionRegistry`. There is no longer a separate `STMService`; history is persisted automatically by the agent.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/stm/sessions` | GET | [List Sessions](./STM_ListSessions.md) |
| `/stm/get-chat-history` | GET | [Get Chat History](./STM_GetChatHistory.md) |
| `/stm/add-chat-history` | POST | [Add Chat History](./STM_AddChatHistory.md) |
| `/stm/sessions/{session_id}/metadata` | PATCH | [Update Metadata](./STM_UpdateSessionMetadata.md) |
| `/stm/sessions/{session_id}` | DELETE | [Delete Session](./STM_DeleteSession.md) |
| `/stm/{session_id}/messages` | GET | Fetch all messages (NanoClaw Option B fetch endpoint) |

### Long-Term Memory (LTM)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ltm/add_memory` | POST | [Add Memory](./LTM_AddMemory.md) |
| `/ltm/search_memory` | POST | [Search Memory](./LTM_SearchMemory.md) |
| `/ltm/delete_memory` | DELETE | [Delete Memory](./LTM_DeleteMemory.md) |

### Text-to-Speech (TTS)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/tts/voices` | GET | List available TTS voices |

### Channels

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/channels/slack/events` | POST | [Slack Events Webhook](./Slack_Events.md) |
| `/callback/nanoclaw/{session_id}` | POST | [NanoClaw Task Callback](./Nanoclaw_Callback.md) |

## 3. Usage

```bash
# Example: List available voices
curl "http://127.0.0.1:5500/v1/tts/voices"
# Response: {"voices": ["aria", "alice", "bob"]}
# Returns 503 if TTS service is not initialized
```

## 4. Non-Obvious Patterns

- **No auth on REST endpoints** — `/v1/stm/`, `/v1/ltm/`, `/v1/tts/`, `/v1/callback/` are internal-only (bound to `127.0.0.1`). Do not expose externally or add auth middleware.
- **503 = service not initialized** — All endpoints return `503` when their backing service hasn't completed lifespan init. Not a network error; wait for startup.
- **Slack `/events` is the exception** — Uses HMAC-SHA256 signature verification via `x-slack-signature` + `x-slack-request-timestamp` headers. See `src/services/channel_service/slack_service.py`.

---

## Appendix

### A. Related Documents

- [WebSocket API Guide](../websocket/CLAUDE.md)
- [Service Layer](../feature/service/README.md)
