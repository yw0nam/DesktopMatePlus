# Channels: Slack Events Webhook

Updated: 2026-03-18

## 1. Synopsis

- **Purpose**: Receive Slack Events API webhooks; queue message processing and return immediately
- **I/O**: `POST` Slack-signed JSON payload → `{"ok": true}` (or challenge response)

## 2. Core Logic

### Endpoint

`POST /v1/channels/slack/events`

### Headers

| Header | Required | Description |
|--------|----------|-------------|
| `x-slack-signature` | Yes | HMAC-SHA256 signature (`v0=...`) |
| `x-slack-request-timestamp` | Yes | Unix timestamp (rejected if >5min old) |
| `content-type` | Yes | `application/json` |

### Request Body

Slack Events API JSON payload. Two event types handled:

**URL Verification** (one-time during app setup):
```json
{ "type": "url_verification", "challenge": "abc123" }
```

**Event Callback** (recurring messages):
```json
{
  "type": "event_callback",
  "team_id": "T1234",
  "event": {
    "type": "message",
    "text": "안녕 유리",
    "channel": "C5678",
    "user": "U9012"
  }
}
```

### Response

**URL Verification (200)**:
```json
{ "challenge": "abc123" }
```

**Message queued (200)**:
```json
{ "ok": true }
```

**Ignored event (200)** — bot message, message subtype, or non-message type:
```json
{ "ok": true }
```

**Errors**: `403` (invalid signature), `503` (Slack service not initialized)

### Processing Flow

1. Verify HMAC-SHA256 signature and timestamp freshness
2. For `url_verification`: return challenge immediately
3. Parse event — skip if bot message, has `subtype`, or non-message type
4. Fire `asyncio.create_task(process_message(...))` and return `{"ok": true}`

`process_message` runs in the background:
- Acquires per-session lock (TTL 600s)
- Loads STM + LTM context
- Invokes agent
- Sends reply via `SlackService.send_message(channel_id, text)`

### Session ID Format

```
slack:{team_id}:{channel_id}:{user_id}
```

Example: `slack:T1234:C5678:U9012`

## 3. Usage

```bash
# URL verification (Slack calls this automatically)
curl -X POST http://127.0.0.1:5500/v1/channels/slack/events \
  -H "x-slack-signature: v0=..." \
  -H "x-slack-request-timestamp: 1234567890" \
  -H "content-type: application/json" \
  -d '{"type":"url_verification","challenge":"test-challenge"}'
# Response: {"challenge":"test-challenge"}

# Incoming message event
curl -X POST http://127.0.0.1:5500/v1/channels/slack/events \
  -H "x-slack-signature: v0=..." \
  -H "x-slack-request-timestamp: 1234567890" \
  -H "content-type: application/json" \
  -d '{"type":"event_callback","team_id":"T1","event":{"type":"message","text":"hello","channel":"C1","user":"U1"}}'
# Response: {"ok":true}
```

---

## Appendix

### A. Related Documents

- [REST API Guide](./REST_API_GUIDE.md)
- [NanoClaw Callback](./Nanoclaw_Callback.md)
