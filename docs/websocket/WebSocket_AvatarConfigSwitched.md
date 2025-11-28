# WebSocket: Avatar Config Switched

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Confirm avatar configuration switch
- **I/O**: Server sends `{ type: "avatar_config_switched", file }`

## 2. Core Logic

### Direction

Server → Client

### Payload

```json
{
  "type": "avatar_config_switched",
  "file": "en_nuke_debate.yaml"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"avatar_config_switched"` |
| `file` | string | Yes | Config filename that was activated |

### Behavior

- Response to successful `switch_avatar_config`
- Update UI to reflect new active configuration

## 3. Usage

```javascript
socket.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'avatar_config_switched') {
    updateCurrentConfig(msg.file);
    showNotification(`Switched to: ${msg.file}`);
  }
};
```

---

## Appendix

### A. Related Documents

- [Switch Avatar Config](./WebSocket_SwitchAvatarConfig.md)
