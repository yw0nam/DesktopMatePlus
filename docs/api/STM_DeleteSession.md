# DELETE /v1/stm/sessions/{session_id}

Delete a chat session and its entire history.

## Overview

This endpoint permanently removes a chat session and all associated messages from the Short-Term Memory (STM). This action is irreversible.

## Request

### Method

`DELETE`

### URL

`/v1/stm/sessions/{session_id}`

### Path Parameters

- `session_id` (string, required): The unique identifier for the chat session.

### Query Parameters

- `user_id` (string, required): User identifier
- `agent_id` (string, required): Agent identifier

### Headers

- `Authorization`: `Bearer <Your-Auth-Token>` (Optional)

## Response

### Success (200 OK)

Returns a confirmation message indicating that the session was successfully deleted.

```json
{
    "success": true,
    "message": "Session deleted successfully"
}
```

### Error

- **404 Not Found**: If no session with the specified `session_id` exists.
- **401 Unauthorized**: If the authorization token is missing or invalid.
- **500 Internal Server Error**: If there is a problem deleting the data from the memory store.

## Example

### cURL

```bash
curl -X DELETE "http://127.0.0.1:5500/v1/stm/sessions/abc123-def456-ghi789?user_id=user123&agent_id=agent456"
```

### JavaScript (Fetch API)

```javascript
const sessionId = 'abc123-def456-ghi789';
const userId = 'user123';
const agentId = 'agent456';

fetch(`http://127.0.0.1:5500/v1/stm/sessions/${sessionId}?user_id=${userId}&agent_id=${agentId}`, {
    method: 'DELETE',
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```
