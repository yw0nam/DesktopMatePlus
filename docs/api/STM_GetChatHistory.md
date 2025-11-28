# STM: Get Chat History

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Retrieve chat history for a specific session
- **I/O**: `GET ?user_id&agent_id&session_id&limit?` → `{ session_id, messages[] }`

## 2. Core Logic

### Endpoint

`GET /v1/stm/chat-history`

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | string | Yes | User identifier |
| `agent_id` | string | Yes | Agent identifier |
| `session_id` | string | Yes | Session identifier |
| `limit` | integer | No | Max messages to retrieve |

### Response

**Success (200)**:
```json
{
  "session_id": "abc123-def456",
  "messages": [
    { "role": "user", "content": "Hello!" },
    { "role": "assistant", "content": "Hi there!" }
  ]
}
```

**Errors**: `503` (STM not initialized), `500` (internal)

## 3. Usage

```bash
curl "http://127.0.0.1:5500/v1/stm/chat-history?user_id=user123&agent_id=agent456&session_id=abc123"
```

---

## Appendix

### A. Message Format

Messages follow OpenAI-compatible format with roles: `user`, `assistant`, `tool`, `system`.

### B. Related Documents

- [Add Chat History](./STM_AddChatHistory.md)
- [List Sessions](./STM_ListSessions.md)
