# WebSocket: Authorize Error

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Indicate WebSocket authorization failure
- **I/O**: Server sends `{ type: "authorize_error", error }`

## 2. Core Logic

### Direction

Server → Client

### Payload

```json
{
  "type": "authorize_error",
  "error": "Invalid or expired token"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"authorize_error"` |
| `error` | string | Yes | Error description |

### Behavior

- Client should handle error (display message, retry with different token)
- Connection may be closed by server

## 3. Usage

```javascript
socket.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'authorize_error') {
    console.error('Auth failed:', msg.error);
    socket.close();
  }
};
```

---

## Appendix

### A. Related Documents

- [Authorize](./WebSocket_Authorize.md)
