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
| `persona_id` | string | No | Persona identifier — matches a key in `yaml_files/personas.yml` (default: `"yuri"`) |
| `images` | array | No | Images in OpenAI-compatible format (see below) |
| `limit` | integer | No | STM message limit (default: 10) |
| `session_id` | string | No | Session ID (new if omitted) |
| `tts_enabled` | bool | No | Enable TTS synthesis (default: `true`). `false` = skip audio, still send `tts_chunk` with motion |
| `reference_id` | string | No | Voice reference ID for TTS. `null` = engine default voice |
| `metadata` | object | No | Additional metadata |

### Response Flow

1. `stream_start` — Response begins
2. `stream_token` (multiple) — Text tokens for real-time text rendering
3. `tts_chunk` (multiple) — TTS audio (WAV) + VRM keyframes per sentence
4. `stream_end` — Response complete (all `tts_chunk` guaranteed delivered before this)

> **Note**: `stream_token` is forwarded to the client — use it for real-time text display.
> `tool_call` and `tool_result` are **server-internal only** (logged, never forwarded to client).

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

### Image Size Constraints

| Limit                      | Value   |
|---------------------------|---------|
| Max binary size per image  | ~4.5 MB |
| Max base64 size per image  | 6 MB    |

**Server enforcement**: `ImageContent` validates the base64 URL size on receipt. If exceeded, the server returns an `error` event with a descriptive message instead of silently closing the connection.

**Client responsibility**: Resize images to under 4 MB binary before encoding. The reference demo (`examples/realtime_tts_streaming_demo.py`) handles this automatically using Pillow.

> **Why**: Base64-encoding a large image (e.g. 27 MB PNG → 36 MB JSON) exceeds the WebSocket frame limit, causing a silent connection drop with no error log.

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
