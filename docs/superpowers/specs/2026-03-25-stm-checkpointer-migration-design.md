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
세션 목록 조회 및 sweep용 `session_registry` 컬렉션 별도 유지.

---

## 3. Storage Architecture

```
MongoDB
├── checkpointer collection   ← LangGraph MongoDBSaver 자동 관리
│                               (messages + CustomAgentState 전체)
└── session_registry          ← {thread_id, user_id, agent_id, created_at, updated_at}
                                세션 목록 조회 + BackgroundSweep 전용 (얇은 인덱스)

Mem0 / Qdrant
└── LTM                       ← 변경 없음
```

`session_registry`를 별도로 유지하는 이유: LangGraph MongoDBSaver의 내부 직렬화 포맷은
버전 간 변경될 수 있어 `user_id`/`agent_id` 기반 쿼리를 직접 의존하는 것이 불안정하기 때문.
`updated_at`은 `GET /sessions` 최신순 정렬에 필요하며, 메시지 수신 시마다 갱신된다.

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
    knowledge_saved: bool  # disconnect 시 knowledge summary 중복 방지
```

**설계 결정 — `reply_channel`을 task 레벨로:**
세션 레벨에 `reply_channel`을 두면 유저가 Slack → WebSocket으로 세션을 전환할 때
NanoClaw 콜백이 이전 채널로 라우팅되는 문제가 발생한다.
`reply_channel`은 태스크가 생성된 시점의 채널 컨텍스트에 종속되어야 하므로
`PendingTask` 내부에 위치시킨다.

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
    context={"reply_channel": reply_channel},
)
```

**`session_id` / `thread_id` 경계 정책:**
- **외부 인터페이스** (API 파라미터, WebSocket 메시지, NanoClaw payload): `session_id` 유지 — 클라이언트 breaking change 없음
- **LangGraph 내부 configurable 키**: `thread_id` 사용 — LangGraph 표준 준수
- **매핑**: `AgentService` 내부에서 `session_id` → `thread_id`로 변환 후 `config`에 주입

```python
# AgentService 내부에서만 변환
config = {"configurable": {"thread_id": session_id}}
```

`DelegateToolMiddleware`는 `get_config()["configurable"].get("thread_id", "")`로 읽음 (내부 전용).

### 5-2. DelegateTaskTool

`stm_service`, `session_id` 필드 제거. `ToolRuntime`으로 state 읽기/쓰기.
기존 동기 `httpx.Client._run()` → `async _arun()` + `httpx.AsyncClient` 로 교체.

```python
class DelegateTaskTool(BaseTool):
    async def _arun(self, task: str, runtime: ToolRuntime) -> Command:
        task_id = str(uuid4())
        pending = list(runtime.state.get("pending_tasks", []))
        reply_channel = runtime.context.get("reply_channel")

        task_record = PendingTask(
            task_id=task_id, description=task, status="running",
            created_at=datetime.now(timezone.utc).isoformat(),
            reply_channel=reply_channel,
        )
        pending.append(task_record)

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            await client.post(f"{NANOCLAW_URL}{NANOCLAW_WEBHOOK_PATH}", json=payload)

        return Command(update={
            "pending_tasks": pending,
            "messages": [ToolMessage(f"팀에 작업을 지시했습니다. (task_id: {task_id})", ...)],
        })
```

### 5-3. DelegateToolMiddleware

`stm_service` 주입 로직 제거. configurable 키 `"session_id"` → `"thread_id"` 변경.

```python
session_id = get_config()["configurable"].get("thread_id", "")
delegate = DelegateTaskTool()  # 인자 없음
```

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
        _safe_consolidate_ltm(  # 예외 로깅 래퍼
            history=list(state["messages"]),
            user_id=state.get("user_id", ""),
            agent_id=state.get("agent_id", ""),
            last_consolidated=last_consolidated,
        )
    )
    return {"ltm_last_consolidated_at_turn": current_turn}


async def _safe_consolidate_ltm(*args, **kwargs):
    """asyncio.create_task silent failure 방지 — 예외는 반드시 로깅."""
    try:
        await _consolidate_ltm(*args, **kwargs)
    except Exception as e:
        logger.error(f"LTM consolidation failed: {e}")
```

`@after_model`은 단일 turn 내 여러 번 발생할 수 있으나(tool 호출 후 재진입),
`ltm_last_consolidated_at_turn`을 즉시 업데이트해 state에 반영하므로 중복 트리거는 threshold 조건이 차단한다.
`asyncio.create_task()`로 LTM 저장은 논블로킹. 모든 background task는 예외 로깅 래퍼를 통해 실행.

### 5-5. callback.py

`stm_service` 제거. `AgentService`를 통해 state 읽기/쓰기.

```python
async def nanoclaw_callback(session_id: str, payload: NanoClawCallbackRequest):
    agent_svc = get_agent_service()
    config = {"configurable": {"thread_id": session_id}}

    state = (await agent_svc.agent.aget_state(config)).values
    pending_tasks = list(state.get("pending_tasks", []))
    task_record = next((t for t in pending_tasks if t["task_id"] == payload.task_id), None)
    if task_record is None:
        raise HTTPException(404, ...)

    task_record["status"] = payload.status
    prefix = "TaskResult" if payload.status == "done" else "TaskFailed"
    synthetic_msg = SystemMessage(content=f"[{prefix}:{payload.task_id}] {payload.summary}")

    try:
        await agent_svc.agent.aupdate_state(config, {
            "messages": [synthetic_msg],
            "pending_tasks": pending_tasks,
        })
    except Exception as e:
        logger.error(f"State update failed for session {session_id}: {e}")
        raise HTTPException(status_code=503, detail="State update failed")

    # reply_channel은 task 레벨에서 읽음 (세션 레벨 아님)
    reply_channel = task_record.get("reply_channel")
    if reply_channel:
        asyncio.create_task(process_message(
            text="", session_id=session_id,
            provider=reply_channel["provider"],
            channel_id=reply_channel["channel_id"], ...
        ))
```

### 5-6. process_message() (channel_service)

`stm.upsert_session()`, `stm.update_session_metadata()` 제거.
`session_registry` upsert (최초 1회) + `updated_at` 갱신.
`reply_channel`은 invoke context로 전달.

```python
async def process_message(*, text, session_id, provider, channel_id, ...):
    async with session_lock(session_id):
        await _upsert_session_registry(session_id, user_id, agent_id)  # updated_at 포함
        ltm_prefix = await load_ltm_prefix(ltm, user_id, agent_id, query=text)
        messages = ltm_prefix + ([HumanMessage(text)] if text else [])
        reply_channel = {"provider": provider, "channel_id": channel_id}

        result = await agent_service.invoke(
            messages=messages,
            session_id=session_id,
            context={"reply_channel": reply_channel}, ...
        )
```

### 5-7. handlers.py (WebSocket)

`get_stm_service()` 제거. `load_context()` → `load_ltm_prefix()`.
`metadata["stm_service"]` 제거. `session_registry` upsert + `updated_at` 갱신 추가.

```python
# 변경 전
stm_service = get_stm_service()
message_history = await load_context(stm_service=stm_service, ...)
metadata["stm_service"] = stm_service

# 변경 후
ltm_prefix = await load_ltm_prefix(ltm_service=ltm_service, ...)
message_history = ltm_prefix + [HumanMessage(content=content)]
await _upsert_session_registry(session_id, user_id, agent_id)
# metadata에 stm_service 없음
```

stream 호출 시 `reply_channel=None` context 전달:

```python
agent_stream = agent_service.stream(
    messages=message_history,
    session_id=session_id,
    context={"reply_channel": None}, ...
)
```

### 5-8. load_context() → load_ltm_prefix()

STM history 로드 제거. LTM prefix 조회만 남김. 함수명 변경: `load_ltm_prefix()`.

```python
async def load_ltm_prefix(
    ltm_service: LTMService | None, user_id: str, agent_id: str, query: str,
) -> list[BaseMessage]:
    if not ltm_service:
        return []
    result = await asyncio.to_thread(ltm_service.search_memory, query=query, ...)
    if result.get("results"):
        return [SystemMessage(content=f"Long-term memories: {json.dumps(result)}")]
    return []
```

### 5-9. BackgroundSweepService 재설계

현재 `stm_service.list_all_sessions()` + `get/update_session_metadata()` 의존.
이관 후: `session_registry`로 thread 목록 조회 → `agent.aget_state()` per session.
`reply_channel`은 task 레벨에서 읽음 (세션 레벨 metadata 없음).

```python
class BackgroundSweepService:
    def __init__(self, agent_service, session_registry_col, config, slack_service_fn):
        self._agent = agent_service
        self._registry = session_registry_col
        ...

    async def _sweep_once(self) -> None:
        now = datetime.now(timezone.utc)
        for session in self._registry.find({}, {"thread_id": 1}):
            thread_id = session["thread_id"]
            config = {"configurable": {"thread_id": thread_id}}
            state = (await self._agent.agent.aget_state(config)).values
            pending_tasks = list(state.get("pending_tasks", []))
            if not pending_tasks:
                continue

            updated = False
            for task in pending_tasks:
                if task.get("status") in _EXPIRABLE_STATUSES and _is_expired(task, now, ...):
                    task["status"] = "failed"
                    updated = True

            if updated:
                await self._agent.agent.aupdate_state(config, {"pending_tasks": pending_tasks})
                for task in pending_tasks:
                    if task["status"] == "failed":
                        rc = task.get("reply_channel")
                        if rc and rc.get("provider") == "slack":
                            ...  # Slack 알림
```

### 5-10. API Routes — /v1/stm 재작성

| 엔드포인트 | 구현 |
|---|---|
| `GET /get-chat-history` | `agent.get_state()` → messages 추출 |
| `POST /add-chat-history` | `agent.update_state({"messages": [...]})` |
| `GET /sessions` | `session_registry` 쿼리 (user_id + agent_id 필터, updated_at 정렬) |
| `DELETE /sessions/{id}` | checkpointer thread 삭제 + `session_registry` row 삭제 |
| `PATCH /sessions/{id}/metadata` | `agent.update_state({custom fields})` |

### 5-11. disconnect_handler.py

`stm_service` 제거. `agent.get_state()`로 messages 및 `knowledge_saved` 플래그 조회.
`agent.update_state()`로 `knowledge_saved = True` 기록.

```python
async def on_disconnect_handler(session_id, user_id, agent_id, agent_service, delegate):
    config = {"configurable": {"thread_id": session_id}}
    state = (await agent_service.agent.aget_state(config)).values

    if state.get("knowledge_saved"):
        return

    messages = state.get("messages", [])
    human_count = sum(1 for m in messages if isinstance(m, HumanMessage))
    if human_count < MIN_TURNS_FOR_SUMMARY:
        return

    payload = build_delegate_payload(session_id, user_id, agent_id, messages=messages)
    await delegate(payload)
    await agent_service.agent.aupdate_state(config, {"knowledge_saved": True})
```

**Option B (stm_fetch_url) 처리:**
`build_delegate_payload()`의 Option B 경로(`stm_fetch_url`)는 `/v1/stm/{session_id}/messages`를
NanoClaw에게 전달한다. 이 엔드포인트는 §5-10에서 재작성되는 `/v1/stm` 라우트의 일부로
`agent.get_state()` 기반으로 유지되어야 한다.

### 5-12. health.py

`check_stm()` 메서드 제거. MongoDB checkpointer 연결 ping으로 교체.

```python
async def check_mongodb(self) -> tuple[bool, str | None]:
    """Check MongoDB checkpointer connectivity."""
    try:
        mongo_client.admin.command("ping")
        return True, None
    except Exception as e:
        return False, f"MongoDB checkpointer ping failed: {str(e)}"
```

`overall_status` 집계에서 `stm_ready` → `mongodb_ready`로 교체.

### 5-13. event_handlers.py

`save_turn()` 호출 제거. checkpointer 자동 저장. `turn.metadata`에서 `stm_service` 키 참조 제거.

---

## 6. Data Flow

### WebSocket
```
WebSocket 메시지
→ handlers.py: session_registry upsert, load_ltm_prefix()
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
→ checkpointer 자동 저장 → LTMConsolidationMiddleware
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

### Background Sweep
```
BackgroundSweepService._sweep_once()
→ session_registry.find() → thread_id 목록
→ per thread: agent.aget_state() → pending_tasks 확인
→ 만료된 task: agent.aupdate_state({pending_tasks: updated})
→ task.reply_channel이 slack이면 Slack 알림
```

---

## 7. Removed

- `src/services/stm_service/` 전체
- `src/services/websocket_service/manager/memory_orchestrator.py` (LTM 부분 → middleware 이전)
- `get_stm_service()` / STM 초기화 in `service_manager.py`, `main.py`
- `DelegateTaskTool.stm_service`, `DelegateTaskTool.session_id` 필드
- `save_turn()` STM 저장 로직
- `load_context()` → `load_ltm_prefix()`로 교체
- `handlers.py`의 `stm_service` 참조 및 `metadata["stm_service"]`
- `BackgroundSweepService` 생성자의 `stm_service` 인자
- `disconnect_handler.py`의 `STMService` 의존성 (`on_disconnect_handler`, `build_delegate_payload`)

---

## 8. Testing Strategy

- `CustomAgentState` 필드 직렬화/역직렬화 단위 테스트
- `DelegateTaskTool` — `ToolRuntime` mock으로 state 읽기/쓰기, async HTTP 검증
- `LTMConsolidationMiddleware` — turn count 조건, 중복 트리거 방지, fire-and-forget 검증
- `callback.py` — `aget_state` / `aupdate_state` 호출 + task 레벨 `reply_channel` 라우팅 분기 검증
- `BackgroundSweepService` — `session_registry` 순회, `aget_state` / `aupdate_state`, Slack 알림 분기 검증
- `handlers.py` — `stm_service` 미참조 확인, `session_registry` upsert 검증
- `GET /sessions` — `session_registry` 쿼리 + `updated_at` 정렬 검증
- `disconnect_handler.py` — `aget_state` 기반 messages/knowledge_saved 조회, `aupdate_state` 호출 검증
- 채널 전환 시나리오 통합 테스트: Slack → WebSocket 전환 후 NanoClaw 콜백이 Slack으로 정확히 라우팅되는지 확인
