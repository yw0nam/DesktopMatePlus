# WebSocket Service

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Real-time communication with streaming responses and TTS integration
- **I/O**: WebSocket messages → Streamed events (tokens, TTS chunks, tool calls)

## 2. Core Logic

### Components

| Component | File | Purpose |
|-----------|------|---------|
| `WebSocketManager` | `manager/websocket_manager.py` | Connection lifecycle |
| `ConnectionHandler` | `manager/connection.py` | Per-connection handling |
| `HeartbeatManager` | `manager/heartbeat.py` | Keep-alive ping/pong |
| `MessageProcessor` | `message_processor/processor.py` | Token processing & TTS chunking |

### Message Flow

```text
1. Client connects → WebSocket handshake
2. Client sends 'authorize' → Server validates token
3. Server sends 'authorize_success' with connection_id
4. Client sends 'chat_message'
5. Server streams: stream_start → tts_ready_chunk(s) → stream_end
6. Server sends 'ping' periodically → Client responds 'pong'
```

### Key Features

- Authorization-based connections
- Heartbeat monitoring with configurable timeout
- Stream interruption support
- Real-time TTS chunk generation (sentence-level)
- Avatar and background management

### Event Types

| Direction | Type | Description |
|-----------|------|-------------|
| C→S | `authorize` | Auth with token |
| S→C | `authorize_success` | Auth confirmed |
| C→S | `chat_message` | User message |
| S→C | `stream_start` | Response begins |
| S→C | `tts_ready_chunk` | Sentence ready for TTS |
| S→C | `tool_call` | Agent calling tool |
| S→C | `tool_result` | Tool response |
| S→C | `stream_end` | Response complete |
| S→C | `ping` | Heartbeat |
| C→S | `pong` | Heartbeat response |
| C→S | `interrupt_stream` | Cancel streaming |

## 3. Usage

### Client Connection (JavaScript)

```javascript
const socket = new WebSocket('ws://localhost:5500/v1/chat/stream');

socket.onopen = () => {
    socket.send(JSON.stringify({
        type: 'authorize',
        token: 'your-auth-token'
    }));
};

socket.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    switch (msg.type) {
        case 'authorize_success':
            console.log('Connected:', msg.connection_id);
            break;
        case 'tts_ready_chunk':
            // Synthesize and play audio
            synthesizeTTS(msg.chunk);
            break;
        case 'ping':
            socket.send(JSON.stringify({ type: 'pong' }));
            break;
    }
};

// Send message
socket.send(JSON.stringify({
    type: 'chat_message',
    content: 'Hello!',
    user_id: 'user_001',
    agent_id: 'agent_001',
    conversation_id: 'conv_001'
}));
```

---

## Appendix

### A. Related Documents

- [Service Layer](./README.md)
- [WebSocket API Guide](../../websocket/WEBSOCKET_API_GUIDE.md)
- [WebSocket Message Reference](../../websocket/)
