# WebSocket: Background Files

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Return list of available background images
- **I/O**: Server sends `{ type: "background_files", files[] }`

## 2. Core Logic

### Direction

Server → Client

### Payload

```json
{
  "type": "background_files",
  "files": ["background1.jpg", "background2.png", "nature.jpg"]
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"background_files"` |
| `files` | array | Yes | List of background filenames |

### Behavior

- Response to `fetch_backgrounds`
- Use to populate background selector UI

## 3. Usage

```javascript
socket.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'background_files') {
    msg.files.forEach(file => addBackgroundOption(file));
  }
};
```

---

## Appendix

### A. Related Documents

- [Fetch Backgrounds](./WebSocket_FetchBackgrounds.md)
