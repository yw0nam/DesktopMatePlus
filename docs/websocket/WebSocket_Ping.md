# WebSocket: Ping

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Server heartbeat to check client connection
- **I/O**: Server sends `{ type: "ping" }` → Client responds with `pong`

## 2. Core Logic

### Direction

Server → Client

### Payload

```json
{ "type": "ping" }
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"ping"` |

### Behavior

- Sent periodically by server
- Client must respond with `pong`
- Connection may close if no response

## 3. Usage

```javascript
socket.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'ping') {
    socket.send(JSON.stringify({ type: 'pong' }));
  }
};
```

---

## Appendix

### A. Related Documents

- [Pong](./WebSocket_Pong.md)
