# STM: Add Chat History

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Add messages to a chat session's history (creates new session if none specified)
- **I/O**: `POST { user_id, agent_id, session_id?, messages[] }` → `{ session_id, message_count }`

## 2. Core Logic

### Endpoint

`POST /v1/stm/chat-history`

### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | string | Yes | User identifier |
| `agent_id` | string | Yes | Agent identifier |
| `session_id` | string | No | Session ID (new session created if omitted) |
| `messages` | array | Yes | Messages to add (OpenAI-compatible format) |

### Message Roles

| Role | Fields |
|------|--------|
| `user` | `role`, `content` |
| `assistant` | `role`, `content`, `tool_calls?` |
| `tool` | `role`, `name`, `tool_call_id`, `content` |
| `system` | `role`, `content` |

### Response

**Success (201)**:
```json
{ "session_id": "abc123-def456", "message_count": 3 }
```

**Errors**: `400` (validation), `503` (STM not initialized), `500` (internal)

## 3. Usage

```bash
curl -X POST "http://127.0.0.1:5500/v1/stm/chat-history" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "agent_id": "agent456",
    "messages": [{ "role": "user", "content": "Hello!" }]
  }'
```

---

## Appendix

### A. Full Request Example

```json
{
  "user_id": "user123",
  "agent_id": "agent456",
  "session_id": "optional-session-id",
  "messages": [
    { "role": "user", "content": "What is the length of 'extraordinary'?" },
    {
      "role": "assistant",
      "tool_calls": [{
        "type": "function",
        "id": "chatcmpl-tool-abc123",
        "function": { "name": "get_word_length", "arguments": "{\"word\": \"extraordinary\"}" }
      }],
      "content": ""
    },
    { "role": "tool", "name": "get_word_length", "tool_call_id": "chatcmpl-tool-abc123", "content": "13" },
    { "role": "assistant", "content": "The word has 13 letters." }
  ]
}
```

### B. Related Documents

- [Get Chat History](./STM_GetChatHistory.md)
- [REST API Guide](./REST_API_GUIDE.md)
