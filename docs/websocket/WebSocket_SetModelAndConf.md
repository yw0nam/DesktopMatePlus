# WebSocket: Set Model And Conf

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Provide Live2D model and configuration info to client
- **I/O**: Server sends `{ type: "set_model_and_conf", model_info, conf_name, ... }`

## 2. Core Logic

### Direction

Server → Client

### Payload

```json
{
  "type": "set_model_and_conf",
  "model_info": {
    "model_path": "/models/mao_pro/mao_pro.model3.json",
    "expressions": ["happy", "sad", "angry"],
    "motions": ["idle", "wave", "nod"]
  },
  "conf_name": "Mao Pro",
  "conf_uid": "mao-pro-001",
  "client_uid": "client-123",
  "persona_prompt": "You are a friendly virtual assistant named Mao."
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"set_model_and_conf"` |
| `model_info` | object | Yes | Live2D model paths and capabilities |
| `conf_name` | string | Yes | Configuration display name |
| `conf_uid` | string | Yes | Configuration unique ID |
| `client_uid` | string | Yes | Client unique ID |
| `persona_prompt` | string | Yes | Persona prompt for the agent |

### Behavior

- Provides all info to load/configure Live2D model
- Initialize renderer with paths, expressions, motions

## 3. Usage

```javascript
socket.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'set_model_and_conf') {
    loadLive2DModel(msg.model_info.model_path);
    setExpressions(msg.model_info.expressions);
    setMotions(msg.model_info.motions);
  }
};
```

---

## Appendix

### A. Related Documents

- [Switch Avatar Config](./WebSocket_SwitchAvatarConfig.md)
- [Avatar Config Files](./WebSocket_AvatarConfigFiles.md)
