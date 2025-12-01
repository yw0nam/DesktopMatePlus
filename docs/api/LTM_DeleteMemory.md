# LTM: Delete Memory

Updated: 2025-12-01

## 1. Synopsis

- **Purpose**: Delete a specific memory from Long-Term Memory storage
- **I/O**: `DELETE { user_id, agent_id, memory_id }` → `{ success, message, result }`

## 2. Core Logic

### Endpoint

`DELETE /v1/ltm/delete_memory`

### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | string | Yes | User identifier |
| `agent_id` | string | Yes | Agent identifier |
| `memory_id` | string | Yes | ID of the memory to delete |

### Response

**Success (200)**:

```json
{
  "success": true,
  "message": "Memory deleted successfully.",
  "result": {}
}
```

**Errors**: `503` (LTM not initialized), `500` (internal)

## 3. Usage

```bash
curl -X DELETE "http://127.0.0.1:5500/v1/ltm/delete_memory" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "agent_id": "agent456",
    "memory_id": "memory-uuid-to-delete"
  }'
```

---

## Appendix

### A. Related Documents

- [REST API Guide](./REST_API_GUIDE.md)
- [LTM Service Guide](../feature/service/LTM_Service.md)
