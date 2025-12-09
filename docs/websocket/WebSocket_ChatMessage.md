# WebSocket: Chat Message

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Send user message to agent for processing
- **I/O**: Client sends message → Server streams response (tokens, tool calls, TTS)

## 2. Core Logic

### Direction

Client → Server

### Payload

```json
{
  "type": "chat_message",
  "content": "Hello, what's the weather?",
  "agent_id": "yuri-assistant",
  "user_id": "user-123",
  "session_id": "optional-uuid"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"chat_message"` |
| `content` | string | Yes | User's input text |
| `agent_id` | string | Yes | Agent identifier |
| `user_id` | string | Yes | User identifier |
| `persona` | string | No | Custom persona/system prompt |
| `images` | array | No | Image URLs or base64 strings |
| `limit` | integer | No | STM message limit (default: 10) |
| `session_id` | string | No | Session ID (new if omitted) |
| `metadata` | object | No | Additional metadata |

### Response Flow

1. `stream_start` - Response begins
2. `stream_token` (multiple) - Text chunks
3. `tool_call` / `tool_result` - If tools used
4. `tts_ready_chunk` - TTS-ready text
5. `stream_end` - Response complete

## 3. Usage

```javascript
socket.send(JSON.stringify({
  type: 'chat_message',
  content: 'Tell me a fun fact',
  agent_id: 'yuri-assistant',
  user_id: 'user-123'
}));
```

---

## Appendix

### A. Related Documents

- [Stream Start](./WebSocket_StreamStart.md)
- [Stream Token](./WebSocket_StreamToken.md)
- [Stream End](./WebSocket_StreamEnd.md)
