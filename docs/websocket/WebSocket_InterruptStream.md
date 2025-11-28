# WebSocket: Interrupt Stream

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Cancel an active response stream
- **I/O**: Client sends `{ type: "interrupt_stream", turn_id? }`

## 2. Core Logic

### Direction

Client → Server

### Payload

```json
{
  "type": "interrupt_stream",
  "turn_id": "optional-turn-id"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"interrupt_stream"` |
| `turn_id` | string | No | Specific turn to interrupt (all if omitted) |

### Behavior

- Stops ongoing agent response
- Useful for user interruption (new question before current completes)

## 3. Usage

```javascript
function interruptStream(turnId = null) {
  const msg = { type: 'interrupt_stream' };
  if (turnId) msg.turn_id = turnId;
  socket.send(JSON.stringify(msg));
}
```

---

## Appendix

### A. Related Documents

- [Stream Start](./WebSocket_StreamStart.md)
- [Chat Message](./WebSocket_ChatMessage.md)
