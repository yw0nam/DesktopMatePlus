# Human in the Loop (HitL) — Feasibility Study

**작성일:** 2026-04-14
**상태:** 구현 가능 (LangGraph + 기존 인프라로 완전 구현 가능)

## 개요

LangGraph Agent가 실행 중 특정 지점(도구 실행 전, 중요 결정 시)에서 일시 중단하고,
유저에게 승인/거부/수정을 요청한 뒤 결과를 받아 실행을 재개하는 기능.

---

## 판정: ✅ 구현 가능 (핵심 인프라 준비 완료)

### 근거

| 항목 | 판정 | 근거 파일 |
|------|------|-----------|
| LangGraph interrupt API | ✅ 지원 | `pyproject.toml:16` — `langgraph>=1.1.2` (interrupt/Command API 포함) |
| MongoDB Checkpointer | ✅ 존재 | `openai_chat_agent.py:130-136` — `AsyncMongoDBSaver` 이미 사용 중 |
| Thread ID per session | ✅ 존재 | `openai_chat_agent.py:225` — `thread_id=session_id` 매핑 확인 |
| Middleware 인터셉트 | ✅ 존재 | `tool_gate_middleware.py:18-131` — `awrap_tool_call()` 패턴 재활용 가능 |
| WS 메시지 타입 확장 | ⚠️ 미존재 | `websocket.py:13-36` — `approval_request` / `approval_response` 타입 추가 필요 |
| Turn 일시중단 인프라 | ✅ 존재 | `processor.py:193-215` — `interrupt_turn()` 패턴 재활용 가능 |
| Callback 비동기 재개 | ✅ 존재 | `callback.py:24-68` — NanoClaw 패턴을 HitL resume에 재활용 가능 |

---

## 핵심 흐름

```
[Client WS]          [MessageProcessor]          [LangGraph Graph]
     |                      |                           |
     |-- chat_message ------>|                           |
     |                      |-- graph.ainvoke() -------->|
     |                      |                       interrupt()
     |                      |<--- __interrupt__ ---------|
     |<-- hitl_request ------|  (승인 요청 WS push)      |
     |                      |                           | (대기)
     |-- hitl_response ----->|                           |
     |                      |-- graph.ainvoke(           |
     |                      |   Command(resume=...)) --->|
     |                      |                       재개 실행
     |<-- stream_token ------|<--- agent events ----------|
```

---

## 구현 방향

### Phase 1 — MVP: 도구 실행 전 승인 요청

**1. 메시지 타입 추가** (`src/models/websocket.py`)

```python
# Server → Client
class HitLRequest(BaseModel):
    request_id: str
    tool_name: str
    tool_args: dict
    description: str  # "이 작업을 실행할까요?"

# Client → Server
class HitLResponse(BaseModel):
    request_id: str
    approved: bool
    feedback: str | None = None  # 수정 요청 시 자연어 피드백
```

**2. LangGraph interrupt 노드** (`src/services/agent_service/`)

```python
from langgraph.types import interrupt, Command

def human_approval_node(state: AgentState):
    decision = interrupt({
        "tool_name": state["pending_tool"],
        "tool_args": state["pending_args"],
    })
    if decision["approved"]:
        return Command(goto="execute_tool")
    return Command(goto="cancel_tool", update={"feedback": decision.get("feedback")})
```

**3. HitL 대기 로직** (`src/services/websocket_service/message_processor/processor.py`)

```python
# asyncio.Queue로 유저 응답 대기
self._hitl_queue: asyncio.Queue | None = None

async def _await_hitl_response(self, timeout: float = 300.0) -> dict:
    self._hitl_queue = asyncio.Queue(maxsize=1)
    try:
        return await asyncio.wait_for(self._hitl_queue.get(), timeout=timeout)
    except asyncio.TimeoutError:
        raise HitLTimeoutError("유저 응답 시간 초과")
    finally:
        self._hitl_queue = None

async def handle_hitl_response(self, response: dict):
    """handlers.py에서 hitl_response 수신 시 호출"""
    if self._hitl_queue:
        await self._hitl_queue.put(response)
```

**4. WS 핸들러 등록** (`src/services/websocket_service/manager/handlers.py`)

```python
case "hitl_response":
    await processor.handle_hitl_response(message.data)
```

---

### Phase 2 — 도구 카테고리별 선택적 적용

모든 도구에 승인을 요구하는 대신, 위험도에 따라 분류:

| 카테고리 | 예시 | 승인 요구 |
|---------|------|----------|
| 읽기 전용 | 검색, 조회 | 불필요 |
| 상태 변경 | 파일 수정, DB 쓰기 | 필요 |
| 외부 발송 | 이메일, Slack 메시지 | 필요 |
| 위험 | 파일 삭제, 시스템 명령 | 필수 |

`tool_gate_middleware.py`의 allowlist 패턴을 확장해 카테고리 매핑 관리.

### Phase 3 — 아규먼트 편집 후 재실행

유저가 단순 승인/거부뿐 아니라 도구 인자를 수정해 재실행 요청 가능:

```python
# hitl_response에 edited_args 추가
class HitLResponse(BaseModel):
    request_id: str
    approved: bool
    edited_args: dict | None = None  # 수정된 인자
    feedback: str | None = None
```

---

## 아키텍처 고려사항

- **Checkpointer 필수**: `interrupt()`는 MongoDB checkpointer 없이 동작 불가. 이미 존재하므로 OK.
- **asyncio.Queue vs Event**: 응답 payload(승인/거부 + 피드백) 동반이므로 `asyncio.Queue` 사용.
- **타임아웃 처리**: `wait_for(timeout=300)` — 5분 미응답 시 자동 취소, `hitl_timeout` 이벤트 push.
- **연결 끊김 대응**: WS disconnect 시 `_hitl_queue`를 정리하고 graph를 abandon 처리 (기존 cleanup 패턴 참조).
- **동시성 보호**: HitL 대기 중 새 chat_message → 기존 "concurrent turn protection (4002)" 로직이 그대로 적용.
- **Breakpoint 방식 대안**: compile 시 `interrupt_before=["tool_call_node"]`로 특정 노드 전 일괄 중단 가능. 조건부 중단이 필요하면 `interrupt()` 함수 방식이 더 유연.

---

## 신규 추가 항목 요약

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `src/models/websocket.py` | 추가 | `HitLRequest`, `HitLResponse` 메시지 타입 |
| `src/services/agent_service/` | 추가 | `human_approval_node` + graph 연결 |
| `src/services/websocket_service/message_processor/processor.py` | 수정 | HitL 대기 queue + resume 로직 |
| `src/services/websocket_service/manager/handlers.py` | 수정 | `hitl_response` 핸들러 등록 |
| `src/services/agent_service/middleware/` | 추가 | `HitLMiddleware` (카테고리별 승인 분기) |

---

## 예상 작업량

| Phase | 신규 코드 | 수정 파일 수 | 난이도 |
|-------|-----------|-------------|--------|
| Phase 1 (MVP) | ~120줄 | 4개 | 중간 |
| Phase 2 (카테고리 분류) | ~80줄 | 1개 | 낮음 |
| Phase 3 (인자 편집) | ~40줄 | 2개 | 낮음 |

---

## 블로커

없음. LangGraph interrupt/Command API, MongoDB checkpointer, WebSocket turn lifecycle 모두 준비 완료.
스키마 추가(WS 메시지 타입 2개)만 하면 즉시 구현 진입 가능.
