# WebSocket Message Examples

This document provides examples of WebSocket messages for DesktopMate+ client-server communication.

## Client Messages

### Authorization Message
```json
{
  "type": "authorize",
  "token": "your_auth_token_here"
}
```

### Chat Message (with persistent identifiers)
```json
{
  "type": "chat_message",
  "content": "Hello, can you help me with my task?",
  "agent_id": "desktop-assistant-v1",
  "user_id": "user_12345",
  "metadata": {
    "conversation_id": "conv_67890",
    "timestamp": 1698451200,
    "client_version": "1.0.0"
  }
}
```

### Interrupt Stream Message
```json
{
  "type": "interrupt_stream",
  "turn_id": "optional_specific_turn_id"
}
```

### Pong Message (heartbeat response)
```json
{
  "type": "pong",
  "timestamp": 1698451200
}
```

## Server Messages

### Authorization Success
```json
{
  "type": "authorize_success",
  "connection_id": "01234567-89ab-cdef-0123-456789abcdef"
}
```

### Authorization Error
```json
{
  "type": "authorize_error",
  "error": "Invalid authentication token"
}
```

### Chat Response
```json
{
  "type": "chat_response",
  "content": "I'd be happy to help you with your task. What specific assistance do you need?",
  "metadata": {
    "turn_id": "turn_98765",
    "conversation_id": "conv_67890",
    "timestamp": 1698451220
  }
}
```

### Ping Message (heartbeat)
```json
{
  "type": "ping",
  "timestamp": 1698451200
}
```

### Error Message
```json
{
  "type": "error",
  "error": "Message processing failed",
  "code": 500
}
```

## Important Notes

### Persistent Identifiers

**agent_id**: This should be a persistent identifier for the AI agent instance. This allows the memory tool to maintain context across different WebSocket connections and sessions. Examples:
- `"desktop-assistant-v1"`
- `"natsume-assistant"`
- `"personal-ai-companion"`

**user_id**: This should be a persistent identifier for the user/client. This allows the memory tool to maintain user-specific context across different sessions. Examples:
- `"user_12345"`
- `"alex_smith"`
- `"client_abc123"`

### Connection vs Session Identifiers

- **connection_id**: Temporary identifier unique to each WebSocket connection (changes on reconnect)
- **user_id**: Persistent identifier for the user (remains same across reconnections)
- **agent_id**: Persistent identifier for the AI agent (remains same across reconnections)
- **conversation_id**: Persistent identifier for a conversation thread (can span multiple connections)
- **turn_id**: Unique identifier for each message exchange within a conversation

### Required Fields

For chat messages, both `agent_id` and `user_id` are **required** fields. The server will reject chat messages that don't include these persistent identifiers.
