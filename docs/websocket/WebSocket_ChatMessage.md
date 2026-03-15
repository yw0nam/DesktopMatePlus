# WebSocket: Chat Message

Updated: 2026-03-15

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
| `images` | array | No | Images in OpenAI-compatible format (see below) |
| `limit` | integer | No | STM message limit (default: 10) |
| `session_id` | string | No | Session ID (new if omitted) |
| `tts_enabled` | bool | No | Enable TTS synthesis (default: `true`). `false` = skip audio, still send `tts_chunk` with motion |
| `reference_id` | string | No | Voice reference ID for TTS. `null` = engine default voice |
| `metadata` | object | No | Additional metadata |

### Response Flow

1. `stream_start` - Response begins
2. `stream_token` (multiple) - Text chunks
3. `tool_call` / `tool_result` - If tools used
4. `tts_chunk` (multiple) - TTS audio + motion per sentence (parallel to tokens)
5. `stream_end` - Response complete (all `tts_chunk` guaranteed delivered before this)

### Image Format

Images must follow the OpenAI-compatible format. Each image is an object with `type` and `image_url`:

```json
{
  "type": "chat_message",
  "content": "What's in this image?",
  "agent_id": "yuri-assistant",
  "user_id": "user-123",
  "images": [
    {
      "type": "image_url",
      "image_url": {
        "url": "data:image/png;base64,<base64_data>",
        "detail": "auto"
      }
    }
  ]
}
```

`detail` is optional and defaults to `"auto"`. Accepted values: `"auto"`, `"low"`, `"high"`.

Images are only processed when the agent has `support_image: true` in its config.

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
- [TTS Chunk](./WebSocket_TtsChunk.md)
- [Stream End](./WebSocket_StreamEnd.md)
