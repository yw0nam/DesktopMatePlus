# WebSocket API Guide

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
| `fetch_backgrounds` | Get backgrounds | [FetchBackgrounds](./WebSocket_FetchBackgrounds.md) |
| `fetch_avatar_configs` | Get avatars | [FetchAvatarConfigs](./WebSocket_FetchAvatarConfigs.md) |
| `switch_avatar_config` | Switch avatar | [SwitchAvatarConfig](./WebSocket_SwitchAvatarConfig.md) |

### Server → Client Messages

| Type | Description | Doc |
|------|-------------|-----|
| `authorize_success` | Auth confirmed | [AuthorizeSuccess](./WebSocket_AuthorizeSuccess.md) |
| `authorize_error` | Auth failed | [AuthorizeError](./WebSocket_AuthorizeError.md) |
| `ping` | Heartbeat | [Ping](./WebSocket_Ping.md) |
| `stream_start` | Response begins | [StreamStart](./WebSocket_StreamStart.md) |
| `stream_token` | Token chunk | [StreamToken](./WebSocket_StreamToken.md) |
| `stream_end` | Response complete | [StreamEnd](./WebSocket_StreamEnd.md) |
| `tts_ready_chunk` | TTS-ready text | [TTSReadyChunk](./WebSocket_TTSReadyChunk.md) |
| `tool_call` | Tool invocation | [ToolCall](./WebSocket_ToolCall.md) |
| `tool_result` | Tool response | [ToolResult](./WebSocket_ToolResult.md) |
| `error` | Error occurred | [ErrorMessage](./WebSocket_ErrorMessage.md) |
| `background_files` | Background list | [BackgroundFiles](./WebSocket_BackgroundFiles.md) |
| `avatar_config_files` | Avatar list | [AvatarConfigFiles](./WebSocket_AvatarConfigFiles.md) |
| `avatar_config_switched` | Avatar changed | [AvatarConfigSwitched](./WebSocket_AvatarConfigSwitched.md) |
| `set_model_and_conf` | Model config | [SetModelAndConf](./WebSocket_SetModelAndConf.md) |

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

- [REST API Guide](../api/REST_API_GUIDE.md)
- [WebSocket Service](../feature/service/WebSocket_Service.md)
