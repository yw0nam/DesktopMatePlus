# WebSocket: Tool Result

Updated: 2026-03-18

## 1. Synopsis

- **Purpose**: Internal event for tool execution result — logged server-side only; NOT forwarded to client
- **I/O**: Agent emits `{ type: "tool_result", result }` → server logs it

> **Server-internal only**: This event is never sent to the WebSocket client.

## 2. Core Logic

### Direction

Agent → Server (internal only)

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

- Server logs the result for observability
- Agent continues processing with result
- Client receives subsequent `tts_chunk` events (not this event)

---

## Appendix

### A. Related Documents

- [Tool Call](./WebSocket_ToolCall.md)
