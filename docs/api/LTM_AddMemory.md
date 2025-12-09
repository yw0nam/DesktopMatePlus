# LTM: Add Memory

Updated: 2025-12-01

## 1. Synopsis

- **Purpose**: Add memory to Long-Term Memory storage
- **I/O**: `POST { user_id, agent_id, memory_dict }` → `{ success, message, result }`

## 2. Core Logic

### Endpoint

`POST /v1/ltm/add_memory`

### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | string | Yes | User identifier |
| `agent_id` | string | Yes | Agent identifier |
| `memory_dict` | array \| string | Yes | Memory content (list of role-content dicts or plain string) |

### Memory Dict Format

**Option 1: List of role-content dicts**
```json
[
  {"role": "user", "content": "I like apples."},
  {"role": "assistant", "content": "Understood. Apples are a good fruit."}
]
```

**Option 2: Plain string**
```json
"This is a memory string."
```

### Response

**Success (200)**:
```json
{
  "success": true,
  "message": "Memory added successfully.",
  "result": {
    "results": [...],
    "relations": [...]
  }
}
```

**Errors**: `400` (invalid format), `503` (LTM not initialized), `500` (internal)

## 3. Usage

- Note, request url can be varying based on your server address and port.

```bash
curl -X POST "http://127.0.0.1:5500/v1/ltm/add_memory" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "agent_id": "agent456",
    "memory_dict": [
      {"role": "user", "content": "My name is John."},
      {"role": "assistant", "content": "Nice to meet you, John!"}
    ]
  }'
```

---

## Appendix

### A. Related Documents

- [REST API Guide](./REST_API_GUIDE.md)
- [LTM Service Guide](../feature/service/LTM_Service.md)
