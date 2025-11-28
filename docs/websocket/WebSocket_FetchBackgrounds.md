# WebSocket: Fetch Backgrounds

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Request list of available background images
- **I/O**: Client sends `{ type: "fetch_backgrounds" }` → Server responds with `background_files`

## 2. Core Logic

### Direction

Client → Server

### Payload

```json
{ "type": "fetch_backgrounds" }
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"fetch_backgrounds"` |

### Response

Server sends `background_files` with list of available images.

## 3. Usage

```javascript
socket.send(JSON.stringify({ type: 'fetch_backgrounds' }));

socket.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'background_files') {
    populateBackgroundSelector(msg.files);
  }
};
```

---

## Appendix

### A. Related Documents

- [Background Files](./WebSocket_BackgroundFiles.md)
