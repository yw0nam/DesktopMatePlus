# WebSocket: Authorize Success

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Confirm successful WebSocket authorization
- **I/O**: Server sends `{ type: "authorize_success", connection_id }`

## 2. Core Logic

### Direction

Server → Client

### Payload

```json
{
  "type": "authorize_success",
  "connection_id": "uuid-string"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"authorize_success"` |
| `connection_id` | string | Yes | Unique UUID for this connection |

### Behavior

- Sent immediately after successful authorization
- Client can now send `chat_message` and other messages

## 3. Usage

```javascript
socket.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'authorize_success') {
    console.log('Connected:', msg.connection_id);
    // Ready to send chat messages
  }
};
```

---

## Appendix

### A. Related Documents

- [Authorize](./WebSocket_Authorize.md)
- [Chat Message](./WebSocket_ChatMessage.md)
