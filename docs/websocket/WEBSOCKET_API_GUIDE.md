# WebSocket API Guide

This guide details the real-time communication protocol used by DesktopMatePlus for interactive chat sessions.

## Connection

- **URL**: `ws://127.0.0.1:5500/v1/chat/stream`

The WebSocket connection is the primary channel for streaming agent responses, handling tool calls, and managing the flow of a conversation.

## Communication Flow

1. **Client Connects**: The client establishes a WebSocket connection to the server.
2. **Client Authorizes**: The client sends an `authorize` message with a token.
3. **Server Acknowledges**: The server responds with either an `authorize_success` message with a unique `connection_id`, or an `authorize_error` message if authorization fails.
4. **Client Sends Chat Message**: The client sends a `chat_message` to the agent (with required `agent_id` and `user_id`).
5. **Server Streams Response**: The server sends a series of messages to the client, including:
    - `stream_start`: Indicates the beginning of a new response turn.
    - `tts_ready_chunk`: A chunk of text ready for TTS synthesis (sentence-level, emitted during streaming).
    - `tool_call`: If the agent needs to use a tool.
    - `tool_result`: The result of the tool execution.
    - `stream_end`: Indicates the end of the response turn.
6. **Background Memory Save**: After `stream_end`, memory is saved asynchronously in a background thread (non-blocking).
7. **Lather, Rinse, Repeat**: The process repeats from step 4 for each new user message.

> **Note**: Raw `stream_token` events are processed internally for sentence detection. Clients receive `tts_ready_chunk` events which contain complete sentences ready for TTS synthesis.

## Base Message Structure

All WebSocket messages share a common base structure with optional tracking fields:

```json
{
    "type": "message_type",
    "id": "optional-message-id",
    "timestamp": 1732723200.123
}
```

- `type` (string, required): The message type identifier.
- `id` (string, optional): Message ID for tracking purposes.
- `timestamp` (float, optional): Unix timestamp of the message.

## Message Types

All messages are JSON objects with a `type` field that identifies the message.

### Client-to-Server Messages

- **[Authorize](./WebSocket_Authorize.md)**: Authenticate the connection.
- **[Pong](./WebSocket_Pong.md)**: Response to server ping for heartbeat.
- **[Chat Message](./WebSocket_ChatMessage.md)**: Send a user's message to the agent.
- **[Interrupt Stream](./WebSocket_InterruptStream.md)**: Interrupt an active response stream.
- **[Fetch Backgrounds](./WebSocket_FetchBackgrounds.md)**: Request list of available background images.
- **[Fetch Avatar Configs](./WebSocket_FetchAvatarConfigs.md)**: Request list of available avatar configurations.
- **[Switch Avatar Config](./WebSocket_SwitchAvatarConfig.md)**: Switch to a different avatar configuration.

### Server-to-Client Messages

- **[Authorize Success](./WebSocket_AuthorizeSuccess.md)**: Confirms successful connection and authorization.
- **[Authorize Error](./WebSocket_AuthorizeError.md)**: Indicates authorization failure.
- **[Ping](./WebSocket_Ping.md)**: Heartbeat message from server.
- **[Stream Start](./WebSocket_StreamStart.md)**: Signals the beginning of an agent's response turn.
- **[Stream Token](./WebSocket_StreamToken.md)**: A piece of the agent's text response.
- **[Stream End](./WebSocket_StreamEnd.md)**: Signals the end of an agent's response turn.
- **[TTS Ready Chunk](./WebSocket_TTSReadyChunk.md)**: A chunk of text ready for TTS synthesis.
- **[Tool Call](./WebSocket_ToolCall.md)**: Informs the client that the agent is using a tool.
- **[Tool Result](./WebSocket_ToolResult.md)**: Provides the result of a tool's execution.
- **[Error Message](./WebSocket_ErrorMessage.md)**: Sent when an error occurs.
- **[Background Files](./WebSocket_BackgroundFiles.md)**: List of available background images.
- **[Avatar Config Files](./WebSocket_AvatarConfigFiles.md)**: List of available avatar configurations.
- **[Avatar Config Switched](./WebSocket_AvatarConfigSwitched.md)**: Confirmation of avatar configuration switch.
- **[Set Model And Conf](./WebSocket_SetModelAndConf.md)**: Server message to set model and configuration.
