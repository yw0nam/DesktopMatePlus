# Frontend Integration Guide (Last Updated: 2025-11-27)

Welcome to the DesktopMatePlus backend! This guide provides frontend developers with all the necessary information to integrate with the backend services, including the REST API and the real-time WebSocket communication.

## Getting Started

To begin, you should familiarize yourself with the two main ways to interact with the backend:

1. **[REST API](./api/REST_API_GUIDE.md)**: For stateless operations like managing chat history (STM), synthesizing speech (TTS), and analyzing images (VLM).
2. **[WebSocket API](./websocket/WEBSOCKET_API_GUIDE.md)**: For real-time, stateful, and interactive chat sessions with the agent.

## Authentication

Both the REST API and WebSocket connections require authentication. The backend expects an authentication token to be provided. For the WebSocket, this is done via an `authorize` message, and for the REST API, it should be included in the request headers.

*For development purposes, any non-empty string can be used as a token.*

## Core Concepts

- **Agent**: The AI model that processes user input and generates responses.
- **User**: The end-user interacting with the application. Identified by `user_id`.
- **Agent ID**: Persistent agent identifier (`agent_id`) for multi-agent support.
- **Session/Conversation**: A series of interactions between a user and an agent. A `session_id` is used to track this.
- **Turn**: A single user request and the agent's full response, which may include multiple messages or tool calls. A `turn_id` is used to track this.

## Typical Workflow

```text
1. Connect to WebSocket: ws://localhost:5500/v1/chat/stream
2. Send 'authorize' message with token
3. Receive 'authorize_success' with connection_id
4. Send 'chat_message' with content, agent_id, user_id, session_id
5. Receive 'stream_start'
6. Receive multiple 'tts_ready_chunk' events (sentence-level text)
   → For each chunk, call POST /v1/tts/synthesize to get audio
   → Play audio immediately for real-time experience
7. Receive 'stream_end'
8. Memory is saved in background (non-blocking)
9. Repeat from step 4 for next message
```

## Memory System

- **STM (Short-Term Memory)**: MongoDB-based session history. Retrieved before agent processing.
- **LTM (Long-Term Memory)**: mem0-based semantic memory. Searched for relevant context.
- **Async Save**: Memory operations run in background threads after `stream_end`, ensuring TTS playback is never blocked.

Note, This memory rely on agent_id and user_id. If any of these change, the memory context will be lost.

---

## API Models Reference

### WebSocket Messages

#### Client → Server Messages

| Message Type | Description |
|-------------|-------------|
| `authorize` | Authenticate the connection with a token |
| `pong` | Response to server ping for heartbeat |
| `chat_message` | Send a user's message to the agent |
| `interrupt_stream` | Interrupt an active response stream |
| `fetch_backgrounds` | Request list of available backgrounds |
| `fetch_avatar_configs` | Request list of avatar configurations |
| `switch_avatar_config` | Switch to a different avatar configuration |

#### Server → Client Messages

| Message Type | Description |
|-------------|-------------|
| `authorize_success` | Confirms successful authorization (includes `connection_id`) |
| `authorize_error` | Indicates authorization failure |
| `ping` | Heartbeat message from server |
| `stream_start` | Beginning of agent response (includes `turn_id`, `session_id`) |
| `stream_token` | Internal token chunk (not typically used by clients) |
| `tts_ready_chunk` | Complete sentence ready for TTS (includes `chunk`, optional `emotion`) |
| `tool_call` | Agent is calling a tool (includes `tool_name`, `args`) |
| `tool_result` | Result from tool execution |
| `stream_end` | End of agent response (includes `turn_id`, `session_id`, `content`) |
| `error` | Error message (includes `error`, optional `code`) |
| `background_files` | List of available background files |
| `avatar_config_files` | List of avatar configurations |
| `avatar_config_switched` | Confirmation of config switch |
| `set_model_and_conf` | Set Live2D model and configuration |


Please refer to the specific guides for detailed information on each endpoint and message type.
