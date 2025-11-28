# STM: List Sessions

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Retrieve all chat sessions for a user/agent pair
- **I/O**: `GET ?user_id&agent_id` → `{ sessions[] }`

## 2. Core Logic

### Endpoint

`GET /v1/stm/sessions`

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | string | Yes | User identifier |
| `agent_id` | string | Yes | Agent identifier |

### Response

**Success (200)**:
```json
{
  "sessions": [
    {
      "session_id": "a1b2c3d4-e5f6-7890",
      "user_id": "user-123",
      "agent_id": "agent-001",
      "created_at": "2025-11-10T10:00:00Z",
      "updated_at": "2025-11-10T10:05:00Z",
      "metadata": { "title": "My First Chat" }
    }
  ]
}
```

**Errors**: `401` (unauthorized), `500` (internal)

## 3. Usage

```bash
curl "http://127.0.0.1:5500/v1/stm/sessions?user_id=user123&agent_id=agent456"
```

---

## Appendix

### A. Related Documents

- [Get Chat History](./STM_GetChatHistory.md)
- [Delete Session](./STM_DeleteSession.md)
