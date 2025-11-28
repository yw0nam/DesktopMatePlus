# WebSocket: Fetch Avatar Configs

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Request list of available avatar configurations
- **I/O**: Client sends `{ type: "fetch_avatar_configs" }` → Server responds with `avatar_config_files`

## 2. Core Logic

### Direction

Client → Server

### Payload

```json
{ "type": "fetch_avatar_configs" }
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"fetch_avatar_configs"` |

### Response

Server sends `avatar_config_files` with list of configurations.

## 3. Usage

```javascript
socket.send(JSON.stringify({ type: 'fetch_avatar_configs' }));

socket.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'avatar_config_files') {
    msg.configs.forEach(c => console.log(c.name, c.filename));
  }
};
```

---

## Appendix

### A. Related Documents

- [Avatar Config Files](./WebSocket_AvatarConfigFiles.md)
- [Switch Avatar Config](./WebSocket_SwitchAvatarConfig.md)
