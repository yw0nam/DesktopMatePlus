# WebSocket: Stream Start

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Signal beginning of agent response
- **I/O**: Server sends `{ type: "stream_start", turn_id, conversation_id }`

## 2. Core Logic

### Direction

Server → Client

### Payload

```json
{
  "type": "stream_start",
  "turn_id": "turn-uuid",
  "conversation_id": "conv-uuid"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"stream_start"` |
| `turn_id` | string | Yes | Unique ID for this response turn |
| `conversation_id` | string | Yes | Session identifier |

### Behavior

- Marks start of response sequence
- Followed by `stream_token`, `tool_call`, `tts_ready_chunk` messages
- Ends with `stream_end`

## 3. Usage

```javascript
socket.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'stream_start') {
    currentTurnId = msg.turn_id;
    showTypingIndicator();
  }
};
```

---

## Appendix

### A. Related Documents

- [Stream Token](./WebSocket_StreamToken.md)
- [Stream End](./WebSocket_StreamEnd.md)
