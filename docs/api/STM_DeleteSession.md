# STM: Delete Session

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Permanently delete a chat session and all its messages
- **I/O**: `DELETE /{session_id}?user_id&agent_id` → `{ success, message }`

## 2. Core Logic

### Endpoint

`DELETE /v1/stm/sessions/{session_id}`

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | Yes | Session identifier |

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | string | Yes | User identifier |
| `agent_id` | string | Yes | Agent identifier |

### Response

**Success (200)**:
```json
{ "success": true, "message": "Session deleted successfully" }
```

**Errors**: `404` (not found), `401` (unauthorized), `500` (internal)

## 3. Usage

```bash
curl -X DELETE "http://127.0.0.1:5500/v1/stm/sessions/abc123?user_id=user123&agent_id=agent456"
```

---

## Appendix

### A. Important Notes

- This action is **irreversible**
- All associated messages are permanently removed

### B. Related Documents

- [List Sessions](./STM_ListSessions.md)
- [Update Session Metadata](./STM_UpdateSessionMetadata.md)
