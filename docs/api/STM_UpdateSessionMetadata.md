# STM: Update Session Metadata

Updated: 2026-03-18

## 1. Synopsis

- **Purpose**: Update metadata (title, tags) for a chat session
- **I/O**: `PATCH /{session_id}/metadata { metadata }` → `{ message }`

## 2. Core Logic

### Endpoint

`PATCH /v1/stm/sessions/{session_id}/metadata`

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | Yes | Session identifier |

### Request Body

```json
{
  "metadata": {
    "title": "Updated Title",
    "tags": ["important", "work"]
  }
}
```

### Response

**Success (200)**:
```json
{ "message": "Metadata updated successfully" }
```

**Errors**: `400` (invalid input), `404` (not found), `503` (STM not initialized), `500` (internal)

## 3. Usage

```bash
curl -X PATCH "http://127.0.0.1:5500/v1/stm/sessions/abc123/metadata" \
  -H "Content-Type: application/json" \
  -d '{ "metadata": { "title": "New Title" } }'
```

---

## Appendix

### A. Related Documents

- [List Sessions](./STM_ListSessions.md)
- [Delete Session](./STM_DeleteSession.md)
