# WebSocket: Stream Token

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Deliver text chunk of agent response
- **I/O**: Server sends `{ type: "stream_token", chunk, turn_id }`

## 2. Core Logic

### Direction

Server → Client

### Payload

```json
{
  "type": "stream_token",
  "chunk": "Hello! ",
  "turn_id": "turn-uuid",
  "node": "agent_response_node"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"stream_token"` |
| `chunk` | string | Yes | Text fragment |
| `turn_id` | string | Yes | Links to `stream_start` |
| `node` | string | No | Processing node identifier |

### Behavior

- Multiple tokens sent per turn
- Append chunks to create full response
- Stream concludes with `stream_end`

## 3. Usage

```javascript
socket.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'stream_token') {
    responseElement.textContent += msg.chunk;
  }
};
```

---

## Appendix

### A. Related Documents

- [Stream Start](./WebSocket_StreamStart.md)
- [Stream End](./WebSocket_StreamEnd.md)
