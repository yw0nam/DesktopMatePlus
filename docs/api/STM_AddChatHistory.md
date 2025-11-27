# POST /v1/stm/chat-history

Add new messages to a chat session's history.

## Overview

This endpoint allows you to add one or more messages to a chat session. If no `session_id` is provided, a new session will be created. This is useful for manually adding context or restoring a conversation.

## Request

### Method

`POST`

### URL

`/v1/stm/chat-history`

### Query Parameters

None

### Headers

- `Content-Type`: `application/json`

### Body

A JSON object containing the user, agent, session identifiers and an array of messages to add.

```json
{
    "user_id": "user123",
    "agent_id": "agent456",
    "session_id": "optional-session-id",
    "messages": [
        {
            "role": "user",
            "content": "What is the length of the word 'extraordinary'?"
        },
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "type": "function",
                    "id": "chatcmpl-tool-11d1a983d7e241d6b015c804a0fd412d",
                    "function": {
                        "name": "get_word_length",
                        "arguments": "{\"word\": \"extraordinary\"}"
                    }
                }
            ],
            "content": ""
        },
        {
            "role": "tool",
            "name": "get_word_length",
            "tool_call_id": "chatcmpl-tool-11d1a983d7e241d6b015c804a0fd412d",
            "content": "13"
        },
        {
            "role": "assistant",
            "content": "The word \"extraordinary\" has a length of 13 letters."
        },
        {
            "role": "system",
            "content": "You are a helpful AI assistant."
        }
    ]
}
```

## Response

### Success (201 Created)

Returns the session ID and message count.

```json
{
    "session_id": "abc123-def456-ghi789",
    "message_count": 3
}
```

### Error

- **400 Bad Request**: If message validation fails (invalid role, empty content, etc.)
- **503 Service Unavailable**: If STM service is not initialized
- **500 Internal Server Error**: If there is a problem with the memory store.

## Example

### cURL

```bash
curl -X POST "http://127.0.0.1:5500/v1/stm/chat-history" \
     -H "Content-Type: application/json" \
     -d '{
    "user_id": "user123",
    "agent_id": "agent456",
    "messages": [
        {
            "role": "user",
            "content": "What is the weather like today?"
        }
    ]
}'
```

### JavaScript (Fetch API)

```javascript
const userId = 'user123';
const agentId = 'agent456';
const messages = [
    { role: 'user', content: 'What is the weather like today?' }
];

fetch(`http://127.0.0.1:5500/v1/stm/chat-history`, {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        user_id: userId,
        agent_id: agentId,
        messages: messages
    }),
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```
.catch(error => console.error('Error:', error));
```
