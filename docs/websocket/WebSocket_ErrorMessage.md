# WebSocket: Error Message

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Report errors during WebSocket communication
- **I/O**: Server sends `{ type: "error", code, error }`

## 2. Core Logic

### Direction

Server → Client

### Payload

```json
{
  "type": "error",
  "code": 500,
  "error": "An unexpected error occurred"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"error"` |
| `code` | integer | Yes | HTTP-style error code |
| `error` | string | Yes | Error description |

### Common Codes

| Code | Meaning |
|------|---------|
| `400` | Bad request |
| `401` | Unauthorized |
| `500` | Internal server error |

## 3. Usage

```javascript
socket.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'error') {
    console.error(`Error ${msg.code}: ${msg.error}`);
    if (msg.code === 401) handleReauthorize();
  }
};
```

---

## Appendix

### A. Related Documents

- [Authorize Error](./WebSocket_AuthorizeError.md)
