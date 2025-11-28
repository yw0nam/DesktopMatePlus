# WebSocket: Tool Result

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Report tool execution result
- **I/O**: Server sends `{ type: "tool_result", result }`

## 2. Core Logic

### Direction

Server → Client

### Payload

```json
{
  "type": "tool_result",
  "result": "{\"temperature\": \"15°C\", \"condition\": \"Cloudy\"}",
  "node": "tool_execution_node"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"tool_result"` |
| `result` | string | Yes | JSON string of tool output |
| `node` | string | No | Processing node identifier |

### Behavior

- Informational (show tool data to user if desired)
- Agent continues processing with result
- More `stream_token` messages follow

## 3. Usage

```javascript
socket.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'tool_result') {
    hideToolIndicator();
    displayToolResult(JSON.parse(msg.result));
  }
};
```

---

## Appendix

### A. Related Documents

- [Tool Call](./WebSocket_ToolCall.md)
