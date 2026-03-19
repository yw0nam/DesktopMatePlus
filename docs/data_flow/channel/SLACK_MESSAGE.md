# SLACK_MESSAGE Data Flow

Updated: 2026-03-19

## Overview

Slack channel 메시지 처리에는 두 가지 경로가 있다.

1. **Direct Flow** — 에이전트가 즉시 응답 (delegation 없음)
2. **Delegation Flow** — 에이전트가 NanoClaw에 작업을 위임하고, 완료 후 콜백으로 응답

세션 ID 형식: `slack:{team_id}:{channel_id}:{user_id}` (현재 `user_id`는 상수 `"default"`)

---

## Flow 1: Direct Message (No Delegation)

```mermaid
sequenceDiagram
    actor User as User (Slack)
    participant Slack as Slack Server
    participant BE as Backend (FastAPI)
    participant STM as STM Service
    participant LTM as LTM Service
    participant Agent as AgentService

    User->>Slack: Send message in channel
    Slack->>BE: POST /v1/channels/slack/events<br/>(x-slack-signature, x-slack-request-timestamp)

    activate BE
    BE->>BE: Verify HMAC-SHA256 signature<br/>& timestamp freshness (±5min)

    alt Invalid signature or stale timestamp
        BE-->>Slack: 403 Forbidden
    end

    BE->>BE: Parse event<br/>(skip: bot message, subtype, non-message type)
    BE-->>Slack: 200 {"ok": true}  ← immediate return

    Note over BE: asyncio.create_task(process_message(...))
    deactivate BE

    activate BE
    BE->>BE: Acquire session_lock(session_id)<br/>(TTL 600s — prevents concurrent processing)
    BE->>STM: upsert_session(session_id, user_id, agent_id)
    BE->>STM: update_session_metadata<br/>({user_id, agent_id, reply_channel: {provider, channel_id}})
    BE->>STM: load_context → STM chat history
    BE->>LTM: load_context → LTM prefix (relevant memories)

    BE->>Agent: invoke(context + HumanMessage(text), session_id, persona_id)
    Agent-->>BE: {content, new_chats}

    BE->>STM: save_turn(HumanMessage + new_chats)<br/>(asyncio.create_task — non-blocking)
    BE->>LTM: save_turn(...) — same task

    BE->>Slack: SlackService.send_message(channel_id, content)
    deactivate BE

    Slack-->>User: Display AI reply
```

---

## Flow 2: Delegation Flow (NanoClaw Task)

에이전트가 `DelegateTaskTool`을 사용해 NanoClaw에 작업을 위임하는 경우.

```mermaid
sequenceDiagram
    actor User as User (Slack)
    participant Slack as Slack Server
    participant BE as Backend (FastAPI)
    participant STM as STM Service
    participant LTM as LTM Service
    participant Agent as AgentService
    participant NC as NanoClaw

    User->>Slack: Send message in channel
    Slack->>BE: POST /v1/channels/slack/events
    BE->>BE: Verify signature, parse event
    BE-->>Slack: 200 {"ok": true}  ← immediate return

    activate BE
    Note over BE: asyncio.create_task(process_message(...))
    BE->>BE: Acquire session_lock(session_id)
    BE->>STM: upsert_session + update_session_metadata<br/>(reply_channel 저장됨)
    BE->>STM: load_context → history
    BE->>LTM: load_context → memories

    BE->>Agent: invoke(context + HumanMessage(text), ...)
    Note right of Agent: Agent decides to delegate
    Agent->>NC: POST /api/webhooks/fastapi<br/>(DelegateTaskTool — task payload)
    NC-->>Agent: {task_id} acknowledged
    Agent-->>BE: {content: "작업 중...", new_chats: [AIMessage + ToolMessages]}

    BE->>STM: save_turn(HumanMessage + new_chats)<br/>(non-blocking)
    BE->>Slack: send_message(channel_id, "작업 중...")
    deactivate BE

    Note over NC: NanoClaw executes task asynchronously

    NC->>BE: POST /v1/callback/nanoclaw/{session_id}<br/>{task_id, status: "done", summary}

    activate BE
    BE->>STM: get_session_metadata → pending_tasks
    BE->>STM: update pending_tasks[task_id].status = "done"
    BE->>STM: add_chat_history([SystemMessage("[TaskResult:task_id] summary")])

    Note over BE: reply_channel found in metadata
    Note over BE: asyncio.create_task(process_message(text="", ...))
    BE-->>NC: 200 {task_id, status, message}
    deactivate BE

    activate BE
    BE->>BE: Acquire session_lock(session_id)
    BE->>STM: upsert_session + update_session_metadata
    BE->>STM: load_context → history (now includes TaskResult SystemMessage)
    BE->>LTM: load_context → memories

    Note over BE: text="" → HumanMessage 추가 안 함<br/>TaskResult가 이미 STM에 있어 에이전트가 이를 기반으로 응답
    BE->>Agent: invoke(context, ...)  ← no HumanMessage
    Agent-->>BE: {content: "최종 결과...", new_chats}

    BE->>STM: save_turn(new_chats)  ← HumanMessage 없이 저장
    BE->>LTM: save_turn(...)

    BE->>Slack: send_message(channel_id, "최종 결과...")
    deactivate BE

    Slack-->>User: Display final AI reply
```

---

## Flow 3: URL Verification (App Setup, One-Time)

```mermaid
sequenceDiagram
    participant Slack as Slack Server
    participant BE as Backend (FastAPI)

    Slack->>BE: POST /v1/channels/slack/events<br/>{type: "url_verification", challenge: "abc123"}
    BE->>BE: Verify signature
    BE-->>Slack: 200 {"challenge": "abc123"}
```

---

## Key Implementation Details

### Signature Verification

- Algorithm: HMAC-SHA256 over `v0:{timestamp}:{body}`
- Timestamp tolerance: ±5 minutes (replay attack prevention)
- Comparison: `hmac.compare_digest` (timing-safe)

### Session Lock

- `session_lock(session_id)`: `cachetools.TTLCache` 기반 async context manager
- TTL: 600s, maxsize: 1024
- 동일 세션의 동시 처리를 방지한다 (예: 빠른 연속 메시지, callback 재진입)

### reply_channel Metadata

- `process_message()` 최초 호출 시 STM session metadata에 저장됨:
  ```json
  {"provider": "slack", "channel_id": "C5678"}
  ```
- Callback 핸들러가 이 값을 확인해 Slack 라우팅 결정
- WebSocket 세션에는 `reply_channel`이 없으므로 콜백 시 외부 전송 없음

### process_message `text=""` 경로 (Callback)

- `text`가 비어있으면 `HumanMessage`를 추가하지 않음
- STM에 이미 주입된 `[TaskResult:task_id]` `SystemMessage`가 에이전트 응답을 구동
- `save_turn` 시에도 `HumanMessage` 없이 `new_chats`만 저장

### Error Handling

- `process_message` 예외 시 Slack으로 에러 메시지 전송: `"처리 중 오류가 발생했어. 다시 시도해줘"`
- 에러는 백그라운드 태스크에서 발생하므로 Slack에 `{"ok": true}`가 이미 반환된 이후

---

## Appendix

- [Slack Events API Doc](../../../docs/api/Slack_Events.md)
- [NanoClaw Callback Doc](../../../docs/api/Nanoclaw_Callback.md)
- [ADD_CHAT_MESSAGE Data Flow](../chat/ADD_CHAT_MESSAGE.md)
