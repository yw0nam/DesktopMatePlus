# STM → LangGraph Checkpointer Migration Design

**Date:** 2026-03-25
**Status:** Approved
**Branch:** feat/stm-checkpointer-migration (proposed)

---

## 1. Motivation

- **B.** LangGraph `get_state()` / `update_state()` 등 state 조작 API 활용
- **C.** `@after_model` middleware로 context 관리 (trim, summarize) 통합
- **D.** multi-agent, human-in-the-loop 등 LangGraph 고급 기능 확장 기반

---

## 2. Scope

**Full STM removal** — `MongoDBSTM` 완전 제거.
messages(chat history)는 LangGraph `MongoDBSaver` checkpointer로 이관.
세션 메타데이터(`pending_tasks`, `ltm_last_consolidated_at_turn`, `user_id`, `agent_id`)는 `CustomAgentState` 커스텀 필드로 이동.
세션 목록 조회용 `session_registry` 컬렉션 별도 유지.

---

## 3. Storage Architecture

```
MongoDB
├── checkpointer collection   ← LangGraph MongoDBSaver 자동 관리
│                               (messages + CustomAgentState 전체)
└── session_registry          ← {thread_id, user_id, agent_id, created_at}
                                세션 목록 조회 전용 (얇은 인덱스)

Mem0 / Qdrant
└── LTM                       ← 변경 없음
```

`session_registry`를 별도로 유지하는 이유: LangGraph MongoDBSaver의 내부 직렬화 포맷은 버전 간 변경될 수 있어 `user_id`/`agent_id` 기반 쿼리를 직접 의존하는 것이 불안정하기 때문.

---

## 4. CustomAgentState

```python
from langchain.agents import AgentState
from typing import TypedDict

class ReplyChannel(TypedDict):
    provider: str    # "slack" | "websocket"
    channel_id: str

class PendingTask(TypedDict):
    task_id: str
    description: str
    status: str              # "running" | "done" | "failed"
    created_at: str
    reply_channel: ReplyChannel | None  # 태스크 생성 시점 채널 고정

class CustomAgentState(AgentState):
    user_id: str
    agent_id: str
    pending_tasks: list[PendingTask]
    ltm_last_consolidated_at_turn: int
```

**설계 결정 — `reply_channel`을 task 레벨로:**
세션 레벨에 `reply_channel`을 두면 유저가 Slack → WebSocket으로 세션을 전환할 때 NanoClaw 콜백이 이전 채널로 라우팅되는 문제가 발생한다. `reply_channel`은 태스크가 생성된 시점의 채널 컨텍스트에 종속되어야 하므로 `PendingTask` 내부에 위치시킨다.

---

## 5. Component Changes

### 5-1. AgentService

```python
from langgraph.checkpoint.mongodb import MongoDBSaver

checkpointer = MongoDBSaver(mongo_client, db_name="desktopmate")
agent = create_agent(
    model,
    tools=[...],
    state_schema=CustomAgentState,
    checkpointer=checkpointer,
    middleware=[DelegateToolMiddleware(), LTMConsolidationMiddleware()],
)
```

invoke/stream 시 `thread_id`와 `reply_channel` context 전달:

```python
agent.stream(
    {"messages": [HumanMessage(text), *ltm_prefix]},
    config={"configurable": {"thread_id": session_id}},
    context={"reply_channel": reply_channel},  # Slack이면 값, WebSocket이면 None
)
```

### 5-2. DelegateTaskTool

`stm_service` 의존성 제거. `ToolRuntime`으로 state 읽기/쓰기.

```python
class DelegateTaskTool(BaseTool):
    # stm_service, session_id 필드 제거

    def _run(self, task: str, runtime: ToolRuntime) -> Command:
        task_id = str(uuid4())
        pending = list(runtime.state.get("pending_tasks", []))
        reply_channel = runtime.context.get("reply_channel")

        task_record = PendingTask(
            task_id=task_id,
            description=task,
            status="running",
            created_at=datetime.now(timezone.utc).isoformat(),
            reply_channel=reply_channel,
        )
        pending.append(task_record)

        # NanoClaw POST ...

        return Command(update={
            "pending_tasks": pending,
            "messages": [ToolMessage(f"팀에 작업을 지시했습니다. (task_id: {task_id})", ...)]
        })
```

### 5-3. DelegateToolMiddleware

`session_id` → `thread_id` 키 변경. `stm_service` 주입 로직 제거.

```python
session_id = get_config()["configurable"].get("thread_id", "")
```

`DelegateTaskTool`이 `stm_service`를 더 이상 요구하지 않으므로 tool 인스턴스 생성 시 주입 불필요.

### 5-4. LTMConsolidationMiddleware (신규)

```python
from langchain.agents.middleware import after_model
from langgraph.runtime import Runtime

_LTM_CONSOLIDATION_INTERVAL = 10

@after_model
def ltm_consolidation(state: CustomAgentState, runtime: Runtime) -> dict | None:
    last_consolidated = state.get("ltm_last_consolidated_at_turn", 0)
    current_turn = sum(1 for m in state["messages"] if isinstance(m, HumanMessage))

    if current_turn - last_consolidated < _LTM_CONSOLIDATION_INTERVAL:
        return None

    asyncio.create_task(
        _consolidate_ltm(
            history=list(state["messages"]),
            user_id=state.get("user_id", ""),
            agent_id=state.get("agent_id", ""),
            last_consolidated=last_consolidated,
        )
    )
    return {"ltm_last_consolidated_at_turn": current_turn}
```

`return {"ltm_last_consolidated_at_turn": current_turn}` 로 state를 즉시 업데이트해 중복 트리거를 방지. LTM 실제 저장은 `asyncio.create_task()`로 논블로킹.

### 5-5. callback.py

`stm_service` 제거. `AgentService`를 통해 state 읽기/쓰기.

```python
async def nanoclaw_callback(session_id: str, payload: NanoClawCallbackRequest):
    agent_svc = get_agent_service()
    config = {"configurable": {"thread_id": session_id}}

    # state 읽기
    state = (await agent_svc.agent.aget_state(config)).values

    # pending_tasks에서 task 매칭
    pending_tasks = list(state.get("pending_tasks", []))
    task_record = next((t for t in pending_tasks if t["task_id"] == payload.task_id), None)
    if task_record is None:
        raise HTTPException(404, ...)

    # task status 업데이트 + synthetic message 주입
    task_record["status"] = payload.status
    prefix = "TaskResult" if payload.status == "done" else "TaskFailed"
    synthetic_msg = SystemMessage(content=f"[{prefix}:{payload.task_id}] {payload.summary}")

    await agent_svc.agent.aupdate_state(config, {
        "messages": [synthetic_msg],
        "pending_tasks": pending_tasks,
    })

    # reply_channel은 task 레벨에서 읽음
    reply_channel = task_record.get("reply_channel")
    if reply_channel:
        asyncio.create_task(process_message(
            text="",
            session_id=session_id,
            provider=reply_channel["provider"],
            channel_id=reply_channel["channel_id"],
            ...
        ))
```

### 5-6. process_message() (channel_service)

`stm.upsert_session()`, `stm.update_session_metadata()` 제거.
`session_registry`에 thread 등록 (최초 1회 upsert).
`reply_channel`은 invoke context로 전달.

```python
async def process_message(*, text, session_id, provider, channel_id, ...):
    async with session_lock(session_id):
        # session_registry upsert (최초 1회)
        await _upsert_session_registry(session_id, user_id, agent_id)

        # LTM prefix 로드
        ltm_prefix = await _load_ltm_prefix(ltm, user_id, agent_id, query=text)

        messages = ltm_prefix + ([HumanMessage(text)] if text else [])
        reply_channel = {"provider": provider, "channel_id": channel_id}

        result = await agent_service.invoke(
            messages=messages,
            session_id=session_id,
            context={"reply_channel": reply_channel},
            ...
        )
        ...
```

### 5-7. load_context() → LTM only

STM history 로드 제거. LTM prefix 조회만 남김. 함수명 변경 고려: `load_ltm_prefix()`.

```python
async def load_ltm_prefix(
    ltm_service: LTMService | None,
    user_id: str,
    agent_id: str,
    query: str,
) -> list[BaseMessage]:
    if not ltm_service:
        return []
    result = await asyncio.to_thread(ltm_service.search_memory, query=query, ...)
    if result.get("results"):
        return [SystemMessage(content=f"Long-term memories: {json.dumps(result)}")]
    return []
```

### 5-8. API Routes — /v1/stm 재작성

| 엔드포인트 | 구현 |
|---|---|
| `GET /get-chat-history` | `agent.get_state()` → messages 추출 |
| `POST /add-chat-history` | `agent.update_state({"messages": [...]})` |
| `GET /sessions` | `session_registry` 컬렉션 직접 쿼리 |
| `DELETE /sessions/{id}` | checkpointer thread 삭제 + registry 삭제 |
| `PATCH /sessions/{id}/metadata` | `agent.update_state({custom fields})` |

### 5-9. event_handlers.py

`save_turn()` 호출 제거. checkpointer가 자동 저장하므로 `stream_end` 이후 별도 persist 불필요.

---

## 6. Data Flow

### WebSocket
```
WebSocket 메시지
→ event_handlers → load_ltm_prefix()
→ agent.stream(messages, config={thread_id}, context={reply_channel: None})
→ checkpointer 자동 저장
→ LTMConsolidationMiddleware (조건 충족 시 asyncio.create_task)
→ WebSocket 클라이언트 스트리밍
```

### Slack
```
Slack webhook → process_message()
→ session_registry upsert → load_ltm_prefix()
→ agent.invoke(messages, config={thread_id}, context={reply_channel: {slack}})
→ checkpointer 자동 저장
→ LTMConsolidationMiddleware
→ slack.send_message()
```

### NanoClaw Callback
```
POST /v1/callback/nanoclaw/{session_id}
→ agent.aget_state() → pending_tasks에서 task 매칭
→ agent.aupdate_state({messages: [synthetic], pending_tasks: updated})
→ task.reply_channel 확인
  → Slack이면: process_message(text="") fire-and-forget
  → None이면: 종료 (WebSocket 유저는 다음 메시지 시 context에서 확인)
```

---

## 7. Removed

- `src/services/stm_service/` 전체
- `src/services/websocket_service/manager/memory_orchestrator.py` (LTM 부분은 middleware로 이전)
- `get_stm_service()` / STM 초기화 in `service_manager.py`, `main.py`
- `DelegateTaskTool.stm_service`, `DelegateTaskTool.session_id` 필드
- `save_turn()` STM 저장 로직
- `load_context()` STM history 로드 부분

---

## 8. Testing Strategy

- `CustomAgentState` 필드 직렬화/역직렬화 단위 테스트
- `DelegateTaskTool` — `ToolRuntime` mock으로 state 읽기/쓰기 검증
- `LTMConsolidationMiddleware` — turn count 조건, fire-and-forget 트리거 검증
- `callback.py` — `aupdate_state` 호출 + `reply_channel` 라우팅 분기 검증
- `GET /sessions` — `session_registry` 쿼리 검증
- 채널 전환 시나리오 (Slack → WebSocket 세션 재사용) 통합 테스트
