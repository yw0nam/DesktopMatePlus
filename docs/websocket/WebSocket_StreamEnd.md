# WebSocket: Stream End

Updated: 2026-03-15

## 1. Synopsis

- **Purpose**: Signal completion of agent response
- **I/O**: Server sends `{ type: "stream_end", turn_id, content }`

## 2. Core Logic

### Direction

Server → Client

### Payload

```json
{
  "type": "stream_end",
  "turn_id": "turn-uuid",
  "session_id": "conv-uuid",
  "content": "Complete response text here."
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"stream_end"` |
| `turn_id` | string | Yes | Turn that completed |
| `session_id` | string | Yes | Session identifier |
| `content` | string | Yes | Full aggregated response |

### Behavior

- No more `stream_token` for this turn
- `content` contains complete response (verify/replace streamed text)
- All `tts_chunk` messages for this turn are **guaranteed to arrive before `stream_end`** (TTS barrier with 10s timeout)
- Hide typing indicator, save to history

## 3. Usage

```javascript
socket.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'stream_end') {
    hideTypingIndicator();
    responseElement.textContent = msg.content;
    saveToHistory('assistant', msg.content);
  }
};
```

---

## Appendix

### A. Related Documents

- [Stream Start](./WebSocket_StreamStart.md)
- [Stream Token](./WebSocket_StreamToken.md)
- [TTS Chunk](./WebSocket_TtsChunk.md)
