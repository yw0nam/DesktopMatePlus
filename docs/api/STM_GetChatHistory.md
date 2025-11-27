# GET /v1/stm/chat-history

Retrieve the chat history for a specific session.

## Overview

This endpoint fetches messages associated with a given session. The messages are returned in chronological order and follow OpenAI-compatible format.

## Request

### Method

`GET`

### URL

`/v1/stm/chat-history`

### Query Parameters

- `user_id` (string, required): User identifier
- `agent_id` (string, required): Agent identifier
- `session_id` (string, required): Session identifier
- `limit` (integer, optional): Maximum number of recent messages to retrieve

### Headers

None required

## Response

### Success (200 OK)

Returns a JSON object representing the session's chat history.

```json
{
    "session_id": "abc123-def456-ghi789",
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

### Error

- **503 Service Unavailable**: If STM service is not initialized
- **500 Internal Server Error**: If there is a problem accessing the memory store.

## Example

### cURL

```bash
curl -X GET "http://127.0.0.1:5500/v1/stm/chat-history?user_id=user123&agent_id=agent456&session_id=abc123-def456-ghi789"
```

### JavaScript (Fetch API)

```javascript
const userId = 'user123';
const agentId = 'agent456';
const sessionId = 'abc123-def456-ghi789';

fetch(`http://127.0.0.1:5500/v1/stm/chat-history?user_id=${userId}&agent_id=${agentId}&session_id=${sessionId}`)
    .then(response => response.json())
    .then(data => console.log(data))
    .catch(error => console.error('Error:', error));
```
