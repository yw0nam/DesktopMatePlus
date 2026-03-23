# WebSocket API Guide

Updated: 2026-03-23

## 1. Synopsis

- **Purpose**: Real-time streaming chat with agent responses and TTS integration
- **I/O**: WebSocket messages (JSON) → Streamed events (tokens, TTS chunks, tool calls)

## 2. Core Logic

### Connection

- **URL**: `ws://127.0.0.1:5500/v1/chat/stream`

### Communication Flow

```text
1. Connect → WebSocket handshake
2. Send 'authorize' → Receive 'authorize_success'
3. Send 'chat_message' → Receive stream events
4. Respond 'pong' to 'ping' (heartbeat)
```

### Client → Server Messages

| Type | Description | Doc |
|------|-------------|-----|
| `authorize` | Auth with token | [Authorize](./WebSocket_Authorize.md) |
| `pong` | Heartbeat response | [Pong](./WebSocket_Pong.md) |
| `chat_message` | User message | [ChatMessage](./WebSocket_ChatMessage.md) |
| `interrupt_stream` | Cancel streaming | [InterruptStream](./WebSocket_InterruptStream.md) |

### Server → Client Messages

| Type | Description | Doc |
|------|-------------|-----|
| `authorize_success` | Auth confirmed | [AuthorizeSuccess](./WebSocket_AuthorizeSuccess.md) |
| `authorize_error` | Auth failed | [AuthorizeError](./WebSocket_AuthorizeError.md) |
| `ping` | Heartbeat | [Ping](./WebSocket_Ping.md) |
| `stream_start` | Response begins | [StreamStart](./WebSocket_StreamStart.md) |
| `stream_end` | Response complete | [StreamEnd](./WebSocket_StreamEnd.md) |
| `tts_chunk` | TTS audio + motion | [TtsChunk](./WebSocket_TtsChunk.md) |
| `error` | Error occurred | [ErrorMessage](./WebSocket_ErrorMessage.md) |

- Note: `stream_token`, `tool_call`, and `tool_result` events are **server-internal only** — they are processed for TTS and logging respectively, and are never forwarded to the WebSocket client.

### Configuration

WebSocket behavior is configured in `yaml_files/main.yml`:

```yaml
websocket:
  ping_interval_seconds: 30       # Heartbeat interval
  pong_timeout_seconds: 10        # Pong response timeout
  max_error_tolerance: 5          # Max consecutive errors
  error_backoff_seconds: 0.5      # Delay after recoverable errors
  inactivity_timeout_seconds: 300 # Idle connection timeout
  disconnect_timeout_seconds: 5.0 # Graceful disconnect timeout
  tts_barrier_timeout_seconds: 10.0 # Per-chunk inactivity timeout for TTS barrier (rolling)
```

### Connection Lifecycle

Connections are closed in these cases:

| Condition | Code | Reason | Docs |
|-----------|------|---------|------|
| Ping Timeout | 4000 | No pong response | See heartbeat behavior below |
| Auth Failed | 4001 | Invalid token | [AuthorizeError](./WebSocket_AuthorizeError.md) |
| Concurrent Turn | 4002 | Multiple simultaneous messages | Handled with error response |
| Inactivity | 1000 | No messages for 5+ min | Normal closure |
| Max Errors | 1011 | Too many errors | [ErrorHandling](./WebSocket_ErrorHandling.md) |

**Heartbeat Behavior:**

- Server sends `ping` every 30s (configurable)
- Client must respond with `pong` within 10s (configurable)
- First ping is not checked (grace period)
- Connection closes if pong not received within timeout

**Concurrent Message Protection:**

- Only one chat turn allowed per connection at a time
- New message while processing returns error code 4002
- Client should wait for `stream_end` or use `interrupt_stream`

For detailed connection management, see [Connection Lifecycle Guide](./WebSocket_ConnectionLifecycle.md).

## 3. Usage

```javascript
const socket = new WebSocket('ws://127.0.0.1:5500/v1/chat/stream');

socket.onopen = () => {
    socket.send(JSON.stringify({ type: 'authorize', token: 'your-token' }));
};

socket.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === 'authorize_success') {
        socket.send(JSON.stringify({
            type: 'chat_message',
            content: 'Hello!',
            user_id: 'user_001',
            agent_id: 'agent_001'
        }));
    }
};
```

---

## Appendix

### A. Message Structure

All messages share a base structure:

```json
{
    "type": "message_type",
    "id": "optional-message-id",
    "timestamp": 1732723200.123
}
```

### B. Related Documents

- [Connection Lifecycle](./WebSocket_ConnectionLifecycle.md) - Detailed connection management
- [Error Handling](./WebSocket_ErrorHandling.md) - Error classification and recovery
- [REST API Guide](../api/CLAUDE.md)
- [WebSocket Service](../feature/service/WebSocket_Service.md)

### C. Error Codes

| Code | Category | Retry | Description |
|------|----------|-------|-------------|
| 1000 | Normal | No | Normal closure |
| 1011 | Fatal | No | Internal error |
| 4000 | Timeout | No | Ping timeout |
| 4001 | Auth | No | Authentication failed |
| 4002 | Client | Yes | Concurrent turn rejected |
| 4003 | Interrupt | N/A | Stream interrupted |
| 4004 | NotFound | No | Turn not found |
