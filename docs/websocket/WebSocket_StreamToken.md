# WebSocket: Stream Token

Updated: 2026-03-18

## 1. Synopsis

- **Purpose**: Internal token event from agent — consumed for TTS synthesis; NOT forwarded to client
- **I/O**: Agent emits `{ type: "stream_token", chunk }` → server processes for TTS → sends `tts_chunk` to client

> **Server-internal only**: This event is never sent to the WebSocket client. The client receives `tts_chunk` events instead.

## 2. Core Logic

### Direction

Agent → Server (internal only)

### Payload

```json
{
  "type": "stream_token",
  "chunk": "Hello! ",
  "turn_id": "turn-uuid",
  "node": "agent_response_node"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"stream_token"` |
| `chunk` | string | Yes | Text fragment |
| `turn_id` | string | No | Injected by `_normalize_event` |
| `node` | string | No | Processing node identifier |

### Behavior

- Multiple tokens emitted per turn by the agent
- Server buffers chunks into sentences and synthesizes TTS for each sentence
- Final output to client is `tts_chunk` events, not `stream_token`

---

## Appendix

### A. Related Documents

- [Stream Start](./WebSocket_StreamStart.md)
- [Stream End](./WebSocket_StreamEnd.md)
