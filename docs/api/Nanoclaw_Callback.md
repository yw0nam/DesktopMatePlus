# Callback: NanoClaw Task Result

Updated: 2026-03-18

## 1. Synopsis

- **Purpose**: Receive task completion/failure from NanoClaw; update STM and optionally route final response to external channel (Slack)
- **I/O**: `POST` `{task_id, status, summary}` → `{task_id, status, message}`

## 2. Core Logic

### Endpoint

`POST /v1/callback/nanoclaw/{session_id}`

### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `session_id` | string | Session that owns the task |

### Request Body

```json
{
  "task_id": "task-abc123",
  "status": "done",
  "summary": "작업 완료 요약"
}
```

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `task_id` | string | — | Task identifier (must match a pending task) |
| `status` | string | `done` \| `failed` | Completion status |
| `summary` | string | — | Human-readable result summary |

### Response

**Success (200)**:
```json
{
  "task_id": "task-abc123",
  "status": "done",
  "message": "Task task-abc123 updated to done"
}
```

**Errors**: `404` (task not found in session), `503` (STM not initialized)

### Processing Flow

1. Look up `pending_tasks` in session metadata
2. Update matched task's `status` field
3. Inject synthetic `SystemMessage` into STM chat history:
   - `done` → `[TaskResult:task-id] summary`
   - `failed` → `[TaskFailed:task-id] summary`
4. If `reply_channel` is set in session metadata → fire `asyncio.create_task(process_message(text="", ...))`
   - `process_message` with empty text skips adding a new `HumanMessage`; the synthetic TaskResult already in STM drives the agent response
   - Agent reply is sent to `reply_channel.channel_id` via `SlackService.send_message`

### reply_channel Metadata

Set by `process_message` on first Slack message. Structure:
```json
{
  "provider": "slack",
  "channel_id": "C5678"
}
```

WebSocket sessions do not set `reply_channel`; callback only triggers external delivery when this field is present.

## 3. Usage

```bash
# NanoClaw reports task completion
curl -X POST http://127.0.0.1:5500/v1/callback/nanoclaw/slack:T1:C1:U1 \
  -H "content-type: application/json" \
  -d '{"task_id":"task-xyz","status":"done","summary":"분석 완료. 결과: 3개 항목 발견"}'
# Response: {"task_id":"task-xyz","status":"done","message":"Task task-xyz updated to done"}
```

---

## Appendix

### A. Related Documents

- [REST API Guide](./REST_API_GUIDE.md)
- [Slack Events Webhook](./Slack_Events.md)
