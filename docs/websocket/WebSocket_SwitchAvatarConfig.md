# WebSocket: Switch Avatar Config

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Switch to a different avatar/persona configuration
- **I/O**: Client sends `{ type: "switch_avatar_config", file }` → Server responds with `avatar_config_switched`

## 2. Core Logic

### Direction

Client → Server

### Payload

```json
{
  "type": "switch_avatar_config",
  "file": "en_nuke_debate.yaml"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"switch_avatar_config"` |
| `file` | string | Yes | Config filename to switch to |

### Response

Server sends `avatar_config_switched` to confirm.

## 3. Usage

```javascript
function switchConfig(filename) {
  socket.send(JSON.stringify({
    type: 'switch_avatar_config',
    file: filename
  }));
}

switchConfig('en_nuke_debate.yaml');
```

---

## Appendix

### A. Related Documents

- [Avatar Config Switched](./WebSocket_AvatarConfigSwitched.md)
- [Fetch Avatar Configs](./WebSocket_FetchAvatarConfigs.md)
