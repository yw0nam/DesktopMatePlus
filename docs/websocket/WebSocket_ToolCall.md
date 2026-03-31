# WebSocket: Tool Call

Updated: 2026-03-18

## 1. Synopsis

- **Purpose**: Internal event when agent invokes a tool — logged server-side only; NOT forwarded to client
- **I/O**: Agent emits `{ type: "tool_call", tool_name, args }` → server logs it

> **Server-internal only**: This event is never sent to the WebSocket client.

## 2. Core Logic

### Direction

Agent → Server (internal only)

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

- Server logs tool name and args for observability
- Client is not notified; no UI action needed

---

## Appendix

### A. Related Documents

- [Tool Result](./WebSocket_ToolResult.md)
