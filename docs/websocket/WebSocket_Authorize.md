# WebSocket: Authorize

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Authenticate WebSocket connection
- **I/O**: Client sends `{ type: "authorize", token }` → Server responds with `authorize_success` or `authorize_error`

## 2. Core Logic

### Direction

Client → Server

### Payload

```json
{
  "type": "authorize",
  "token": "your-auth-token"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"authorize"` |
| `token` | string | Yes | Auth token (any non-empty string for dev) |

### Behavior

- **Must** be sent immediately after connection
- Server blocks all other messages until authorized
- On success: `authorize_success` with `connection_id`
- On failure: `authorize_error` with error message

## 3. Usage

```javascript
const socket = new WebSocket('ws://127.0.0.1:5500/v1/chat/stream');
socket.onopen = () => {
  socket.send(JSON.stringify({ type: 'authorize', token: 'dev-token' }));
};
```

---

## Appendix

### A. Related Documents

- [Authorize Success](./WebSocket_AuthorizeSuccess.md)
- [Authorize Error](./WebSocket_AuthorizeError.md)
