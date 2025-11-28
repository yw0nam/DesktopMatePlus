# WebSocket: Pong

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Client heartbeat response
- **I/O**: Client sends `{ type: "pong" }` in response to `ping`

## 2. Core Logic

### Direction

Client → Server

### Payload

```json
{ "type": "pong" }
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"pong"` |

### Behavior

- Must be sent in response to server `ping`
- Maintains connection alive

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

- [Ping](./WebSocket_Ping.md)
