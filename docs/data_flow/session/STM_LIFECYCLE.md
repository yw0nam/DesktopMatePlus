# STM Lifecycle Data Flow

Updated: 2026-04-08

## 1. Synopsis

- **Purpose**: Short-Term Memory(대화 이력) 생성·복원·만료·정리 전체 라이프사이클
- **I/O**: `session_id` (UUID) ↔ MongoDB (LangGraph checkpointer + session_registry)
- **핵심**: `session_id` = LangGraph `thread_id` — 모든 STM 작업의 기준 키

## 2. Core Logic

### 2-1. 세션 생성 / 복원

```
handle_chat_message(session_id):
  if session_id is None:
    session_id = str(uuid4())        # 신규 세션
  registry.upsert(session_id, user_id, agent_id)
    └─ MongoDB session_registry: {thread_id, user_id, agent_id, created_at, updated_at}

agent_service.stream(messages, session_id):
  config = {"configurable": {"thread_id": session_id}}
  agent.astream(config=config)
    └─ LangGraph MongoDBSaver 자동 동작:
       - 기존 checkpoint 존재 → 이전 messages 전체 로드 (세션 복원)
       - 없으면 신규 state 초기화
```

**Persona 주입**: 신규 세션에만 SystemMessage로 삽입. 기존 세션 재개 시 생략.

### 2-2. 자동 저장 (Auto-Checkpoint)

`astream()` / `ainvoke()` 호출 시 LangGraph MongoDBSaver가 자동 저장. 수동 save 불필요.

```
LangGraph astream():
  ├─ LTM Retrieve Hook (before_model):
  │   └─ ltm.search_memory(query) → SystemMessage[0]에 주입
  ├─ Model Call
  ├─ Tool Calls (DelegateTaskTool 등)
  ├─ LTM Consolidation Hook (after_model):
  │   └─ 10턴마다 fire-and-forget 통합
  └─ MongoDBSaver.checkpoint() ← 자동, 매 turn 저장
```

**CustomAgentState 구조** (`state.py`):
```python
{
  "messages":   list[BaseMessage],       # 전체 대화 이력
  "user_id":    str,
  "agent_id":   str,
  "pending_tasks": list[PendingTask],    # 위임 태스크 상태
  "ltm_last_consolidated_at_turn": int,
  "knowledge_saved": bool                # 중복 저장 방지 플래그
}
```

### 2-3. 백그라운드 Sweep (만료 처리)

60초마다 실행. pending_tasks TTL = 300초.

```
BackgroundSweepService._sweep_once():
  for session in registry.find_all():
    state = agent.aget_state(config)
    for task in state["pending_tasks"]:
      if status in {"pending", "running"} and age > 300s:
        task["status"] = "failed"
    agent.aupdate_state(config, {"pending_tasks": updated})
    if failed and reply_channel:
      → Slack 알림 전송
```

### 2-4. 연결 종료 처리

```
on_disconnect(session_id):
  state = agent.aget_state(config)
  if knowledge_saved: return           # 중복 방지
  if HumanMessage count < 3: return    # 대화 없으면 스킵
  build_delegate_payload()
    ├─ turns < 30: messages 인라인 포함
    └─ turns >= 30: STM REST API URL 참조
  agent.aupdate_state({"knowledge_saved": True})
```

## 3. 전체 시퀀스

```mermaid
sequenceDiagram
    participant Client
    participant WS as WebSocket Handler
    participant Reg as SessionRegistry (MongoDB)
    participant Agent as AgentService (LangGraph)
    participant DB as MongoDB (Checkpointer)
    participant Sweep as BackgroundSweep

    Note over Client, WS: 신규 세션
    Client->>WS: chat_message (session_id=null)
    WS->>WS: session_id = uuid4()
    WS->>Reg: upsert(session_id, user_id, agent_id)
    WS->>Agent: stream(messages, session_id)
    Agent->>DB: aget_state → empty (신규)
    Agent->>Agent: Persona SystemMessage 주입
    Agent->>DB: checkpoint() ← 자동 저장
    Agent-->>WS: stream events

    Note over Client, WS: 기존 세션 복원
    Client->>WS: chat_message (session_id=existing)
    WS->>Reg: upsert(updated_at 갱신)
    WS->>Agent: stream(messages, session_id)
    Agent->>DB: aget_state → 이전 messages 로드
    Note right of Agent: Persona 주입 생략
    Agent->>DB: checkpoint() ← 자동 저장
    Agent-->>WS: stream events

    Note over Sweep: 60s 주기
    Sweep->>Reg: find_all() → session 목록
    Sweep->>Agent: aget_state(per session)
    Sweep->>Agent: aupdate_state(failed tasks)

    Note over Client, WS: 연결 종료
    Client->>WS: disconnect
    WS->>Agent: aget_state(session_id)
    WS->>Agent: aupdate_state(knowledge_saved=True)
```

---

## Appendix

### A. 주요 구현 파일

| 파일 | 역할 |
|------|------|
| `src/services/agent_service/openai_chat_agent.py` | stream(), LangGraph agent 초기화 |
| `src/services/agent_service/state.py` | CustomAgentState, PendingTask |
| `src/services/agent_service/session_registry.py` | MongoDB session_registry CRUD |
| `src/services/task_sweep_service/sweep.py` | 백그라운드 만료 처리 |
| `src/services/websocket_service/manager/disconnect_handler.py` | 연결 종료 처리 |
| `src/services/agent_service/middleware/ltm_middleware.py` | LTM inject/consolidate |
| `yaml_files/services/checkpointer.yml` | MongoDB 연결 설정 |

### B. MongoDB 컬렉션 구조

**session_registry** (수동 관리):
```json
{
  "thread_id": "uuid",
  "user_id": "user-id",
  "agent_id": "agent-id",
  "created_at": "ISO timestamp",
  "updated_at": "ISO timestamp"
}
```

**checkpointer collections** (LangGraph 자동 관리):
- 내부 스키마, 직접 접근 금지. `aget_state()` / `aupdate_state()` API만 사용.

### C. PendingTask TTL

- 기본값: 300초 (`yaml_files/services/task_sweep_service/sweep.yml`)
- 만료 시 `status = "failed"`, reply_channel이 있으면 Slack 알림
- 상태: `pending` → `running` → `done` | `failed`

### D. PatchNote

2026-04-08: 최초 작성. LangGraph MongoDBSaver 기반 STM 라이프사이클 코드베이스 추적 기반.
