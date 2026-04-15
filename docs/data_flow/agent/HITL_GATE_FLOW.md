# HitL Gate Data Flow

Updated: 2026-04-15

## 1. Synopsis

- **Purpose**: 위험 도구(MCP 도구, `delegate_task`) 호출 시 사용자 승인 게이트를 거쳐 실행 여부를 결정하는 흐름
- **I/O**: Agent tool call → `interrupt()` → FE 승인 UI → `hitl_response` → 도구 실행 또는 거부

## 2. Core Logic

### 2-1. 도구 분류

| 분류 | 도구 | HitL 필요 |
|------|------|:---:|
| **Safe** | `search_memory`, `update_user_profile` 등 빌트인 도구 | ❌ |
| **Dangerous** | 모든 MCP 도구 (동적, init 시 등록) | ✅ |
| **Dangerous** | `delegate_task` (NanoClaw 위임) | ✅ |
| **Dangerous** | Static deny-list 도구 (Phase 1: 비어있음) | ✅ |

분류 로직: `HitLMiddleware.is_dangerous(tool_name)` — MCP 도구 이름 + `delegate_task` + deny-list를 합친 frozenset으로 판단.

### 2-2. HitL 요청 흐름

```
Agent tool call (dangerous)
  → HitLMiddleware.awrap_tool_call()
    → interrupt({tool_name, tool_args, request_id})
      → GraphInterrupt 예외 발생 (LangGraph runtime가 catch)
      → Graph suspended at checkpoint
  → event_handlers: hitl_request 이벤트 감지
    → TurnStatus.AWAITING_APPROVAL 설정
    → hitl_request → event_queue → FE 전달
    → token_queue에 SENTINEL 전송
    → Producer exit (return) — graph 재개 대기
```

### 2-3. FE 승인 → 재개 흐름

```
FE: hitl_request 수신 (tool_name, tool_args, request_id)
  → 승인 UI 표시 (사용자에게 "이 도구 실행을 허용하시겠습니까?")
  → 사용자 응답:
    ├─ 승인: hitl_response (request_id, approved=true)
    │   → handlers.handle_hitl_response()
    │     → TurnStatus.PROCESSING 변경
    │     → agent_service.resume_after_approval(session_id, approved, request_id)
    │     → Command(resume={approved: true}) → graph 재개
    │     → processor.attach_agent_stream(turn_id, agent_stream)
    │     → forward_events 재시작 → stream_start → stream_token → ...
    │
    └─ 거부: hitl_response (request_id, approved=false)
        → resume_value={approved: false}
        → HitLMiddleware: "사용자가 '{tool_name}' 도구 실행을 거부했습니다." 반환
        → Agent가 대체 방법 시도 → 정상 stream_end
```

### 2-4. 가드 조건

`handle_hitl_response()` 진입 시 검증:

1. Connection 존재 + message_processor 있음
2. Active turn 존재 (_current_turn_id not None)
3. Turn 상태가 `AWAITING_APPROVAL` 임
4. AgentService 사용 가능

실패 시 `ErrorMessage` (code 4004) 반환.

## 3. 전체 시퀀스

```mermaid
sequenceDiagram
    participant FE as Client (FE)
    participant WS as WebSocket Handler
    participant MP as MessageProcessor
    participant EH as EventHandler
    participant Agent as LangGraph Agent
    participant HitL as HitLMiddleware
    participant Tool as Target Tool

    Note over FE, Tool: Phase 1: HitL Request
    Agent->>HitL: awrap_tool_call(dangerous_tool)
    HitL->>HitL: interrupt({tool_name, args, request_id})
    HitL-->>Agent: GraphInterrupt (suspend)
    Agent-->>EH: hitl_request event
    EH->>MP: update_turn_status(AWAITING_APPROVAL)
    EH->>MP: _put_event(hitl_request)
    EH->>EH: signal_token_stream_closed
    EH->>EH: wait_for_token_queue
    EH-->>EH: return (producer exit)
    MP-->>WS: hitl_request via event_queue
    WS-->>FE: hitl_request (tool_name, tool_args, request_id)

    Note over FE, Tool: Phase 2: FE Approval UI
    FE->>FE: Show approval dialog to user
    opt User approves
        FE->>WS: hitl_response (request_id, approved=true)
        WS->>WS: handle_hitl_response()
        WS->>MP: update_turn_status(PROCESSING)
        WS->>Agent: resume_after_approval(session_id, approved, request_id)
        Agent->>HitL: Command(resume={approved: true})
        HitL->>Tool: handler(request) — execute tool
        Tool-->>Agent: tool result
        Agent-->>EH: stream_token / stream_end (resume)
        EH->>MP: _put_event(stream_token)
        MP-->>WS: event_queue → client
        WS-->>FE: stream_token / stream_end
    else User denies
        FE->>WS: hitl_response (request_id, approved=false)
        WS->>WS: handle_hitl_response()
        WS->>Agent: resume_after_approval(session_id, approved=false)
        Agent->>HitL: Command(resume={approved: false})
        HitL-->>Agent: "사용자가 도구 실행을 거부했습니다."
        Agent-->>EH: stream_token (denial message) → stream_end
        EH->>MP: _put_event(stream_token)
        MP-->>WS: event_queue → client
        WS-->>FE: stream_token / stream_end
    end
```

## 3. Usage

### FE → hitl_response 메시지 형식

```json
{
  "type": "hitl_response",
  "request_id": "uuid-from-hitl_request",
  "approved": true
}
```

### hitl_request 메시지 형식 (FE 수신)

```json
{
  "type": "hitl_request",
  "tool_name": "delegate_task",
  "tool_args": { "task": "..." },
  "request_id": "uuid",
  "turn_id": "uuid"
}
```

---

## Appendix

### A. 주요 구현 파일

| 파일 | 역할 |
|------|------|
| `src/services/agent_service/middleware/hitl_middleware.py` | HitLMiddleware — interrupt() + resume_value 처리 |
| `src/services/agent_service/openai_chat_agent.py` | resume_after_approval() — Command(resume=...) 생성 |
| `src/services/websocket_service/message_processor/event_handlers.py` | hitl_request 이벤트 처리, producer exit |
| `src/services/websocket_service/message_processor/models.py` | TurnStatus.AWAITING_APPROVAL |
| `src/services/websocket_service/manager/handlers.py` | handle_hitl_response() — FE 응답 라우팅 |

### B. Middleware Chain Order

```
ToolGate → Delegate → LTM → Profile → Summary → TaskStatus → HitL
```

HitL은 chain 마지막에 위치 — 모든 다른 middleware가 tool call 전에 실행된 후 최종 게이트로 동작.

### C. 제약 사항

- **LangGraph checkpoint 필요**: `interrupt()`는 LangGraph의 checkpoint 기능이 활성화된 상태에서만 동작
- **단일 HitL per turn**: 동시 다중 HitL 요청은 지원하지 않음 (Phase 1 MVP 제한)
- **Timeout 없음**: FE가 응답하지 않으면 graph는 indefinitely suspended 상태 (FE reconnect 시 재시도 필요)

### D. PatchNote

2026-04-15: 최초 작성. PR #36 (feat: Human-in-the-Loop approval gate) 기반.
