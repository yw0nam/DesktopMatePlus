# GET /v1/stm/sessions

List all available chat sessions.

## Overview

This endpoint retrieves a list of all chat sessions stored in the Short-Term Memory (STM). Each session in the list includes its unique identifier and metadata.

## Request

### Method

`GET`

### URL

`/v1/stm/sessions`

### Query Parameters

- `user_id` (string, required): User identifier
- `agent_id` (string, required): Agent identifier

- `Authorization`: `Bearer <Your-Auth-Token>` (Optional, depending on configuration)

## Response

### Success (200 OK)

Returns a JSON object containing a list of session objects.

```json
{
    "sessions": [
        {
            "session_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
            "user_id": "user-123",
            "agent_id": "agent-001",
            "created_at": "2025-11-10T10:00:00Z",
            "updated_at": "2025-11-10T10:05:00Z",
            "metadata": {
                "title": "My First Chat"
            }
        },
        {
            "session_id": "b2c3d4e5-f6a7-8901-2345-67890abcdef1",
            "user_id": "user-123",
            "agent_id": "agent-001",
            "created_at": "2025-11-11T12:30:00Z",
            "updated_at": "2025-11-11T12:35:00Z",
            "metadata": {
                "title": "Exploring Agent Capabilities"
            }
        }
    ]
}
```

### Error

- **401 Unauthorized**: If the authorization token is missing or invalid.
- **500 Internal Server Error**: If there is a problem accessing the memory store.

## Example

### cURL

```bash
curl -X GET "http://127.0.0.1:5500/v1/stm/sessions?user_id=user123&agent_id=agent456"
```

### JavaScript (Fetch API)

```javascript
const userId = 'user123';
const agentId = 'agent456';

fetch(`http://127.0.0.1:5500/v1/stm/sessions?user_id=${userId}&agent_id=${agentId}`)
    .then(response => response.json())
    .then(data => console.log(data))
    .catch(error => console.error('Error:', error));
```
