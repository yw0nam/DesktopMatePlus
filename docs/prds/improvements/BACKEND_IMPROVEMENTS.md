# Backend Code Improvements

Updated: 2026-03-07

## 1. Synopsis

- **Purpose**: 코드 리뷰에서 발견된 버그 및 설계 결함 수정 목록.
- **Scope**: `agent_service`, `main.py`, `websocket_service` 전반.
- **Priority**: P0 (버그/이벤트 루프 블로킹) -> P1 (설계 결함) -> P2 (코드 품질)

---

## 2. Issues

### [P0] 비동기 스트림 내 블로킹 호출

- **File**: `src/services/agent_service/openai_chat_agent.py:194`
- **Problem**: `async def stream()` 안에서 동기 메서드 `self.save_memory()`를 직접 호출. MongoDB I/O가 이벤트 루프를 블로킹함. 모든 WebSocket 연결이 메모리 저장이 끝날 때까지 멈춤.
- **현재 코드**:
  ```python
  # async_save_memory는 주석 처리, 동기 버전 사용 중
  session_id = self.save_memory(...)  # BLOCKS event loop
  ```
- **Fix**: `asyncio.create_task(self.async_save_memory(...))` 로 fire-and-forget. 동기 `save_memory` 메서드 삭제.
- **Caution**: `create_task`는 "Fire-and-forget"이므로, `async_save_memory` 내부 최상단에 반드시 `try-except` 블록을 두고 로깅해야 함. 그렇지 않으면 메모리 저장 실패 시 아무런 흔적 없이 무시됨.

---

### [P0] LTM Consolidation TOCTOU + 무한 반복 트리거

- **File**: `src/services/agent_service/service.py:166`
- **Problem 1 (TOCTOU)**: `get_chat_history()` 로 count를 읽은 후 `add_memory()` 사이에 동시 요청이 오면 두 요청 모두 modulo 조건을 통과해 LTM에 중복 저장됨.
- **Problem 2 (무한 트리거)**: `len(history) % batch_size == 0` 조건은 20, 40, 60, 80... 번째 메시지마다 영원히 트리거됨. 의도는 "N턴마다 한 번"이지만 실제로는 "N의 배수마다 항상".
- **Fix**: STM session metadata에 `ltm_last_consolidated_at_turn`을 저장하고, `current_turn - last_consolidated >= N` 조건으로 교체. 이미 `service.py:122` TODO 주석에 올바른 방향이 적혀 있음 — 해당 TODO를 실제로 구현.
- **Caution**: 기존 세션 데이터에는 `ltm_last_consolidated_at_turn` 필드가 없을 수 있으므로 `.get("ltm_last_consolidated_at_turn", 0)` 처럼 기본값 처리를 확실히 해야 함.

---

### [P1] `run_id` vs `session_id` 혼재

- **File**: `src/services/agent_service/openai_chat_agent.py:161`
- **Problem**: `run_id = str(uuid4())`를 LangGraph `thread_id`로 쓰고, `stream_end` 이벤트의 `turn_id`로도 내보냄. 동시에 `session_id`는 `save_memory()` 반환값으로 덮어써짐. 호출자 입장에서 어떤 ID가 무엇인지 추적 불가.
- **Semantic 정의**:
  | ID | 의미 | 생성 주체 |
  |----|------|-----------|
  | `session_id` | 유저-에이전트 대화 세션 (영속) | WebSocket handler |
  | `turn_id` | 단일 요청-응답 사이클 | `MessageProcessor` |
  | `thread_id` | LangGraph 내부 체크포인트 키 | `OpenAIChatAgent` (내부) |
- **Fix**: `run_id`를 LangGraph 전용 내부 변수로 유지. `stream_start/end`에서 `turn_id`는 호출자가 주입하거나 제거. `session_id`를 `save_memory` 반환값으로 덮어쓰는 라인 제거.

---

### [P1] `_config_paths` 글로벌 상태

- **File**: `src/main.py:21`
- **Problem**: `lifespan` 함수에 설정 경로를 전달하기 위해 모듈 레벨 mutable global dict 사용. `lifespan`은 `FastAPI` 앱 생성 시 클로저로 캡처되므로, 글로벌 없이도 전달 가능.
- **Fix**:
  ```python
  def create_app(config_paths: dict) -> FastAPI:
      @asynccontextmanager
      async def lifespan(app: FastAPI):
          # config_paths 클로저로 캡처
          ...
      app = FastAPI(..., lifespan=lifespan)
      return app
  ```
  `_config_paths` 글로벌 dict 삭제.

---

### [P1] `WeakSet`으로 인한 heartbeat 태스크 누락 위험

- **File**: `src/services/websocket_service/manager/websocket_manager.py:48`
- **Problem**: `self._heartbeat_tasks: WeakSet = WeakSet()`. asyncio가 실행 중인 Task를 strong reference로 보유하지만, shutdown 시 이 set을 순회해 태스크를 명시적으로 cancel하려면 strong reference가 필요. WeakSet이면 GC에 의해 예기치 않게 비워질 수 있음.
- **Fix**: `set[asyncio.Task]`로 교체. shutdown 시 `task.cancel()` + `await asyncio.gather(...)` 명시적 처리.
- **Caution**: `set` 사용 시 완료된 태스크가 계속 쌓여 메모리 누수가 발생할 수 있음. 태스크 생성 시 `task.add_done_callback(self._heartbeat_tasks.discard)`를 등록하여 완료된 태스크는 즉시 제거되도록 해야 함.

---

### [P2] `save_memory` / `async_save_memory` 중복

- **File**: `src/services/agent_service/service.py:131`
- **Problem**: 두 메서드가 동일한 로직을 sync/async 버전으로 중복 구현. P0 수정 후 동기 버전은 사용처가 없어짐.
- **Fix**: `save_memory` (sync) 삭제. `async_save_memory`만 유지. 메서드명을 `save_memory`로 rename해도 무방.

---

### [P2] `_process_message` 버퍼 flush 로직 4중 반복

- **File**: `src/services/agent_service/openai_chat_agent.py:264`
- **Problem**: `if node == "tools": yield tool_result ... elif node == "agent": yield stream_token` 분기가 정상 흐름, 최대 버퍼 초과, 자연 분할점, 에러 핸들러, 마지막 flush에서 총 4회 반복됨.
- **Fix**: 내부 헬퍼로 추출:
  ```python
  def _flush_buffer(node: str, buffer: str) -> dict:
      if node == "tools":
          return {"type": "tool_result", "result": buffer.strip(), "node": node}
      return {"type": "stream_token", "chunk": buffer.strip(), "node": node}
  ```

---

## 3. 작업 순서

| 순서 | Issue | 예상 영향 |
|------|-------|-----------|
| 1 | P0 블로킹 save_memory | 이벤트 루프 블로킹 즉시 해소 |
| 2 | P1 run_id/session_id 혼재 | P0 수정과 함께 처리 (같은 파일) |
| 3 | P1 글로벌 config_paths | main.py 독립 수정 |
| 4 | P0 LTM TOCTOU | STM metadata 스키마 변경 필요 |
| 5 | P1 WeakSet | websocket_manager 독립 수정 |
| 6 | P2 중복/반복 코드 | 마지막에 일괄 정리 |

---

## Appendix

### A. 연관 파일
- `src/services/agent_service/openai_chat_agent.py`
- `src/services/agent_service/service.py`
- `src/services/websocket_service/manager/websocket_manager.py`
- `src/main.py`

### B. LTM metadata 기반 trigger (P0 상세)

`stm_service.get_session_metadata(session_id)`에서 `ltm_last_consolidated_at_turn: int` 필드 활용.

```python
meta = stm_service.get_session_metadata(session_id)
last = meta.get("ltm_last_consolidated_at_turn", 0)
current = len(history) // 2  # turn count
if current - last >= LTM_CONSOLIDATION_TURN_INTERVAL:
    ltm_service.add_memory(messages=history[last*2:], ...)
    stm_service.update_session_metadata(session_id, {"ltm_last_consolidated_at_turn": current})
```
