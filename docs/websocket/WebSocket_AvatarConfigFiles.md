# WebSocket: Avatar Config Files

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Return list of available avatar configurations
- **I/O**: Server sends `{ type: "avatar_config_files", configs[] }`

## 2. Core Logic

### Direction

Server → Client

### Payload

```json
{
  "type": "avatar_config_files",
  "configs": [
    { "filename": "en_nuke_debate.yaml", "name": "Nuke Debate" },
    { "filename": "en_helpful_ai.yaml", "name": "Helpful AI" }
  ]
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"avatar_config_files"` |
| `configs` | array | Yes | List of config objects |
| `configs[].filename` | string | Yes | Config filename |
| `configs[].name` | string | Yes | Display name |

### Behavior

- Response to `fetch_avatar_configs`
- Use to populate persona/character selector

## 3. Usage

```javascript
socket.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'avatar_config_files') {
    msg.configs.forEach(c => addConfigOption(c.filename, c.name));
  }
};
```

---

## Appendix

### A. Related Documents

- [Fetch Avatar Configs](./WebSocket_FetchAvatarConfigs.md)
- [Switch Avatar Config](./WebSocket_SwitchAvatarConfig.md)
