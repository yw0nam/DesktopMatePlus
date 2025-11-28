# WebSocket: Tool Call

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Inform client that agent is invoking a tool
- **I/O**: Server sends `{ type: "tool_call", tool_name, args }`

## 2. Core Logic

### Direction

Server → Client

### Payload

```json
{
  "type": "tool_call",
  "tool_name": "get_weather",
  "args": "{\"city\": \"London\"}",
  "node": "tool_execution_node"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"tool_call"` |
| `tool_name` | string | Yes | Name of tool being called |
| `args` | string | Yes | JSON string of arguments |
| `node` | string | No | Processing node identifier |

### Behavior

- Informational message (no client action required)
- Show UI indicator: "Searching for weather..."
- Result follows in `tool_result`

## 3. Usage

```javascript
socket.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'tool_call') {
    showToolIndicator(`Using ${msg.tool_name}...`);
  }
};
```

---

## Appendix

### A. Related Documents

- [Tool Result](./WebSocket_ToolResult.md)
