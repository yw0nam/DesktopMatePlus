# PATCH /v1/stm/sessions/{session_id}/metadata

Update the metadata for a specific chat session.

## Overview

This endpoint allows you to modify the metadata associated with a chat session, such as its title or user-defined tags.

## Request

### Method

`PATCH`

### URL

`/v1/stm/sessions/{session_id}/metadata`

### Path Parameters

- `session_id` (string, required): The unique identifier for the chat session.

### Headers

- `Authorization`: `Bearer <Your-Auth-Token>` (Optional)
- `Content-Type`: `application/json`

### Body

A JSON object containing the metadata fields to update.

```json
{
    "metadata": {
        "title": "My Updated Chat Title",
        "tags": ["important", "work"]
    }
}
```

## Response

### Success (200 OK)

Returns a confirmation message.

```json
{
    "message": "Metadata updated successfully"
}
```

### Error

- **404 Not Found**: If no session with the specified `session_id` exists.
- **422 Unprocessable Entity**: If the request body is malformed.
- **401 Unauthorized**: If the authorization token is missing or invalid.
- **500 Internal Server Error**: If there is a problem updating the memory store.

## Example

### cURL

```bash
curl -X PATCH "http://127.0.0.1:5500/v1/stm/sessions/abc123-def456-ghi789/metadata" \
-H "Content-Type: application/json" \
-d '{
    "metadata": {
        "title": "A New Title for an Old Chat",
        "tags": ["important", "work"]
    }
}'
```

### JavaScript (Fetch API)

```javascript
const sessionId = 'abc123-def456-ghi789';
const metadata = {
    metadata: {
        title: 'A New Title for an Old Chat',
        tags: ['important', 'work']
    }
};

fetch(`http://127.0.0.1:5500/v1/stm/sessions/${sessionId}/metadata`, {
    method: 'PATCH',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify(metadata),
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```
