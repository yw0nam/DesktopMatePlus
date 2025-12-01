# LTM: Search Memory

Updated: 2025-12-01

## 1. Synopsis

- **Purpose**: Search memories in Long-Term Memory storage using semantic search
- **I/O**: `POST { user_id, agent_id, query }` → `{ success, result }`

## 2. Core Logic

### Endpoint

`POST /v1/ltm/search_memory`

### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | string | Yes | User identifier |
| `agent_id` | string | Yes | Agent identifier |
| `query` | string | Yes | Search query string |

### Response

**Success (200)**:
```json
{
  "success": true,
  "result": {
    "results": [
      {
        "id": "memory-uuid",
        "memory": "Memory content text",
        "score": 0.85,
        "user_id": "user123",
        "agent_id": "agent456",
        "created_at": "2025-12-01T10:00:00Z"
      }
    ],
    "relations": [
      {
        "source": "entity1",
        "relationship": "related_to",
        "destination": "entity2"
      }
    ]
  }
}
```

**Errors**: `503` (LTM not initialized), `500` (internal)

## 3. Usage

```bash
curl -X POST "http://127.0.0.1:5500/v1/ltm/search_memory" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "agent_id": "agent456",
    "query": "What do I like?"
  }'
```

---

## Appendix

### A. Related Documents

- [REST API Guide](./REST_API_GUIDE.md)
- [LTM Service Guide](../feature/service/LTM_Service.md)
