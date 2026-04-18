# HITL Gate Data Flow

Updated: 2026-04-18

## 1. Synopsis

- **Purpose**: 위험 도구(MCP, `delegate_task`, FS mutating) 호출 시 LangChain 빌트인 `HumanInTheLoopMiddleware` 로 사용자 승인 게이트를 거쳐 실행 여부를 결정한다.
- **I/O**: Agent tool call → graph `interrupt` → FE 승인 UI → `hitl_response(decisions)` → approve / edit / reject 분기로 재개

## 2. Core Logic

### 2-1. 도구 분류

| 분류 | 도구 | HITL 필요 |
|------|------|:---:|
| **Safe** | `read_file`, `list_directory`, `file_search`, `search_memory`, `update_user_profile` | ❌ |
| **Gated** | 모든 MCP 도구 (init 시 `_mcp_tools` 로부터 동적 추출) | ✅ |
| **Gated** | `delegate_task` (NanoClaw 위임) | ✅ |
| **Gated** | FS mutating: `_FS_MUTATING_TOOLS` = {`write_file`, `copy_file`, `move_file`, `file_delete`, `edit_file`} | ✅ |

분류는 서버가 agent init 시 `_build_interrupt_on(mcp_names)` 로 빌드한 `{tool_name: True}` matrix 를 `HumanInTheLoopMiddleware(interrupt_on=...)` 에 주입하여 정해진다. Safe 도구는 matrix 에 없으므로 미들웨어를 그대로 통과한다.

### 2-2. HITL Request 흐름

```
Agent tool call (gated)
  → HumanInTheLoopMiddleware 가 interrupt() 발생
    → Graph suspended at checkpoint (Mongo)
  → openai_chat_agent._stream_internal():
    Interrupt 값에서 action_requests / review_configs 를 추출하여
    {"type": "hitl_request", "action_requests": [...], "review_configs": [...]} 이벤트 yield
  → event_handlers.produce_agent_events():
    TurnStatus.AWAITING_APPROVAL 로 전환
    turn.metadata["pending_action_count"] = len(action_requests)
    hitl_request → event_queue → FE 전달 후 producer exit
```

### 2-3. FE 응답 → 재개 흐름

```
FE: hitl_request 수신 → 각 action_request 에 대해 UI 렌더
  → 사용자가 approve / edit / reject 선택 (review_configs.allowed_decisions 기준)
  → hitl_response (decisions: list, action_requests 순서와 1:1 대응)
    → handlers.handle_hitl_response():
      HitLResponseMessage 로 Pydantic 검증
      len(decisions) == turn.metadata["pending_action_count"] 확인
      TurnStatus.PROCESSING 으로 전환
      agent_service.resume_after_approval(session_id, decisions=[dict,...])
        → LangGraph Command(resume=decisions) 로 그래프 재개
    → 빌트인 미들웨어가 decision.type 별로 분기:
      approve: 원본 tool 그대로 실행
      edit:    edited_action.args 로 tool 실행
      reject:  tool 을 실행하지 않고 message(혹은 기본 거부 메시지) 반환
    → 재개된 stream_token / stream_end 이벤트를 event_queue 로 forward
```

### 2-4. 가드 조건 & 에러

`handle_hitl_response` 진입 시 다음을 모두 검증하고 실패 시 `ErrorMessage(code=4004)` 로 응답한다.

1. Connection + message_processor 존재
2. `_current_turn_id` 존재
3. Turn status == `AWAITING_APPROVAL`
4. `HitLResponseMessage.model_validate` 통과 (`edit` 은 `edited_action` 필수, `approve` 는 부가 필드 금지)
5. `len(decisions) == turn.metadata["pending_action_count"]`
6. `get_agent_service()` 가 None 이 아님

`decisions` 개수 불일치 시에는 상태를 `AWAITING_APPROVAL` 로 유지하여 클라이언트 재시도를 허용한다.

### 2-5. WebSocket 연결 끊김 처리

FE 가 승인 중 연결을 끊으면 `processor.handle_interrupt()` 가 `AWAITING_APPROVAL` 턴을 감지해 `pending_action_count` 만큼 `{"type": "reject"}` decision 을 생성하여 `resume_after_approval` 로 graph checkpoint 를 정리한다. `pending_action_count` 가 0/누락인 경우에는 resume 을 건너뛰고 경고 로그만 남긴다 (관련 제약은 Appendix A 및 KNOWN_ISSUES 참조).

## 3. Usage

### 3-1. 서버 → FE: `hitl_request`

```json
{
  "type": "hitl_request",
  "session_id": "sess-123",
  "action_requests": [
    {"name": "write_file", "args": {"path": "a.txt", "content": "..."}, "description": "Write file a.txt"}
  ],
  "review_configs": [
    {"action_name": "write_file", "allowed_decisions": ["approve", "edit", "reject"]}
  ]
}
```

### 3-2. FE → 서버: `hitl_response`

```json
{
  "type": "hitl_response",
  "decisions": [
    {"type": "edit", "edited_action": {"name": "write_file", "args": {"path": "a.txt", "content": "edited"}}}
  ]
}
```

`decisions` 길이는 서버가 보낸 `action_requests` 길이와 반드시 같아야 한다 (불일치 시 code 4004). `type` 은 `approve` | `edit` | `reject` 중 하나이며, `edit` 일 때만 `edited_action` 필수. `reject` 는 선택적으로 `message` 를 보내 거부 사유를 agent 쪽에 전달할 수 있다.

---

## Appendix

### A. 제약 사항

- **단일 interrupt/turn**: 한 세션에서 동시 다중 HITL interrupt 는 지원하지 않는다 (한 interrupt 안에서 `action_requests` 가 여러 개일 수는 있다).
- **LangGraph checkpoint 필요**: `HumanInTheLoopMiddleware` 는 Mongo 체크포인터가 활성인 상태에서만 동작한다.
- **Timeout 없음 / Disconnect 잔존**: 연결이 끊긴 뒤 reconnect 해도 pending HITL 이 자동 복원되지 않으며, 새 `chat_message` 가 오면 구 checkpoint 는 버려진다. 상세는 `docs/known_issues/KNOWN_ISSUES.md` 참조.
- **FS 화이트리스트**: FS mutating 도구도 결국 `filesystem_root_dir` 내부만 접근 가능 (`FileManagementToolkit` root 제한).

### B. 주요 구현 파일

| 파일 | 역할 |
|------|------|
| `src/services/agent_service/openai_chat_agent.py` | `_FS_MUTATING_TOOLS`, `_build_interrupt_on`, `HumanInTheLoopMiddleware` 주입, `resume_after_approval`, interrupt → `hitl_request` 이벤트 변환 |
| `src/services/websocket_service/message_processor/event_handlers.py` | `hitl_request` 이벤트 수신 → `AWAITING_APPROVAL` 전이, `pending_action_count` 기록 |
| `src/services/websocket_service/message_processor/processor.py` | 연결 끊김 시 `{"type":"reject"}` decision 주입으로 checkpoint 정리 |
| `src/services/websocket_service/message_processor/models.py` | `TurnStatus.AWAITING_APPROVAL` |
| `src/services/websocket_service/manager/handlers.py` | `handle_hitl_response` — decisions 검증 + 그래프 재개 |
| `src/models/websocket.py` | `HitLActionRequest`, `HitLReviewConfig`, `HitLRequestMessage`, `HitLDecision`, `HitLEditedAction`, `HitLResponseMessage` |

### C. Middleware Chain Order

```
HumanInTheLoop → DelegateTool → Profile → Summary → LTM → TaskStatus (before_model)
                                                    → LTM / Summary consolidation (after_model)
```

빌트인 `HumanInTheLoopMiddleware` 가 가장 먼저 배치되어 gated 도구 호출을 조기에 차단한다.

### D. PatchNote

- 2026-04-18: 빌트인 `HumanInTheLoopMiddleware` migration — payload shape 전면 교체 (`request_id`/`approved` → `action_requests` / `decisions` list-based). 커스텀 `HitLMiddleware` / `ToolGateMiddleware` 제거, `_build_interrupt_on` helper 로 MCP + `delegate_task` + `_FS_MUTATING_TOOLS` gate 구성. WS 연결 끊김 시 reject decision 으로 checkpoint 정리 추가.
- 2026-04-15: 최초 작성 (PR #36 기반, `HitLMiddleware.is_dangerous` + 단일 `request_id`/`approved` 페이로드).
